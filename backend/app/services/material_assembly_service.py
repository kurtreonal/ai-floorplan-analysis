"""Flat, fully costed device recipes. No shipping, labor, hidden sizing or nested totals."""
from datetime import datetime, timezone
from decimal import Decimal
import logging
import re
from sqlalchemy import select
from app.models import Material, SymbolLegend
from app.models.material_assembly import MaterialAssembly
from app.repositories import material_assembly_repository as repository
from app.repositories import material_catalog_repository as catalog
from app.repositories import material_price_repository as prices
from app.schemas.material_assembly import AssemblyWrite
from app.schemas.material_price import MaterialPriceWrite
from app.services.product_compatibility import specifications_match

logger = logging.getLogger(__name__)


class AssemblyError(ValueError):
    pass


class AssemblyConflict(AssemblyError):
    pass


def _admin(user):
    if getattr(getattr(user,'role',None),'name',None) != 'ADMIN':
        raise PermissionError('Only an Admin can change device assemblies.')



NAME_EXAMPLES={'simplex_outlet': 'Simplex outlet', 'duplex_outlet': 'Duplex outlet', 'switch_1gang': '1-gang switch', 'switch_2gang': '2-gang switch', 'switch_3gang': '3-gang switch', 'switch_3way': '3-way switch', 'data_simplex': 'Single data outlet', 'data_duplex': 'Duplex data outlet', 'cctv': 'CCTV camera', 'light_single': 'Single-tube light', 'light_twin': 'Twin-tube light', 'downlight': 'Downlight', 'troffer': 'Troffer', 'smoke_detector': 'Smoke detector', 'heat_detector': 'Heat detector', 'pull_station': 'Pull station', 'horn_strobe': 'Horn / siren with strobe', 'pull_horn_strobe': 'Pull station with horn and strobe', 'fire_bell': 'Fire alarm bell', 'bell_pull': 'Fire alarm bell with pull station', 'door_chime': 'Door chime', 'push_button': 'Push button', 'magnetic_contact': 'Magnetic contact', 'motion_detector': 'Motion detector', 'keypad': 'Keypad', 'vibration_detector': 'Vibration detector', 'panelboard': 'Panelboard', 'circuit_breaker': 'Circuit breaker', 'fire_panel': 'Fire alarm control panel', 'voice_outlet': 'Telephone / voice outlet', 'utility_box': 'Utility box', 'pull_box': 'Pull box', 'fan_controller': 'Fan control switch'}

def device_type(name):
    text = name.casefold()
    # Technical source suffixes carry no product specification.
    text = re.sub(r'\s*\[(?:pdf-[^\]]+|sheet-\d+:[^\]]+|u:[^\]]+)\]\s*$', '', text)
    if re.search(r'\b(?:circuit|homerun|notation|ceiling outlet|light outlet|fan outlet)\b',text):
        if not re.search(r'\bcircuit breaker\b',text): return None
    for kind,pattern in [
        ('pull_horn_strobe',r'pull station.*(?:horn|strobe|siren)'),
        ('bell_pull',r'fire alarm bell.*pull station'),
        ('smoke_detector',r'\bsmoke detector\b'),('heat_detector',r'\bheat detector\b'),
        ('pull_station',r'\b(?:pull station|manual call point)\b'),
        ('horn_strobe',r'\b(?:horn|siren|sounder).*strobe'),('fire_bell',r'\bfire alarm bell\b'),
        ('door_chime',r'\b(?:bell/chime|doorbell|door chime)\b'),
        ('magnetic_contact',r'\bmagnetic(?: door)? contact\b'),('motion_detector',r'\bmotion detector\b'),
        ('vibration_detector',r'\bvibration detector\b'),('keypad',r'\bkeypad\b'),
        ('push_button',r'\bpush button\b'),('fire_panel',r'\bfire alarm control panel\b'),
        ('panelboard',r'\bpanel\s*board\b'),('circuit_breaker',r'\bcircuit breaker\b'),
        ('utility_box',r'\butility box\b'),('pull_box',r'\bpull box\b'),
        ('fan_controller',r'\bfan control switch\b'),('voice_outlet',r'\b(?:voice|telephone).*outlet\b'),
        ('downlight',r'\bdownlight\b'),('troffer',r'\btroffer\b'),
        ('light_twin',r'\b2\s*[x×].*(?:fluorescent|lamp)|\btwin.*(?:tube|lamp)'),
        ('light_single',r'\b1\s*[x×].*(?:fluorescent|lamp)|\bsingle.*(?:tube|lamp)')]:
        if re.search(pattern,text): return kind
    if re.search(r'\b(?:cctv|surveillance camera)\b',text):
        return 'cctv'
    if re.search(r'\b(?:data|datacom|rj45|lan)\b',text):
        return 'data_duplex' if re.search(r'\b(?:duplex|double|2[ -]*(?:gang|port))\b',text) else 'data_simplex'
    if re.search(r'\bswitch(?:es)?\b',text):
        if re.search(r'\b(?:three|3)[ -]*way\b',text):
            return 'switch_3way'
        if re.search(r'\b(?:two|2)[ -]*gang\b',text):
            return 'switch_2gang'
        if re.search(r'\b(?:three|3)[ -]*gang\b',text):
            return 'switch_3gang'
        if re.search(r'\b(?:one|1)[ -]*gang\b',text):
            return 'switch_1gang'
        return None  # A generic unknown switch may be a dimmer, isolator or three-way.
    if re.search(r'\b(?:outlet|receptacle|socket)\b',text):
        if 'duplex' in text:
            return 'duplex_outlet'
        if re.search(r'\b(?:simplex|single)\b',text):
            return 'simplex_outlet'


def _protected_match(source, offered):
    # Defaults fill a missing brand only, not missing protection or a conflicting system.
    patterns = [r'\b(?:gfci|rcd|weatherproof|waterproof|grounded|ungrounded|addressable|conventional|wired|wireless|standalone)\b',
                r'\b(?:floor[ -]mounted|wall[ -]mounted|surface[ -]mounted|flush[ -]mounted)\b',
                r'\b(?:analog|hdtvi|tvi|ahd|cvi|ip|poe|ptz|dome|bullet|turret)\b',
                r'\b(?:cat\s*[5678][ae]?)\b', r'\b\d+(?:\.\d+)?\s*mp\b',r'\b(?:one|two|three|four|1|2|3|4)[ -]*way\b']
    source = source.casefold().replace('with ground','grounded').replace('with grounding','grounded')
    offered = offered.casefold().replace('with ground','grounded').replace('with grounding','grounded')
    words={'one':'1','two':'2','three':'3','four':'4'}
    source=re.sub(r'\b(one|two|three|four)(?=[ -]*way\b)',lambda m:words[m[0]],source)
    offered=re.sub(r'\b(one|two|three|four)(?=[ -]*way\b)',lambda m:words[m[0]],offered)
    for pattern in patterns:
        required={re.sub(r'[ -]+','',v) for v in re.findall(pattern,source)}
        available={re.sub(r'[ -]+','',v) for v in re.findall(pattern,offered)}
        if not required <= available:
            return False
    # A generic interior receptacle must not silently become a floor or GFCI assembly.
    for special in ['gfci','weatherproof','floor-mounted']:
        if special in offered and special not in source:
            return False
    return specifications_match(source,offered)


def choose_default(row, materials):
    if row.get('kind') != 'device' or row.get('class_id') is None or row.get('preferred_material_id') or row.get('custom_unit_price') is not None:
        return None
    source=row.get('name','')
    kind=device_type(source)
    if kind is None:
        return None
    recipes=[m for m in materials if m.get('assembly',{}).get('device_type')==kind]
    # Recognize explicitly named catalog brands across the material catalog, not a fixed brand list.
    brands={m['assembly']['brand'].casefold() for m in materials if m.get('assembly')}
    brands.update(m.get('code','').split('-')[0].casefold() for m in materials if m.get('code'))
    brands.update(['panasonic','royu','omni','hikvision','dahua','schneider','belden','alantek','commscope'])
    brands-={'unbranded','ved',''}
    explicit=[brand for brand in brands if re.search(r'(?<!\w)'+re.escape(brand)+r'(?!\w)',source,re.I)]
    if not explicit and not any(m['assembly']['is_default'] for m in recipes):
        return None
    candidates=[]
    for m in recipes:
        recipe=m['assembly']
        if explicit and recipe['brand'].casefold() not in explicit:
            continue
        if kind=='cctv' and not recipe['is_default']:
            source_technologies=set(re.findall(r'\b(?:analog|tvi|ahd|cvi|ip|poe)\b',source,re.I))
            if not source_technologies:
                continue
        if _protected_match(source,m['name']+' '+recipe['specifications']):
            candidates.append(m)
    defaults=[m for m in candidates if m['assembly']['is_default']]
    if len(defaults)==1:
        return defaults[0]
    if not explicit:
        preferred={m['assembly']['brand'].casefold() for m in recipes if m['assembly']['is_default']}
        same_brand=[m for m in candidates if m['assembly']['brand'].casefold() in preferred]
        if same_brand:
            candidates=same_brand
    # Never choose cheapest/nearest/first to conceal conflicting specifications.
    return candidates[0] if len(candidates)==1 else None


def quote(session, record, *, lock=False):
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    parts=[];currencies=set();total=Decimal(0)
    for component in sorted(record.document['components'],key=lambda p:p['material_id']):
        material=prices.lock_material(session,component['material_id']) if lock else session.get(Material,component['material_id'])
        price=prices.latest_price(session,component['material_id'],at=now,lock=lock)
        if not material or not material.is_active or material.unit not in ('piece','unit','set') or not price or price.unit!=material.unit:
            return None
        if re.search(r'\b(?:shipping|freight|delivery|labor|labour)\b',material.name+' '+material.category,re.I):
            return None
        quantity=Decimal(component['quantity'])
        total+=price.unit_price*quantity;currencies.add(price.currency)
        parts.append(dict(material_id=material.id,code=material.code,name=material.name,quantity=str(quantity.quantize(Decimal('.0001'))),
            unit=material.unit,unit_price=str(price.unit_price.quantize(Decimal('.0001'))),price_revision_id=price.id,currency=price.currency))
    if len(currencies)!=1 or total>=Decimal('1e12'):
        return None
    return dict(unit_price=str(total.quantize(Decimal('.0001'))),currency=next(iter(currencies)),components=parts)


def refresh(session,user,records):
    from app.services.material_price_service import update_material_price
    for record in records:
        value=quote(session,record,lock=True)
        if value is None:
            raise AssemblyError('Every assembly component must have an active compatible price in one currency. Shipping is excluded.')
        previous=prices.last_revision(session,record.material_id)
        if not previous or (previous.unit_price,previous.currency)!=(Decimal(value['unit_price']),value['currency']):
            previous=update_material_price(session,current_user=user,material_id=record.material_id,
                request=MaterialPriceWrite(unit_price=value['unit_price'],currency=value['currency'],effective_at=datetime.now(timezone.utc)),_assembly_total=True)
        record.price_snapshot={**value,'price_revision_id':previous.id}
    session.flush()


def save(session,user,data,material_id=None,*,commit=True):
    _admin(user)
    if not repository.available(session):
        raise RuntimeError('Device assembly storage needs database administrator setup.')
    records=repository.records(session,lock=True)
    record=next((r for r in records if r.material_id==material_id),None)
    if material_id is not None and record is None:
        raise AssemblyError('Device assembly was not found.')
    if data.expected_revision != (record.revision if record else 0):
        raise AssemblyConflict('Device assembly changed. Reload before saving.')
    if device_type(data.name)!=data.device_type:
        example=NAME_EXAMPLES[data.device_type]
        actual=device_type(data.name)
        detail=f' This name describes {NAME_EXAMPLES[actual].lower()}.' if actual else ' Include the complete device type, not only a short label.'
        hint=' Duplex is an outlet term; choose Duplex outlet if that is what you are adding.' if 'duplex' in data.name.casefold() and data.device_type.startswith('switch_') else ''
        raise AssemblyError(f'Assembly name: selected type is {example}. Rename the assembly to "{example}" with its brand or rating.{detail}{hint}')
    if len(records)>=500 and not record:
        raise AssemblyError('The assembly catalog is limited to 500 recipes.')
    component_ids=[p.material_id for p in data.components]
    if len(set(component_ids))!=len(component_ids):
        raise AssemblyError('List each component once and set its quantity.')
    if set(component_ids)&{r.material_id for r in records}:
        raise AssemblyError('Nested assemblies are not supported. Use original components to avoid double counting.')
    material=session.get(Material,material_id) if record else catalog.by_code(session,data.code,lock=True)
    if not record and material:
        raise AssemblyError('Use a new assembly code; existing material identities are preserved.')
    if record and (material.code!=data.code or material.name!=data.name):
        raise AssemblyError('Existing assembly code and name cannot be renamed; create another assembly to preserve price assignments.')
    if material is None:
        material=catalog.create(session,dict(code=data.code,name=data.name,unit='piece',category='Device assemblies'))
    if not material.is_active or material.unit!='piece':
        raise AssemblyError('Assembly material must be active and priced per piece.')
    document=data.model_dump(mode='json',include={'components','scope','specifications','source_references','assumed','scope_complete'})
    document['specifications']=data.specifications
    if record:
        record.is_default=False
        record.brand=data.brand;record.device_type=data.device_type
        record.document=document;record.revision+=1;record.updated_by_user_id=user.id
    else:
        record=MaterialAssembly(material_id=material.id,brand=data.brand,device_type=data.device_type,
            revision=1,document=document,price_snapshot={},updated_by_user_id=user.id)
        session.add(record)
    if data.is_default:
        for other in records:
            if other.material_id!=material.id and other.device_type==data.device_type and other.is_default:
                other.is_default=False;other.revision+=1;other.updated_by_user_id=user.id
    session.flush()
    record.is_default=data.is_default
    session.flush()
    refresh(session,user,[record])
    from app.services.activity_log import record as log_activity
    log_activity(session,user,'ASSEMBLY_UPDATED','material',material.id,'Updated a device assembly and its current price. Saved estimates are unchanged.')
    if commit:
        session.commit()
    logger.info('MATERIAL_ASSEMBLY_UPDATED user_id=%s material_id=%s revision=%s',user.id,material.id,record.revision)
    return listing(session)


def legend_price_gaps(session, assemblies):
    """Read-only coverage over existing approved classes and the BOM default rules."""
    materials=[dict(id=a['material_id'], code=a['code'], name=a['name'],
        unit_price=a['unit_price'], assembly=a) for a in assemblies]
    gaps=[]
    for legend in session.scalars(select(SymbolLegend).where(SymbolLegend.is_active.is_(True)).order_by(SymbolLegend.class_id)):
        kind=device_type(legend.name)
        if kind is None:
            continue  # A drawing notation or unresolved class is not an invented product.
        compatible=[m for m in materials if m['assembly']['device_type']==kind
            and _protected_match(legend.name,m['name']+' '+m['assembly']['specifications'])]
        priced=[m for m in compatible if m['unit_price'] is not None]
        default=choose_default(dict(kind='device',class_id=legend.class_id,name=legend.name),materials)
        reason=('missing_product' if not compatible else 'missing_component_price' if not priced or default is not None and default['unit_price'] is None
            else 'default_required' if default is None else 'incomplete_components' if default['assembly'].get('scope_complete',True) is False else None)
        if reason:
            gaps.append(dict(legend_id=legend.id,class_id=legend.class_id,name=legend.name,device_type=kind,
                reason=reason,compatible_material_ids=[m['id'] for m in compatible]))
    return gaps


def listing(session, *, include_coverage=False):
    result=[]
    for record in repository.records(session):
        material=session.get(Material,record.material_id)
        if not material:
            continue
        current=quote(session,record)
        result.append(dict(material_id=material.id,code=material.code,name=material.name,brand=record.brand,
            device_type=record.device_type,is_default=record.is_default,expected_revision=record.revision,
            **record.document,unit_price=Decimal(current['unit_price']) if current else None,
            currency=current['currency'] if current else None,price_available=current is not None,
            price_revision_id=record.price_snapshot.get('price_revision_id'),
            component_prices=current['components'] if current else []))
    response=dict(writable=repository.available(session),assemblies=result,name_examples=NAME_EXAMPLES)
    if include_coverage:
        response['price_gaps']=legend_price_gaps(session,result)
    return response


def annotate_catalog(session,materials):
    """Mark recipes; reject stale/missing component prices rather than use an old total."""
    by_id={r.material_id:r for r in repository.records(session)}
    for material in materials:
        record=by_id.get(material['id'])
        if record is None:
            continue
        current=quote(session,record)
        consistent=(current is not None and current=={k:v for k,v in record.price_snapshot.items() if k!='price_revision_id'}
            and material.get('price_revision_id')==record.price_snapshot.get('price_revision_id'))
        material['assembly']=dict(brand=record.brand,device_type=record.device_type,is_default=record.is_default,
            specifications=record.document['specifications'],scope=record.document['scope'],revision=record.revision,
            components=record.price_snapshot.get('components',[]))
        material['assembly']['assumed']=record.document.get('assumed',False)
        material['assembly']['scope_complete']=record.document.get('scope_complete',True)
        if not consistent:
            material.update(unit_price=None,currency=None,price_unavailable_reason='assembly_component_price_required')
            if 'has_price' in material:
                material['has_price']=False
    return materials


def estimate_snapshot(session,material_id,price_revision_id,*,records=None):
    records=records if records is not None else {r.material_id:r for r in repository.records(session)}
    record=records.get(material_id)
    if record is None:
        return None
    current=quote(session,record)
    if current is None or record.price_snapshot!={**current,'price_revision_id':price_revision_id}:
        raise AssemblyError('Assembly components changed. Reprice the assembly before estimating.')
    return dict(material_id=material_id,brand=record.brand,device_type=record.device_type,
        recipe_revision=record.revision,scope=record.document['scope'],components=current['components'],
        source_references=record.document.get('source_references',[]),shipping_included=False)
