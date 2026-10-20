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


def material_key(name):
    # Only presentation normalization, never remove ratings, dimensions or brands.
    name = re.sub(r'\s*\[(?:pdf-[^\]]+|sheet-\d+:L[\w-]+|u:[\w-]+)\]\s*$', '', name or '')
    return ' '.join(re.findall(r'[a-z0-9]+', name.casefold()))


PAPER_MM = {'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594),
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
            and re.search(r'\b(?:pipe|tube)\b|\b(?:flexible|liquid[- ]tight).*conduit\b|^conduit(?:\s*\d|\s*$)', m['name'], re.I)
            and m['unit'] in ('meter', 'length') and m['unit_price'] is not None]


def apply_conduit_choice(rows, materials, material_id):
    """Explicit draft SKU; never equate a purchase stick/length with one metre."""
    matches = [m for m in conduit_choices(materials) if m['id'] == material_id]
    if len(matches) != 1:
        raise ValueError('Choose an active priced conduit material.')
    material = matches[0]
    for row in rows:
        if (row['kind'] == 'path' and row.get('origin') in ('observed', 'generated', 'manual', 'mixed')
                and row['unit'] == 'meter' and re.search(r'\bconduit\b', row['name'], re.I)):
            row.update(preferred_material_id=material_id,
                       basis=row['basis'] + ' Draft material choice; a non-metre purchase unit requires an explicit conversion.')


def wire_choices(materials):
    # Explicit selection only: data cable is never silently mapped to power wire.
    return [m for m in materials if re.search(r'\b(?:wire|wiring|cable|cables)\b', m.get('category') or '', re.I)
            and re.search(r'\b(?:wire|cable)\b', m['name'], re.I)
            and not re.search(r'\b(?:connector|tray|tie|clip|lug|gland|manager)\b', m['name'], re.I)
            and m['unit_price'] is not None]


def wire_unit_length(material):
    if material['unit'] == 'meter':
        return 1
    # Only an explicit purchase-length annotation; never infer from brand/gauge.
    values = re.findall(r'\((\d+(?:\.\d+)?)\s*m\)', material['name'], re.I)
    return float(values[0]) if len(values) == 1 and float(values[0]) > 0 else None


def apply_wire_choice(rows, materials, material_id, *, meters_per_unit=None, price_per_meter=None):
    matches = [m for m in wire_choices(materials) if m['id'] == material_id]
    if material_id is not None and len(matches) != 1:
        raise ValueError('Choose an active priced wire/cable material.')
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
        if row['kind'] == 'path' and row.get('origin') in ('observed', 'generated', 'manual', 'mixed'):
            additions.append(dict(row, name='Wire/cable — ' + row['name'],
                preferred_material_id=material_id, material_kind='wire',
                wire_meters_per_unit=factor, custom_wire_price_per_meter=price_per_meter,
                unit='source pixel' if row['unit'] == 'source pixel' else 'meter',
                basis=row['basis'] + ' Draft cable route length; no extra allowance added. '
                      'Not conductor purchase quantity; gauge/count remain unspecified.'
                      + (f' Purchase price divided by explicit {factor} metres per unit.' if factor else ' Enter metres per purchase unit for roll pricing.')))
    rows.extend(additions)


def document_takeoff(document, *, scale=None, floor_elevation=None):
    """Count unresolved as draft, exclude deletions/notations; measure source paths."""
    if scale is not None and (not math.isfinite(scale) or scale <= 0):
        raise ValueError('Invalid draft scale.')
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
    symbols = {s['id']: s for s in document.get('symbols', []) if s.get('disposition') != 'rejected'}
    for group in takeoff_path_groups(document):
        drops = set()  # Only this explicitly connected physical group shares drops.
        wire = group[0]
        length = unique_paths_length([w['points'] for w in group])
        if not math.isfinite(length) or length <= 0:
            raise ValueError('Invalid draft path length.')
        unassigned = any(w.get('assignment_state')=='unresolved' for w in group)
        measured = scale is not None and not unassigned
        vertical, missing = 0, []
        for attachment in (a for w in group for a in w.get('device_attachments', [])):
            symbol = symbols.get(attachment['symbol_id'])
            if symbol is None:
                missing.append('attached device unavailable')
                continue
            height, service = symbol.get('mounting_height_meters'), wire.get('elevation_meters')
            if not measured or floor_elevation is None or height is None or service is None:
                missing.append(f"{symbol['id']}: scale, floor elevation, wire elevation and device mounting height are required for the drop/rise")
                continue
            key = (symbol['id'], attachment.get('terminal_id'), service)
            if key not in drops:
                vertical += abs(service - (floor_elevation + height))
                drops.add(key)
        horizontal = length / scale if measured else None
        quantity = Decimal(str(horizontal + vertical if measured else length)).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
        rows.append(dict(kind='path', name='Wiring network — conflicting material mappings' if wire.get('takeoff_material_conflict') else wire.get('wiring_legend_name') or 'Wiring path — type not specified',
            material_conflict=bool(wire.get('takeoff_material_conflict')),
            electrical_assignment_required=unassigned,
            path_id=wire['id'], path_ids=[w['id'] for w in group], circuit_id=wire.get('circuit_id'),
            installation_method=wire.get('installation_method', 'unknown'), origin=wire['origin'],
            quantity=quantity, unit='meter' if measured else 'source pixel',
            horizontal_meters=horizontal, vertical_meters=vertical if measured else None,
            missing_vertical_inputs=missing,
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
            legend = matches[0] if len(matches) == 1 else None
        name = legend.name if legend else training.name if training else prediction.observed_label if prediction else None
        symbol.update(class_id=legend.class_id if legend else None, class_name=name)


def price_rows(rows, materials):
    """Only unique exact-name matches; absent/ambiguous units never become zero costs."""
    index = {}
    for material in materials:
        index.setdefault(material_key(material['name']), []).append(material)
    totals = {}
    for row in rows:
        row.update(material_id=None, material_name=None, unit_price=None, currency=None, line_total=None,
                   price_revision_id=None, price_source=None, project_price_version_id=None,
                   project_price_row_id=None, pricing_state='material_not_found')
        # Partial geometry may be displayed, but neither catalog nor custom
        # prices may turn missing measurements into a complete-looking cost.
        if row.get('missing_vertical_inputs'):
            row['pricing_state'] = 'measurement_incomplete'
            continue
        matches = [m for m in materials if m['id'] == row['preferred_material_id']] if row.get('preferred_material_id') else index.get(material_key(row['name']), [])
        if row.get('material_kind') == 'wire' and row['unit'] == 'meter' and len(matches) == 1 and row.get('wire_meters_per_unit'):
            material = dict(matches[0])
            material.update(unit='meter',unit_price=Decimal(str(material['unit_price'])) / Decimal(str(row['wire_meters_per_unit']))
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
                       basis=row['basis'] + (' User-entered PHP price per device, saved in draft review.' if row['kind'] == 'device' else ' User-entered PHP price per wire metre for this draft calculation.') + ' Not an Admin catalog price.')
            totals['PHP'] = totals.get('PHP', Decimal(0)) + row['line_total']
    return dict(items=rows, priced_subtotals=totals, unpriced_items=sum(r['line_total'] is None for r in rows),
                basis=[
                    'Devices: count active saved symbols, including unresolved draft detections; exclude removed items and circuit notations.',
                    'Paths: unique centerline spans within explicit junction-connected material/installation groups. Independent paths remain separate. Use a reviewed source calibration; paper size or printed scale alone does not calibrate image pixels. Display-only 3D spacing is excluded.',
                    'Costs: quantity × current database unit price imported by Admin from Excel, unless explicitly overridden by a saved draft device price or calculator-only wire PHP/metre price. Catalog prices are unchanged.',
                    'Attached drops/rises use saved elevations only. Missing drop measurements are flagged and excluded; illustrative 3D offsets, cable gauge, conductor count and allowances are not inferred. Subtotals exclude unpriced items.',
                    'Read-only planning BOM; no per-item confirmation, layout approval or training approval is created. Saved estimate prices remain fixed.'
                ])


def saved_circuit_takeoff(session, user, project_id, rows, materials):
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
        if row.get('canonical') and binding and binding['material_id'] in catalog_by_id:
            row.update(preferred_material_id=binding['material_id'],
                quantity=Decimal(str(row['quantity']))*Decimal(str(binding['units_per_symbol'])),
                unit=catalog_by_id[binding['material_id']]['unit'],
                basis='Canonical device count × saved material units per symbol for the current route.')
    for kind, length in [('conduit', measured['lengths'].conduit_meters), ('wire', measured['lengths'].wire_meters)]:
        identity = configuration.get(f'{kind}_material_id')
        material = catalog_by_id.get(identity)
        factor = configuration.get(f'{kind}_meters_per_unit')
        if material and length is not None and (material['unit']=='meter' or factor):
            quantity=(Decimal(str(length))/Decimal(str(factor or 1))).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
            rows.append(dict(kind='path', name=material['name'], preferred_material_id=identity,
                quantity=quantity, unit=material['unit'], floor_id=None,
                basis=f'Saved route #{measured["route_version_id"]}: {length} {kind} meters / {factor or 1} meters per purchase unit. '
                      f'Saved conductor count {count}; no added allowance.'))
    return True


def planning_bom(session, user, project_id, *, components, layouts, floor_plan_id=None, processing_job_id=None,
                 conduit_material_id=None, wire_material_id=None, paper_size=None,
                 custom_width_mm=None, custom_height_mm=None, wire_meters_per_unit=None, wire_price_per_meter=None):
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
    materials, project_pricing = current_catalog_prices(session, user, project_id, materials)
    eligible_layouts = [l for l in layouts if floor_plan_id is None or l['floor_plan_id'] == floor_plan_id]
    verified_floors = {l['floor_id'] for l in eligible_layouts}
    rows = [dict(kind='device', name=r['name'], class_id=r['class_id'], quantity=r['quantity'], unit='piece',
        floor_id=r['floor_id'], symbol_ids=r['symbol_ids'], canonical=True, basis='Current saved canonical layout; one unit per symbol.')
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
    runs = session.execute(query).all()
    scales = latest_scales(session, [r.floor_plan_page_id for r,_,_ in runs])
    legends = {l.id:l for l in session.scalars(select(SymbolLegend).where(SymbolLegend.is_active.is_(True)))}
    missing_inputs = []
    for run, floor_id, filename in runs:
        if floor_id in verified_floors:
            continue
        candidate = _candidate(run)
        review = find_latest_review(session, interpretation_run_id=run.id)
        document = _review_document(review) if review else {}
        if not review:
            previous = find_latest_previous_review(session, run=run)
            if previous:
                document = inherit_review_draft(candidate, _candidate(previous[0]), _review_document(previous[1]))
        if 'symbols' not in document:
            document['symbols'] = [dict(id=s.id, disposition='unresolved', symbol_legend_id=None)
                                   for s in candidate.payload.symbols.items]
        name_draft_symbols(document, candidate, legends)
        document = annotate_wiring(session, candidate, document, drawing_name=filename)
        document = connect_touching_endpoints(candidate, document)
        scale = scales.get(run.floor_plan_page_id)
        plane = candidate.payload.source_plane
        ppm = float(scale.pixels_per_meter) if scale and scale.pixels_per_meter and (
            scale.reference_width_pixels, scale.reference_height_pixels) == (plane.width_pixels, plane.height_pixels) else None
        scale_basis = 'measured_page' if ppm else 'unresolved'
        if ppm is None and paper_size:
            missing_inputs.append(f'Plan {run.floor_plan_id}: paper metadata {paper_size} '
                f'{dimensions[0]} × {dimensions[1]} mm does not establish image scale. '
                'Calibrate a known real-world dimension; paths remain source pixels until then.')
        elevation = latest_elevation(session, floor_id)
        items = document_takeoff(document, scale=ppm, floor_elevation=float(elevation.elevation_meters)
                                if elevation and elevation.elevation_meters is not None else None)
        missing_drops = {note for item in items for note in item.get('missing_vertical_inputs', [])}
        if missing_drops:
            missing_inputs.append(f'Plan {run.floor_plan_id}: {len(missing_drops)} attached devices have unmeasured drops/rises. '
                'Subtotal excludes these lengths. Save floor elevation, wire elevation and device mounting heights; a scale is required.')
        rows.extend(dict(row, floor_id=floor_id, floor_plan_id=run.floor_plan_id, page_id=run.floor_plan_page_id) for row in items)
        sources.append(dict(floor_id=floor_id, floor_plan_id=run.floor_plan_id, page_id=run.floor_plan_page_id,
            processing_job_id=run.processing_job_id, review_revision=review.revision_number if review else None,
            state='saved_draft' if review else 'detected_draft', pixels_per_meter=ppm,
            scale_revision_id=scale.id if scale and scale_basis == 'measured_page' else None,
            scale_basis=scale_basis, assumed_paper_size=None))
    reused = saved_circuit_takeoff(session, user, project_id, rows, materials) if floor_plan_id is None else False
    if not reused:
        missing_inputs.append('Wire purchasing quantities require saved circuit specifications for a current measured project route; missing or stale specifications are not assumed.')
    if conduit_material_id is not None:
        apply_conduit_choice(rows, materials, conduit_material_id)
    if wire_material_id is not None or wire_price_per_meter is not None:
        apply_wire_choice(rows, materials, wire_material_id, meters_per_unit=wire_meters_per_unit,price_per_meter=wire_price_per_meter)
    elif wire_meters_per_unit is not None:
        raise ValueError('Choose a wire product before entering its purchase length.')
    choices = [{k: m[k] for k in ('id', 'name', 'unit', 'unit_price', 'currency')} for m in conduit_choices(materials)]
    result = price_rows(rows, materials)
    if project_pricing:
        result['basis'][2] = ('Costs: latest confirmed client import, version '
            f'{project_pricing["version_number"]}, normalized using reviewed purchase-unit conversions. '
            'Unmapped materials remain unpriced; explicit draft overrides are retained. '
            'Shared catalog and saved estimate prices are unchanged.')
    return dict(result, sources=sources, calculated_at=now.isoformat(), project_pricing=project_pricing,
                conduit_materials=choices, selected_conduit_material_id=conduit_material_id, requested_paper_size=paper_size,
                wire_materials=[dict({k: m[k] for k in ('id', 'name', 'unit', 'unit_price', 'currency')},meters_per_unit=wire_unit_length(m)) for m in wire_choices(materials)],
                selected_wire_material_id=wire_material_id,
                wire_meters_per_unit=wire_meters_per_unit, wire_price_per_meter=wire_price_per_meter,
                custom_width_mm=custom_width_mm, custom_height_mm=custom_height_mm,
                catalog_materials=len(materials), missing_inputs=missing_inputs,
                scope='plan' if floor_plan_id is not None else 'project')
