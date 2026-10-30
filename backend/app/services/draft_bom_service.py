"""Read-only planning takeoff. No review/approval or model state is modified."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
import re

from sqlalchemy import func, select
from app.models import FloorPlan, FloorPlanInterpretationRun, ProjectFloor, SymbolLegend
from app.repositories.floor_plan_lifecycle_repository import active_floor_plan
from app.repositories import material_catalog_repository as catalog, material_price_repository as prices
from app.repositories.analysis_settings_repository import latest_scales, latest_elevation
from app.routing.endpoint_connections import connect_touching_endpoints
from app.repositories.floor_plan_interpretation_repository import find_latest_review, find_latest_previous_review
from app.services.demo_interpretation_service import _candidate, _review_document
from app.services.wiring_legend_service import annotate_wiring
from app.ai.floor_plan_interpretation.reviewed_reference import inherit_review_draft
from app.geometry.path_lengths import unique_paths_length
from app.geometry.wire_network import takeoff_path_groups
from app.geometry.device_mounting import resolved_mounting, connection_height
from app.services.layout_materials import route_device_layout


def material_key(name):
    # Only presentation normalization, never remove ratings, dimensions or brands.
    name = re.sub(r'\s*\[(?:pdf-[^\]]+|sheet-\d+:L[\w-]+|u:[\w-]+)\]\s*$', '', name or '')
    return ' '.join(re.findall(r'[a-z0-9]+', name.casefold()))


PAPER_MM = {'A5': (148, 210), 'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594),
            'A1': (594, 841), 'A0': (841, 1189)}


def paper_dimensions(paper_size, custom_width_mm=None, custom_height_mm=None):
    if paper_size == 'CUSTOM':
        if any(v is None or not math.isfinite(v) or not 0 < v <= 10000
               for v in (custom_width_mm, custom_height_mm)):
            raise ValueError('Custom sheet dimensions must be positive millimetres, at most 10000.')
        return custom_width_mm, custom_height_mm
    if custom_width_mm is not None or custom_height_mm is not None:
        raise ValueError('Custom dimensions require CUSTOM paper size.')
    if paper_size not in PAPER_MM:
        raise ValueError('Unknown paper size.')
    return PAPER_MM[paper_size]


def paper_scale(width, height, paper_size, custom_width_mm=None, custom_height_mm=None):
    """Planning fallback at 1:100, never an approved source-page calibration."""
    short, long = sorted(paper_dimensions(paper_size, custom_width_mm, custom_height_mm))
    pixel_short, pixel_long = sorted((width, height))
    if not all(math.isfinite(v) and v > 0 for v in (pixel_short, pixel_long)):
        raise ValueError('Invalid source dimensions.')
    # 1:100: paper millimetres / 10 = real metres. Fit the long page edge.
    return pixel_long / (long / 10)


def conduit_choices(materials):
    return [m for m in materials if re.match(r'^conduit\b', m.get('category') or '', re.I)
            and re.search(r'\b(?:pipe|tube|tubing|conduit)\b', m['name'], re.I)
            and m['unit'] in ('meter', 'length', 'roll') and m['unit_price'] is not None]


def product_brand(product):
    return (product.get('assembly') or {}).get('brand') or {
        'PANASONIC':'Panasonic','HEWITT':'Hewitt-Dade / Lexington','NICHI':'Nichi',
        'BELDEN':'Belden','ALANTEK':'Alantek','COMMSCOPE':'CommScope','MOLDEX':'Moldex','PHELPDODGE':'Phelps Dodge',
    }.get(product.get('code','').split('-')[0])


def apply_conduit_choice(rows, materials, material_id):
    """Explicit draft SKU; never equate a purchase stick/length with one metre."""
    matches = [m for m in conduit_choices(materials) if m['id'] == material_id]
    if len(matches) != 1:
        raise ValueError('Choose an active priced conduit material.')
    material = matches[0]
    for row in rows:
        if (row['kind'] == 'path' and (row.get('canonical') or row.get('origin') in ('observed', 'generated', 'manual', 'mixed'))
                and row['unit'] in ('meter', 'source pixel') and (row.get('material_kind') == 'conduit'
                    or not row.get('material_kind') and re.search(r'\bconduit\b', row['name'], re.I))):
            row.update(preferred_material_id=material_id,
                       basis=row['basis'] + ' Draft material choice; a non-metre purchase unit requires an explicit conversion.')


def wire_choices(materials):
    # Explicit selection only: data cable is never silently mapped to power wire.
    return [m for m in materials if m['unit'] in ('meter', 'roll', 'length')
            and (re.search(r'\b(?:wire|cable)\b', m['name'], re.I) or re.search(r'\b(?:COPPER|FIBER)\s*(?:-\s*)?CABLES?\b',m.get('category',''),re.I))
            and not re.search(r'\b(?:connector|tray|tie|clip|lug|gland|manager|patchcord|patch cord|panel)\b', m['name'], re.I)]


def wire_unit_length(material):
    if material['unit'] == 'meter':
        return 1
    # Only an explicit purchase-length annotation; never infer from brand/gauge.
    if material.get('meters_per_unit'):
        return float(material['meters_per_unit'])
    values = re.findall(r'\((\d+(?:\.\d+)?)\s*(?:m|mtr|meters?|metres?)(?:\s*/\s*(?:rl|roll|length|len))?\)', material['name'], re.I)
    return float(values[0]) if len(values) == 1 and float(values[0]) > 0 else None


def apply_wire_choice(rows, materials, material_id, *, meters_per_unit=None, price_per_meter=None):
    matches = [m for m in wire_choices(materials) if m['id'] == material_id]
    if material_id is not None and len(matches) != 1:
        raise ValueError('Choose an active wire/cable product.')
    if meters_per_unit is not None and (not math.isfinite(meters_per_unit) or not 0 < meters_per_unit <= 100000):
        raise ValueError('Invalid wire purchase length.')
    if matches and matches[0]['unit'] == 'meter' and meters_per_unit not in (None, 1):
        raise ValueError('A metre-priced wire already uses one metre per unit.')
    if price_per_meter is not None and (not math.isfinite(price_per_meter) or not 0 <= price_per_meter <= 1_000_000_000):
        raise ValueError('Invalid custom wire price.')
    if material_id is None and price_per_meter is None:
        raise ValueError('Choose a wire product or enter a custom wire price.')
    factor = meters_per_unit if meters_per_unit is not None else wire_unit_length(matches[0]) if matches else None
    # Draft route-length pricing, not an extra surcharge or conductor takeoff.
    additions = []
    for row in rows:
        if row['kind'] == 'path' and (row.get('canonical') or row.get('origin') in ('observed', 'generated', 'manual', 'mixed')):
            if row.get('paired_path_component') and row.get('material_kind') != 'wire':
                continue
            value = dict(row, name=row['name'] if row.get('paired_path_component') else 'Wire/cable — ' + row['name'],
                preferred_material_id=material_id, material_kind='wire',
                wire_meters_per_unit=factor, custom_wire_price_per_meter=price_per_meter,
                unit='source pixel' if row['unit'] == 'source pixel' else 'meter',
                basis=row['basis'] + ' Draft cable route length; no extra allowance added. '
                      'Not conductor purchase quantity; gauge/count remain unspecified.'
                      + (f' Purchase price divided by explicit {factor} metres per unit.' if factor else ' Enter metres per purchase unit for roll pricing.'))
            if row.get('paired_path_component'):
                row.update(value)
            else:
                additions.append(value)
    rows.extend(additions)


def _wire_vertical(wire, symbols, scale, floor_elevation, service_height, automatic, seen, *, issues=None):
    vertical, missing, assumed = 0, [], bool(wire.get('connection_height_assumed'))
    for attachment in wire.get('device_attachments', []):
        symbol = symbols.get(attachment['symbol_id'])
        if symbol is None:
            missing.append('attached device unavailable')
            continue
        if re.search(r'home.?run|circuit.*notation',symbol.get('class_name') or symbol.get('name') or '',re.I):
            continue  # A route annotation has no mounting height or vertical drop.
        height, service = connection_height(symbol), wire.get('elevation_meters')
        relative = wire.get('height_above_floor_meters')
        inherited = relative is None and service is None and (wire.get('installation_method') == 'concealed_in_ceiling' if automatic else wire.get('installation_method') != 'concealed_under_floor')
        if inherited:
            relative = service_height
        if relative is None and service is None and wire.get('installation_method')=='concealed_under_floor':
            relative=0
            assumed=True
        required = [('plan scale', scale), ('device mounting height', height)]
        if relative is None:
            required.extend([('floor elevation', floor_elevation), ('wire elevation', service)])
        absent = [name for name, value in required if value is None]
        if wire.get('assignment_state') == 'unresolved':
            absent.append('electrical assignment')
        if absent:
            missing.append(f"{symbol['id']}: save {', '.join(absent)} for the connected drop/rise")
            if issues is not None:
                for kind,needed in [('scale',scale is None),('device-height',height is None),
                        ('wire-height',relative is None and (floor_elevation is None or service is None)),
                        ('wiring',wire.get('assignment_state')=='unresolved')]:
                    if needed:issues.append(dict(kind=kind,path_id=wire['id'],symbol_id=symbol['id'],
                        device_name=symbol.get('class_name') or symbol.get('name') or 'Device'))
            continue
        assumed = assumed or automatic and (inherited or symbol.get('mounting_height_source') in ('ved_default', 'ved_automatic'))
        key = (symbol['id'], attachment.get('terminal_id'), relative if relative is not None else service - floor_elevation)
        if key not in seen:
            vertical += abs(relative - height) if relative is not None else abs(service - (floor_elevation + height))
            seen.add(key)
    return vertical, missing, assumed


def document_takeoff(document, *, scale=None, floor_elevation=None, mounting_defaults=None,service_height_above_floor=None,automatic_heights=False,assume_connections=False):
    """Count unresolved as draft, exclude deletions/notations; measure source paths."""
    if scale is not None and (not math.isfinite(scale) or scale <= 0):
        raise ValueError('Invalid draft scale.')
    if assume_connections:
        from app.services.connection_estimates import apply_connection_estimates
        prepared=apply_connection_estimates(document,ceiling_height=service_height_above_floor if service_height_above_floor is not None else 3)
        arguments=dict(scale=scale,floor_elevation=floor_elevation,mounting_defaults=mounting_defaults,
            service_height_above_floor=service_height_above_floor,automatic_heights=automatic_heights)
        return document_takeoff(prepared,**arguments)
    groups, seen = {}, set()
    for symbol in document.get('symbols', []):
        if symbol['id'] in seen:
            raise ValueError('Duplicate draft symbol identity.')
        seen.add(symbol['id'])
        name = symbol.get('class_name') or 'Unclassified device'
        if symbol.get('disposition') == 'rejected' or re.search(r'home.?run|circuit.*notation|raceway conduit', name, re.I):
            continue
        custom_price = symbol.get('custom_unit_price')
        key = (symbol.get('class_id'), name, custom_price)
        row = groups.setdefault(key, dict(kind='device', name=name, class_id=key[0],
            quantity=0, unit='piece', symbol_ids=[], custom_unit_price=custom_price,
            basis='One unit per active symbol; draft detections are not verified.'))
        row['quantity'] += 1
        row['symbol_ids'].append(symbol['id'])
    rows = list(groups.values())
    symbols = {s['id']: resolved_mounting(s,defaults=mounting_defaults) for s in document.get('symbols', []) if s.get('disposition') != 'rejected'}
    for group in takeoff_path_groups(document):
        drops = set()  # Only this explicitly connected physical group shares drops.
        wire = group[0]
        length = unique_paths_length([w['points'] for w in group])
        if not math.isfinite(length) or length <= 0:
            raise ValueError('Invalid draft path length.')
        unassigned = any(w.get('assignment_state')=='unresolved' for w in group)
        measured = scale is not None and not unassigned
        vertical, missing, height_assumed = 0, [], False
        path_measurements,measurement_issues = [],[]
        for member in group:
            value, absent, assumed = _wire_vertical(member, symbols, scale, floor_elevation, service_height_above_floor, automatic_heights, drops,issues=measurement_issues)
            vertical += value; missing.extend(absent); height_assumed = height_assumed or assumed
            own_vertical, own_missing, _ = _wire_vertical(member, symbols, scale, floor_elevation, service_height_above_floor, automatic_heights, set())
            own_horizontal = unique_paths_length([member['points']]) / scale if measured else None
            path_measurements.append(dict(id=member['id'], horizontal_meters=own_horizontal,
                vertical_meters=own_vertical if measured else None,
                total_meters=round(own_horizontal + own_vertical, 4) if measured else None,
                incomplete=bool(own_missing or member.get('completeness') != 'complete')))
        horizontal = length / scale if measured else None
        quantity = Decimal(str(horizontal + vertical if measured else length)).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
        rows.append(dict(kind='path', name='Wiring network — conflicting material mappings' if wire.get('takeoff_material_conflict') else wire.get('wiring_legend_name') or 'Wiring path — type not specified',
            connected_layout_categories=sorted({category for member in group for attachment in member.get('device_attachments',[]) if (category:=route_device_layout(symbols.get(attachment['symbol_id'],{}).get('class_name','')))}),
            material_conflict=bool(wire.get('takeoff_material_conflict')),
            electrical_assignment_required=unassigned,
            unresolved_path_ids=[w['id'] for w in group if w.get('assignment_state')=='unresolved'],
            path_id=wire['id'], path_ids=[w['id'] for w in group], circuit_id=wire.get('circuit_id'),
            path_measurements=path_measurements,
            installation_method=wire.get('installation_method', 'unknown'), origin=wire['origin'],
            quantity=quantity, unit='meter' if measured else 'source pixel',
            horizontal_meters=horizontal, vertical_meters=vertical if measured else None,
            conductor_count=wire.get('conductor_count'),
            height_assumed=height_assumed,estimated=height_assumed or any(w.get('connection_assumed') for w in group),
            connection_assumed=any(w.get('connection_assumed') for w in group),
            trace_incomplete=any((w.get('completeness')!='complete' or w.get('source_evidence_required')) and not w.get('connection_assumed') for w in group),
            missing_vertical_inputs=missing,measurement_issues=measurement_issues,
            basis=('Geometric alternative: electrical assignment and service level unresolved. Source pixels only; excluded from measured/purchase takeoff. ' if unassigned else '')+'Unique collinear centerline spans within this explicit junction-connected network and material/installation group / source pixels per meter + attached device drops/rises from saved absolute wire elevation minus (floor elevation + device mounting height). Separate or merely same-named circuits are not merged. Shared device drops at the same service elevation counted once. No inferred conductors, waste or display offsets.'
                + (' INCOMPLETE: unmeasured drops/rises excluded.' if missing else '')))
    return rows


def name_draft_symbols(document, candidate, legends):
    """Use exact catalog identities for planning, never persist a review mapping."""
    predicted = {s.id:s for s in candidate.payload.symbols.items}
    for symbol in document['symbols']:
        legend = legends.get(symbol.get('symbol_legend_id'))
        prediction = predicted.get(symbol['id'])
        training = (prediction.training_legend if prediction and
            candidate.provenance.model_release_id == 'development_multiclass56_yolo' else None)
        # A model index is NOT a database primary key. Drawing-specific identity
        # and the complete legend description must both match, without fuzzing.
        if not legend and not symbol.get('symbol_legend_id') and prediction:
            matches = [l for l in legends.values() if l.class_id == prediction.catalog_class_id] if prediction.catalog_class_id else []
            if not matches and training:
                name = f'{training.name} [{training.legend_entry}]'
                matches = [l for l in legends.values() if l.name == name]
            if not matches and prediction.observed_label:
                matches = [l for l in legends.values() if material_key(l.name)==material_key(prediction.observed_label)]
            legend = matches[0] if len(matches) == 1 else None
        name = legend.name if legend else training.name if training else prediction.observed_label if prediction else None
        symbol.update(class_id=legend.class_id if legend else None, class_name=name)


def validate_preview(session, user, floor_plan_id, processing_job_id, payload):
    """Validate an ephemeral canvas snapshot without writing a review or approval."""
    from app.services.demo_interpretation_service import _authorized_run
    if floor_plan_id is None or processing_job_id is None or payload.review_complete or payload.approved_for_layout or payload.dataset_approval:
        raise ValueError('A canvas preview requires one analysis and cannot grant approval.')
    run = _authorized_run(session, current_user=user, floor_plan_id=floor_plan_id,
                          processing_job_id=processing_job_id, write=False)
    if payload.candidate_run_id != run.candidate_run_id:
        raise ValueError('Canvas source does not match the analysis.')
    plane = _candidate(run).payload.source_plane
    for items in (payload.walls, payload.rooms, payload.symbols, [*payload.observed_wiring, *payload.generated_wiring]):
        if len({item.id for item in items}) != len(items):
            raise ValueError('Duplicate canvas identity.')
    symbols = {symbol.id:symbol for symbol in payload.symbols if symbol.disposition != 'rejected'}
    points = [s.center for s in payload.symbols]
    points += [p for wall in payload.walls for p in (wall.start,wall.end)]
    points += [p for room in payload.rooms for p in room.boundary]
    for wire in [*payload.observed_wiring,*payload.generated_wiring]:
        points.extend(wire.points)
        if wire.disposition == 'rejected':
            continue
        for attachment in wire.device_attachments:
            target = symbols.get(attachment.symbol_id)
            if target is None or wire.points[attachment.point_index] != target.center:
                raise ValueError('Invalid canvas connection.')
    if any(p.x > plane.width_pixels or p.y > plane.height_pixels for p in points):
        raise ValueError('Canvas geometry leaves its source page.')


def price_rows(rows, materials, *, canvas_preview=False, device_defaults=True):
    """Exact identities first, then explicitly configured compatible device defaults."""
    index = {}
    for material in materials:
        index.setdefault(material_key(material['name']), []).append(material)
    totals = {}
    for row in rows:
        row.update(material_id=None, material_name=None, unit_price=None, currency=None, line_total=None,
                   price_revision_id=None, price_source=None, project_price_version_id=None,
                   project_price_row_id=None, pricing_state='material_not_found')
        # Price only known lengths. Missing drops remain explicit and are not
        # silently counted as zero or presented as a complete estimate.
        matches = [m for m in materials if m['id'] == row['preferred_material_id']] if row.get('preferred_material_id') else index.get(material_key(row['name']), [])
        if not matches and device_defaults:
            from app.services.material_assembly_service import choose_default
            default=choose_default(row,materials)
            if default:
                matches=[default]
                row.update(assembly_id=default['id'],assembly=default['assembly'],default_brand_used=True)
                if default['assembly'].get('assumed'): row['estimated']=True
                if default['assembly'].get('scope_complete') is False: row['assembly_scope_incomplete']=True
                row['basis'] += ' Admin-configured device assembly for unspecified brand. '+default['assembly']['scope']+' Shipping excluded.'
        if len(matches) == 1:
            row.update(material_id=matches[0]['id'], material_name=matches[0]['name'])
        factor = row.get('wire_meters_per_unit') if row.get('material_kind') == 'wire' else row.get('purchase_meters_per_unit')
        if row['kind'] == 'path' and row['unit'] == 'meter' and len(matches) == 1 and factor:
            material = dict(matches[0])
            material.update(unit='meter',unit_price=Decimal(str(material['unit_price'])) / Decimal(str(factor))
                if material['unit_price'] is not None else None)
            matches = [material]
        if row.get('electrical_assignment_required'):
            row['pricing_state']='electrical_assignment_required'
        elif row.get('material_conflict'):
            row['pricing_state'] = 'network_material_review_required'
        elif row['kind'] == 'device' and row.get('class_id') is None:
            row['pricing_state'] = 'classification_required'
        elif row['unit'] == 'source pixel':
            row['pricing_state'] = 'scale_required'
        elif len(matches) > 1:
            row['pricing_state'] = 'ambiguous_material'
        elif len(matches) == 1:
            material = matches[0]
            row.update(material_id=material['id'], material_name=material['name'],
                price_source=material.get('price_source', 'catalog'),
                project_price_version_id=material.get('project_price_version_id'),
                project_price_row_id=material.get('project_price_row_id'))
            if material['unit'] != row['unit'] and not (row['unit']=='piece' and material['unit']=='unit'):
                row['pricing_state'] = 'purchase_unit_required'
            elif material['unit_price'] is None:
                row['pricing_state'] = material.get('price_unavailable_reason') or 'missing_price'
            else:
                row.update(pricing_state='priced', unit_price=material['unit_price'], currency=material['currency'],
                           price_revision_id=material['price_revision_id'])
                row['line_total'] = Decimal(str(row['quantity'])) * Decimal(str(material['unit_price']))
                totals[material['currency']] = totals.get(material['currency'], Decimal(0)) + row['line_total']
        custom = row.get('custom_unit_price') if row['kind'] == 'device' else row.get('custom_wire_price_per_meter') if row.get('material_kind') == 'wire' and row['unit'] == 'meter' else None
        if custom is not None and not row.get('material_conflict'):
            amount = Decimal(str(custom))
            if not amount.is_finite() or not 0 <= amount <= 1_000_000_000:
                raise ValueError('Invalid custom device price.')
            amount = amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            if row['line_total'] is not None:
                totals[row['currency']] -= row['line_total']
            row.update(pricing_state='custom_priced', unit_price=amount, currency='PHP',
                       price_revision_id=None, price_source='custom', project_price_version_id=None,
                       project_price_row_id=None,
                       line_total=Decimal(str(row['quantity'])) * amount,
                       basis=row['basis'] + ((' User-entered PHP price per device in this unsaved canvas preview.' if canvas_preview else ' User-entered PHP price per device, saved in draft review.') if row['kind'] == 'device' else ' User-entered PHP price per wire metre for this draft calculation.') + ' Not an Admin catalog price.')
            totals['PHP'] = totals.get('PHP', Decimal(0)) + row['line_total']
        if row.get('missing_vertical_inputs') and row['line_total'] is not None:
            row['pricing_state'] = 'partial_measurement_priced'
    return dict(items=rows, priced_subtotals=totals, unpriced_items=sum(r['line_total'] is None for r in rows),
                basis=[
                    'Devices: count active canvas symbols, including unsaved edits; no review or approval is written.' if canvas_preview else 'Devices: count active saved symbols, including unresolved draft detections; exclude removed items and circuit notations.',
                    'Paths: unique centerline spans within explicit junction-connected material/installation groups. Independent paths remain separate. Saved calibration takes precedence; otherwise a scaled PDF uses physical source-page dimensions and the drawing ratio. Standalone images require a known distance. Display paper and 3D spacing do not change lengths.',
                    'Costs: quantity × current database unit price imported by Admin from Excel, unless explicitly overridden by a saved draft device price or calculator-only wire PHP/metre price. Catalog prices are unchanged.',
                    'Attached drops/rises use saved elevations only. Missing drop measurements are flagged and excluded; illustrative 3D offsets, cable gauge, conductor count and allowances are not inferred. Subtotals exclude unpriced items.',
                    'Read-only planning BOM; no per-item confirmation, layout approval or training approval is created. Saved estimate prices remain fixed.'
                ])


def saved_circuit_takeoff(session, user, project_id, rows, materials, *, scope_floors=None):
    """Reuse saved explicit purchase mappings only for the SAME current route."""
    from app.repositories.estimate_repository import list_estimates, source
    from app.services.material_quantity_service import retrieve_route_material_lengths
    records = list_estimates(session, project_id)
    if not records:
        return
    snapshot = source(session, records[0].id)
    if not snapshot:
        return
    configuration = snapshot.snapshot.get('configuration', {})
    count = configuration.get('conductor_count')
    if type(count) is not int or count < 1:
        return
    try:
        measured = retrieve_route_material_lengths(session, current_user=user, project_id=project_id, conductor_count=count)
    except ValueError:
        return
    if measured['route_version_id'] != snapshot.snapshot.get('route_version_id'):
        return
    bindings = {r['class_id']:r for r in configuration.get('components', [])}
    catalog_by_id = {m['id']:m for m in materials}
    for row in rows:
        binding = bindings.get(row.get('class_id'))
        if row.get('canonical') and row.get('floor_id') in {int(k) for k in measured['layout_versions']} and binding and binding['material_id'] in catalog_by_id:
            row.update(preferred_material_id=binding['material_id'],
                quantity=Decimal(str(row['quantity']))*Decimal(str(binding['units_per_symbol'])),
                unit=catalog_by_id[binding['material_id']]['unit'],
                basis='Canonical device count × saved material units per symbol for the current route.')
    if scope_floors is not None and not {int(k) for k in measured['layout_versions']} <= scope_floors:
        return True  # Aggregate multi-floor quantities cannot be allocated by guess.
    for kind, length in [('conduit', measured['lengths'].conduit_meters), ('wire', measured['lengths'].wire_meters)]:
        identity = configuration.get(f'{kind}_material_id')
        material = catalog_by_id.get(identity)
        factor = configuration.get(f'{kind}_meters_per_unit')
        if material and length is not None and (material['unit']=='meter' or factor):
            quantity=(Decimal(str(length))/Decimal(str(factor or 1))).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
            rows.append(dict(kind='path', name=material['name'], preferred_material_id=identity,
                quantity=quantity, unit=material['unit'], material_kind=kind,
                saved_route_version_id=measured['route_version_id'],
                floor_id=int(next(iter(measured['layout_versions']))) if len(measured['layout_versions']) == 1 else None,
                basis=f'Saved route #{measured["route_version_id"]}: {length} {kind} meters / {factor or 1} meters per purchase unit. '
                      f'Saved conductor count {count}; no added allowance.'))
    return True


def planning_bom(session, user, project_id, *, components, layouts, floor_plan_id=None, processing_job_id=None,
                 conduit_material_id=None, wire_material_id=None, paper_size=None,
                 custom_width_mm=None, custom_height_mm=None, wire_meters_per_unit=None, wire_price_per_meter=None,
                 conduit_price_per_meter=None, scale_denominator=None,
                 draft_preview=None, device_materials=None, purchase_pricing=None):
    dimensions = paper_dimensions(paper_size, custom_width_mm, custom_height_mm) if paper_size else None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    materials = []
    for material in catalog.catalog(session):
        if not material.is_active:
            continue
        price = prices.latest_price(session, material.id, at=now)
        usable = price is not None and price.unit == material.unit
        materials.append(dict(id=material.id, code=material.code, name=material.name, unit=material.unit, category=material.category,
            unit_price=price.unit_price if usable else None, currency=price.currency if usable else None,
            price_revision_id=price.id if usable else None))
    from app.services.project_pricing_service import current_catalog_prices
    from app.services.material_assembly_service import annotate_catalog
    materials=annotate_catalog(session,materials)
    approved_materials=[dict(m) for m in materials]
    from app.services.application_defaults_service import effective as shared_defaults
    from app.services.wiring_material_pairing import pair_rows, purchase_quantities, purchase_prices,fill_planning_conductor_counts
    defaults=shared_defaults(session)
    pair_rules=defaults['wire_conduit_pairs']
    from app.services.layout_materials import project_layout,default_wire,wire_allowed,device_allowed,device_layout,layout_values
    project_layout_type=project_layout(session,project_id)
    from app.repositories.item_price_repository import current as current_choices
    from app.services.material_selection_service import resolve as resolve_choices
    saved_choices=current_choices(session,project_id)
    choice_document=saved_choices.document if saved_choices else {}
    explicit={k:v for k,v in dict(wire=str(wire_material_id) if wire_material_id else None,
        conduit=str(conduit_material_id) if conduit_material_id else None,wireMetersPerUnit=wire_meters_per_unit,
        wirePricePerMeter=wire_price_per_meter,deviceMaterials=device_materials,purchasePricing=purchase_pricing).items() if v is not None}
    def context_for(plan_id):
        value={**resolve_choices(choice_document,plan_id),**explicit}
        from app.services.plan_material_setup import plan_layout
        value['layoutType']=plan_layout(session,plan_id,choice_document) or value.get('layoutType') or project_layout_type
        selected=next((m for m in approved_materials if str(m['id'])==str(value.get('wire'))),None)
        if value['layoutType'] and (not selected or not wire_allowed(selected,value['layoutType'])):
            candidate=default_wire(defaults,value['layoutType'])
            available=next((m for m in approved_materials if m['id']==candidate and wire_allowed(m,value['layoutType'])),None)
            value.update(wire=available['id'] if available else None,conduit=None,purchasePricing={},wireMetersPerUnit=None,wirePricePerMeter=None)
            if available:
                from app.services.plan_material_setup import snapshot
                value['automaticDefaults']=snapshot(session,value['layoutType'])['automaticDefaults']
        return dict(value,wire=int(value['wire']) if value.get('wire') else None,
            conduit=int(value['conduit']) if value.get('conduit') else None)
    effective_choice=context_for(floor_plan_id)
    wire_material_id=effective_choice['wire']
    conduit_material_id=effective_choice['conduit']
    for material in approved_materials:
        rule=next((p for p in pair_rules if p['wire_material_id']==material['id'] or p['conduit_material_id']==material['id']),None)
        if rule:
            material['meters_per_unit']=rule['wire_meters_per_unit'] if rule['wire_material_id']==material['id'] else rule['conduit_meters_per_unit']
    materials, project_pricing = current_catalog_prices(session, user, project_id, materials)
    # Client prices take priority, but absent client rows do not hide VED products.
    approved_by_id={m['id']:m for m in approved_materials}
    materials=[dict(approved_by_id[m['id']],price_source='catalog')
        if m.get('price_unavailable_reason')=='missing_project_material_price' else m for m in materials]
    def scoped_catalog(choice):
        automatic=(choice.get('automaticDefaults') or {}).get('wire_material_id')==choice['wire']
        explicit_wire=None if automatic else choice['wire']
        return [approved_by_id[m['id']] if m['id'] in (explicit_wire,choice['conduit']) else m for m in materials]
    eligible_layouts = [] if draft_preview is not None else [l for l in layouts if floor_plan_id is None or l['floor_plan_id'] == floor_plan_id]
    verified_floors = {l['floor_id'] for l in eligible_layouts}
    rows = [dict(kind='device', name=r['name'], class_id=r['class_id'], quantity=r['quantity'], unit='piece',
        floor_id=r['floor_id'], floor_plan_id=next(l['floor_plan_id'] for l in eligible_layouts if l['floor_id'] == r['floor_id']),
        symbol_ids=r['symbol_ids'], canonical=True, basis='Current saved canonical layout; one unit per symbol.')
        for r in components if r['floor_id'] in verified_floors]
    from app.geometry.canonical import canonical_geometry_from_dict
    from app.geometry.canonical_takeoff import canonical_path_rows
    from app.models import LayoutVersion
    from app.services.canonical_extension_storage import retrieve_canonical_extension
    for layout in eligible_layouts:
        saved = session.get(LayoutVersion, layout['layout_version_id'])
        geometry = canonical_geometry_from_dict(saved.geometry_document)
        extension = retrieve_canonical_extension(saved.id, geometry)
        rows.extend(dict(row,floor_id=layout['floor_id'],floor_plan_id=layout['floor_plan_id'],canonical=True)
                    for row in canonical_path_rows(geometry, extension))
    sources = [dict(floor_id=l['floor_id'], floor_plan_id=l['floor_plan_id'], layout_version_id=l['layout_version_id'], state='canonical')
               for l in eligible_layouts]
    # Latest successful candidate for EACH source page, not one arbitrary PDF page.
    latest = select(func.max(FloorPlanInterpretationRun.id)).group_by(FloorPlanInterpretationRun.floor_plan_page_id)
    query = (select(FloorPlanInterpretationRun, ProjectFloor.id, FloorPlan.original_filename)
        .join(FloorPlan, FloorPlan.id == FloorPlanInterpretationRun.floor_plan_id)
        .join(ProjectFloor, ProjectFloor.id == FloorPlan.project_floor_id)
        .where(ProjectFloor.project_id == project_id, active_floor_plan())
        .order_by(FloorPlanInterpretationRun.id))
    query = query.where(FloorPlanInterpretationRun.processing_job_id == processing_job_id) if processing_job_id is not None else query.where(FloorPlanInterpretationRun.id.in_(latest))
    if floor_plan_id is not None:
        query = query.where(FloorPlan.id == floor_plan_id)
    if draft_preview is not None:
        query = query.where(FloorPlanInterpretationRun.candidate_run_id == draft_preview.candidate_run_id)
    runs = session.execute(query).all()
    scales = latest_scales(session, [r.floor_plan_page_id for r,_,_ in runs])
    legends = {l.id:l for l in session.scalars(select(SymbolLegend).where(SymbolLegend.is_active.is_(True)))}
    missing_inputs = []
    for run, floor_id, filename in runs:
        if floor_id in verified_floors:
            continue
        candidate = _candidate(run)
        review = find_latest_review(session, interpretation_run_id=run.id)
        document = draft_preview.model_dump(mode='json') if draft_preview is not None else _review_document(review) if review else {}
        if not review and draft_preview is None:
            previous = find_latest_previous_review(session, run=run)
            if previous:
                document = inherit_review_draft(candidate, _candidate(previous[0]), _review_document(previous[1]))
        if 'symbols' not in document:
            document['symbols'] = [dict(id=s.id, disposition='unresolved', symbol_legend_id=None)
                                   for s in candidate.payload.symbols.items]
        name_draft_symbols(document, candidate, legends)
        if draft_preview is None:
            document = annotate_wiring(session, candidate, document, drawing_name=filename)
            document = connect_touching_endpoints(candidate, document)
            # Source contact/corner adaptation establishes shared route context.
            # Resolve its automatic placement again, as the workspace reader
            # does, so short solid leads do not become a separate ceiling run.
            document = annotate_wiring(session, candidate, document, drawing_name=filename)
            document = connect_touching_endpoints(candidate, document)
        scale = scales.get(run.floor_plan_page_id)
        plane = candidate.payload.source_plane
        from app.services.draft_scale_service import source_scale
        metric = source_scale(session, run, plane, scale,
            multiple_views=any(w.code=='separate_source_views' for w in candidate.payload.warnings),
            overrides=dict(paper_size=paper_size,custom_width_mm=custom_width_mm,
                custom_height_mm=custom_height_mm,scale_denominator=scale_denominator))
        ppm, scale_basis = metric['pixels_per_meter'], metric['scale_basis']
        if ppm is None and paper_size:
            missing_inputs.append(f'Plan {run.floor_plan_id}: paper metadata {paper_size} '
                f'{dimensions[0]} × {dimensions[1]} mm does not establish image scale. '
                'Calibrate a known real-world dimension; paths remain source pixels until then.')
        elevation = latest_elevation(session, floor_id)
        from app.services.application_defaults_service import mounting_defaults
        items = document_takeoff(document, scale=ppm, mounting_defaults={**mounting_defaults(session),**metric.get('mounting_defaults',{})},
                                service_height_above_floor=metric.get('service_height_above_floor_meters'),automatic_heights=metric.get('height_mode')=='automatic',floor_elevation=float(elevation.elevation_meters)
                                  if elevation and elevation.elevation_meters is not None else None,
                                  assume_connections=bool(context_for(run.floor_plan_id).get('assumeConnections')))
        for item in items:
            if item['kind'] == 'path':
                item.update(scale_basis=scale_basis, scale_approved=metric['scale_approved'],measurement_state=metric['measurement_state'],estimated=metric['estimated'] or item.get('height_assumed',False))
        missing_drops = {note for item in items for note in item.get('missing_vertical_inputs', [])}
        if missing_drops:
            missing_inputs.append(f'Plan {run.floor_plan_id}: {len(missing_drops)} attached devices have unmeasured drops/rises. '
                'Subtotal excludes these lengths. Save floor elevation, wire elevation and device mounting heights; a scale is required.')
        rows.extend(dict(row, floor_id=floor_id, floor_plan_id=run.floor_plan_id, page_id=run.floor_plan_page_id,
            candidate_run_id=run.candidate_run_id) for row in items)
        sources.append(dict(floor_id=floor_id, floor_plan_id=run.floor_plan_id, page_id=run.floor_plan_page_id,
            processing_job_id=run.processing_job_id,candidate_run_id=run.candidate_run_id, review_revision=review.revision_number if review else None,
            state='canvas_preview' if draft_preview is not None else 'saved_draft' if review else 'detected_draft', pixels_per_meter=ppm,
            scale_revision_id=scale.id if scale and scale_basis in ('measured_page', 'paper_ruler_draft') else None,
            scale_basis=scale_basis, assumed_paper_size=metric.get('paper_size'),
            custom_width_mm=metric.get('custom_width_mm'), custom_height_mm=metric.get('custom_height_mm'),
            scale_denominator=metric.get('scale_denominator'), scale_approved=metric['scale_approved'],
            source_width_mm=metric.get('source_width_mm'),source_height_mm=metric.get('source_height_mm'),
            display_sheet=metric.get('display_sheet'),
            measurement_state=metric['measurement_state'],estimated=metric['estimated'],
            scale_reason=metric.get('scale_reason')))
    reused = saved_circuit_takeoff(session, user, project_id, rows, materials,
        scope_floors=verified_floors if floor_plan_id is not None else None) if draft_preview is None else False
    if not reused:
        missing_inputs.append('Wire purchasing quantities require saved circuit specifications for a current measured project route; missing or stale specifications are not assumed.')
    from app.services.wiring_bom_components import paired_wiring_components
    rows = paired_wiring_components(rows, materials)
    scopes={plan_id:context_for(plan_id) for plan_id in {r.get('floor_plan_id') for r in rows}}
    planning_counts={plan_id:(choice.get('automaticDefaults') or {}).get('conductor_count',defaults['planning_conductor_count']) for plan_id,choice in scopes.items()}
    excluded_devices=sum(r['kind']=='device' and not device_allowed(r['name'],scopes[r.get('floor_plan_id')].get('layoutType')) for r in rows)
    rows=[r for r in rows if (device_allowed(r['name'],scopes[r.get('floor_plan_id')].get('layoutType')) if r['kind']=='device' else
        not scopes[r.get('floor_plan_id')].get('layoutType') or not r.get('connected_layout_categories') or bool(set(layout_values(scopes[r.get('floor_plan_id')]['layoutType'])) & set(r['connected_layout_categories'])))]
    for row in rows:
        choice=scopes[row.get('floor_plan_id')]
        connected=row.get('connected_layout_categories') or []
        inferred=device_layout(row['name']) if row['kind']=='device' else connected[0] if len(connected)==1 else None
        selected_types=layout_values(choice.get('layoutType'))
        row['layout_category']=(selected_types[0] if len(selected_types)==1 else inferred if inferred in selected_types or not selected_types else None)
        if row['kind']=='path' and row['layout_category'] is None and connected and set(connected)<={'lighting','power'}:
            row['layout_category']='power' if 'power' in selected_types else 'lighting' if 'lighting' in selected_types else None
        if row.get('material_kind')=='wire' and row.get('conductor_count') is None and choice.get('conductorCount'):
            row['conductor_count']=choice['conductorCount']
    from app.services.workspace_products import split_devices,apply_network_choices
    rows=split_devices(rows,scopes)
    scope_rows={plan_id:[r for r in rows if r.get('floor_plan_id')==plan_id] for plan_id in scopes}
    result=price_rows([],materials,canvas_preview=draft_preview is not None,device_defaults=False)
    for plan_id,items in scope_rows.items():
        choice=scopes[plan_id]
        from app.services.plan_material_setup import apply_layout_wires
        apply_layout_wires(items,choice,approved_materials,defaults)
        if choice['wire'] is not None or choice.get('wirePricePerMeter') is not None:
            apply_wire_choice(items,approved_materials,choice['wire'],meters_per_unit=choice.get('wireMetersPerUnit'),price_per_meter=choice.get('wirePricePerMeter'))
        elif choice.get('wireMetersPerUnit') is not None:
            raise ValueError('Choose a wire product before entering its purchase length.')
        fill_planning_conductor_counts(items,approved_materials,planning_counts[plan_id],wire_id=choice['wire'])
        pair_rows(items,pair_rules,wire_id=choice['wire'],conduit_id=choice['conduit'],materials=approved_materials)
        result['items'].extend(price_rows(items,scoped_catalog(choice),canvas_preview=draft_preview is not None,device_defaults=False)['items'])
    from app.services.product_compatibility import inch_sizes
    choices = [dict({k: m[k] for k in ('id','code','name','unit','unit_price','currency')},brand=product_brand(m),nominal_inches=min(inch_sizes(m['name']),default=None),meters_per_unit=wire_unit_length(m) or (3 if m['unit']=='length' else None))
        for m in sorted(conduit_choices(approved_materials),key=lambda m:(min(inch_sizes(m['name']),default=1000),product_brand(m) or '',m['name']))]
    calculator_quotes={}
    for row in result['items']:
        choice=scopes[row.get('floor_plan_id')]
        selected=choice['conduit'] if row.get('material_kind')=='conduit' else choice['wire'] if row.get('material_kind')=='wire' else None
        if selected is not None and row.get('material_id')==selected and row.get('line_total') is not None:
            calculator_quotes[(row.get('floor_plan_id'),row['material_kind'],row['unit'])]={key:row.get(key) for key in (
                'material_id','material_name','unit_price','currency','price_source','price_revision_id')}
    from app.services.item_pricing_service import apply_prices
    result = apply_prices(session, project_id, result, materials)
    # Resolve pairs after client matching as well as explicit product selection.
    for plan_id,choice in scopes.items():
        fill_planning_conductor_counts([r for r in result['items'] if r.get('floor_plan_id')==plan_id],approved_materials,planning_counts[plan_id],wire_id=choice['wire'])
        pair_rows([r for r in result['items'] if r.get('floor_plan_id')==plan_id],pair_rules,
            wire_id=choice['wire'],conduit_id=choice['conduit'],materials=approved_materials)
    for row in result['items']:
        if row.get('material_kind')=='conduit' and row.get('automatic_material_pair'):
            if row.get('material_id')==row['preferred_material_id'] and row.get('price_source') in ('client_upload','manual_override','item_override') and row.get('line_total') is not None:
                continue
            quote=next((m for m in scoped_catalog(scopes[row.get('floor_plan_id')]) if m['id']==row['preferred_material_id']),None)
            if quote:
                factor=row.get('purchase_meters_per_unit') or wire_unit_length(quote)
                row.update(material_id=quote['id'],material_name=quote['name'],purchase_meters_per_unit=factor,price_revision_id=quote.get('price_revision_id'))
                if row['unit']=='meter' and factor and quote['unit_price'] is not None and not row.get('material_conflict') and not row.get('electrical_assignment_required'):
                    rate=Decimal(str(quote['unit_price']))/Decimal(str(factor))
                    row.update(unit_price=rate,currency=quote['currency'],line_total=Decimal(str(row['quantity']))*rate,pricing_state='priced',price_source=quote.get('price_source','catalog'))
    # Uploaded/explicit item prices resolve against their original identity first.
    # Adding a default material must not invalidate an existing client fingerprint.
    for row in result['items']:
        if row['pricing_state'] not in ('material_not_found','missing_price','ambiguous_material') or row.get('item_price_warning'):
            continue
        from app.services.material_assembly_service import choose_default
        default=choose_default(row,materials)
        if default and default['unit_price'] is not None:
            row.update(material_id=default['id'],material_name=default['name'],unit_price=default['unit_price'],
                currency=default['currency'],price_revision_id=default['price_revision_id'],price_source='catalog_assembly',
                line_total=Decimal(str(row['quantity']))*default['unit_price'],pricing_state='priced',
                assembly_id=default['id'],assembly=default['assembly'],default_brand_used=True)
            if default['assembly'].get('assumed'): row['estimated']=True
            if default['assembly'].get('scope_complete') is False: row['assembly_scope_incomplete']=True
            row['basis']+=' Admin-configured assembly for unspecified brand. '+default['assembly']['scope']+' Shipping excluded.'
    from app.services.draft_device_pricing import apply_choices,groups,selections
    selected_devices=selections(effective_choice.get('deviceMaterials'))
    device_groups=groups(result['items'],approved_materials)
    for plan_id,choice in scopes.items():
        apply_choices([r for r in result['items'] if r.get('floor_plan_id')==plan_id],approved_materials,selections(choice.get('deviceMaterials')))
    for row in result['items']:
        if row.get('workspace_material_id'):
            if any(m['id']==row['workspace_material_id'] for m in approved_materials):
                apply_choices([row],approved_materials,{row['class_id']:row['workspace_material_id']})
            else:row.update(material_id=None,material_name=None,unit_price=None,currency=None,line_total=None,pricing_state='material_not_found')
    # Explicit calculator rates win over uploaded rates, without rewriting any
    # client price list, item assignment or captured historical estimate.
    for row in result['items']:
        selected_quote=calculator_quotes.get((row.get('floor_plan_id'),row.get('material_kind'),row['unit']))
        if selected_quote and not row.get('material_conflict') and not row.get('electrical_assignment_required'):
            row.update(selected_quote,client_product_name=None,client_unit_price=None,
                line_total=Decimal(str(row['quantity']))*Decimal(str(selected_quote['unit_price'])),
                pricing_state='partial_measurement_priced' if row.get('missing_vertical_inputs') else 'priced')
        rate = conduit_price_per_meter if row.get('material_kind')=='conduit' else scopes[row.get('floor_plan_id')].get('wirePricePerMeter') if row.get('material_kind')=='wire' else None
        if rate is not None and row['unit']=='meter' and not row.get('material_conflict') and not row.get('electrical_assignment_required'):
            amount=Decimal(str(rate))
            if not amount.is_finite() or not 0<=amount<=1_000_000_000:
                raise ValueError('Invalid manual path price per metre.')
            row.update(unit_price=amount,currency='PHP',line_total=Decimal(str(row['quantity']))*amount,
                price_source='manual_draft',pricing_state='partial_measurement_priced' if row.get('missing_vertical_inputs') else 'custom_priced')
    result['priced_subtotals']={}
    # A missing scale blocks quantities, not the identity/price of a selected
    # product. Keep its purchase quote separate from the unmeasured line cost.
    for row in result['items']:
        if row.get('kind')!='path' or row.get('line_total') is not None:continue
        choice=scopes[row.get('floor_plan_id')]
        selected=choice['wire'] if row.get('material_kind')=='wire' else row.get('preferred_material_id')
        quote=next((m for m in scoped_catalog(choice) if m['id']==selected),None)
        if quote:
            override=purchase_prices(choice.get('purchasePricing')).get(row.get('material_kind'))
            amount=override.get('price') if override and override['material_id']==selected else None
            row.update(material_id=selected,material_name=quote['name'],catalog_unit_price=amount if amount is not None else quote['unit_price'],
                catalog_price_unit=quote['unit'],catalog_currency='PHP' if amount is not None else quote['currency'],
                client_product_name=None,client_unit_price=None,unit_price=None)
    apply_network_choices(result['items'],scopes,approved_materials,pair_rules,planning_counts=planning_counts)
    from app.services.wiring_bom_components import apply_conductor_quantity
    for row in result['items']:
        if row.get('material_kind')=='wire' and not row.get('saved_route_version_id') and row.get('conductor_count') is None and re.search(r'\b(?:THHN|THW|single[ -]?core|single conductor)\b',row.get('material_name') or '',re.I):
            automatic=scopes[row.get('floor_plan_id')].get('automaticDefaults') or {}
            row.update(conductor_count=automatic.get('conductor_count',defaults['planning_conductor_count']),conductor_count_assumed=True,estimated=True)
        apply_conductor_quantity(row)
    purchase_quantities(result['items'],materials,{},overrides_by_plan={key:purchase_prices(value.get('purchasePricing')) for key,value in scopes.items()},
        catalogs_by_plan={key:{m['id']:m for m in scoped_catalog(value)} for key,value in scopes.items()})
    for row in result['items']:
        if row.get('compatible_pair_missing'):
            row.update(line_total=None,pricing_state='compatible_conduit_required')
    for row in result['items']:
        if row['line_total'] is not None:
            currency=row['currency']
            result['priced_subtotals'][currency]=result['priced_subtotals'].get(currency,Decimal(0))+row['line_total']
    result['unpriced_items']=sum(row['line_total'] is None for row in result['items'])
    if project_pricing:
        result['basis'][2] = ('Costs: latest confirmed client import, version '
            f'{project_pricing["version_number"]}, normalized using reviewed purchase-unit conversions. '
            'Absent client prices use compatible approved catalog prices; explicit draft overrides are retained. '
            'Shared catalog and saved estimate prices are unchanged.')
    # Read-only product identity for presentation. Never affects price selection.
    visual_catalog = {m['id']: m for m in approved_materials}
    for row in result['items']:
        product = visual_catalog.get(row.get('material_id'))
        if product:
            row.update(material_code=product.get('code'), material_category=product.get('category'),
                brand=product_brand(product))
        if product and not row.get('client_price_only') and not row.get('client_product_name'):
            row['product_identity'] = dict(material_id=product['id'], code=product.get('code'),
                brand=product_brand(product),
                device_type=(product.get('assembly') or {}).get('device_type'),
                components=(product.get('assembly') or {}).get('components', []))
    from app.services.project_budget import comparison
    budget=comparison(session,project_id,result['priced_subtotals'],incomplete=bool(result['unpriced_items'] or any(r.get('missing_vertical_inputs') or r.get('trace_incomplete') for r in result['items']))) if floor_plan_id is None else None
    return dict(result,project_id=project_id,budget_comparison=budget, sources=sources, calculated_at=now.isoformat(), project_pricing=project_pricing,
                material_selection=resolve_choices(choice_document,floor_plan_id),material_selection_revision=saved_choices.version_number if saved_choices else 0,
                layout_type=effective_choice.get('layoutType'),excluded_device_groups=excluded_devices,
                default_conductor_count=(effective_choice.get('automaticDefaults') or {}).get('conductor_count',defaults['planning_conductor_count']),
                allowed_symbol_legend_ids=[legend.id for legend in session.scalars(select(SymbolLegend).where(SymbolLegend.is_active.is_(True))) if device_allowed(legend.name,effective_choice.get('layoutType'))],
                conduit_materials=choices, selected_conduit_material_id=conduit_material_id, requested_paper_size=paper_size,
                device_groups=device_groups,selected_device_materials=selected_devices,
                wire_materials=[dict({k: m[k] for k in ('id','code','name','unit','unit_price','currency')},brand=product_brand(m),meters_per_unit=wire_unit_length(m)) for m in wire_choices(approved_materials) if wire_allowed(m,effective_choice.get('layoutType'))],
                wire_conduit_pairs=pair_rules,
                selected_wire_material_id=wire_material_id,
                wire_meters_per_unit=wire_meters_per_unit, wire_price_per_meter=wire_price_per_meter,
                custom_width_mm=custom_width_mm, custom_height_mm=custom_height_mm,
                catalog_materials=len(materials), missing_inputs=missing_inputs,
                scope='plan' if floor_plan_id is not None else 'project')
