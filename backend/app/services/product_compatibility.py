"""Conservative product-family and explicit-rating checks, not electrical sizing."""
import re
from fractions import Fraction


def inch_sizes(text):
    """Trade-size fractions stay distinct; source line IDs are not dimensions."""
    text = re.sub(r'\[(?:pdf-|sheet-|u:)[^\]]+\]', '', text.casefold())
    pattern = r'(?<![\d/])((?:\d+[ -]+)?\d+/\d+|\d+(?:\.\d+)?)\s*(?:["″”]|inches?\b|in\b)'
    result = set()
    for value in re.findall(pattern, text):
        try:
            result.add(float(sum((Fraction(p) for p in re.split(r'[ -]+', value)), Fraction(0))))
        except (ValueError, ZeroDivisionError):
            continue
    return result


def fitting_styles(text):
    text = text.casefold()
    styles = set()
    for kind, pattern in [('non_threaded', r'\b(?:non[- ]threaded|unthreaded|threadless)\b'),
            ('set_screw', r'\bset[- ]screw\b'), ('compression', r'\bcompression\b'),
            ('male', r'\bmale\b'), ('female', r'\bfemale\b')]:
        if re.search(pattern, text): styles.add(kind)
    if 'non_threaded' not in styles and re.search(r'\bthreaded\b', text): styles.add('threaded')
    return styles


def source_specification(row):
    """A fallback assembly describes the estimate, not additional source evidence."""
    return row['name']+' '+('' if row.get('default_brand_used') else row.get('material_name') or '')


def family(text):
    if re.search(r'\b(?:voice|telephone).*outlet\b',text,re.I):
        return 'voice'
    if re.search(r'\b(?:data|datacom|telephone|network|rj45)\b',text,re.I) and not re.search(r'\b(?:wire|wiring|cable|conduit|pipe)\b',text,re.I):
        return 'data'
    for kind, pattern in [('conduit',r'\b(?:conduit|pipe)\b'),('wire',r'\b(?:wire|wiring|cable)\b'),
            ('alarm',r'\b(?:smoke detector|heat detector|fire alarm|pull station|manual call point|horn.*strobe|siren.*strobe)\b'),
            ('security',r'\b(?:magnetic(?: door)? contact|motion detector|vibration detector|keypad)\b'),
            ('voice',r'\b(?:voice|telephone).*outlet\b'),
            ('box',r'\b(?:utility box|pull box)\b'),('chime',r'\b(?:bell/chime|doorbell|door chime)\b'),
            ('cctv',r'\b(?:cctv|surveillance camera)\b'),
            ('panel',r'\b(?:panelboard|panel board|distribution board|electrical panel)\b'),
            ('switch',r'\bswitch(?:es)?\b'),('outlet',r'\b(?:outlet|receptacle|socket)\b'),
            ('light',r'\b(?:light|lighting|lamp|troffer|luminaire|downlight|spotlight|floodlight|fluorescent)\b'),('data',r'\b(?:data|datacom)\b')]:
        if re.search(pattern,text,re.I): return kind


def ratings(text):
    text=text.casefold().replace('²','2')
    words={'one':'1','two':'2','three':'3','four':'4'}
    text=re.sub(r'\b(one|two|three|four)(?=[ -]+gang\b)',lambda m:words[m[0]],text)
    result={}
    lamps=re.search(r'\b(\d+)\s*[x×]\s*\d+(?:\.\d+)?\s*(?:watts?|w)\b',text)
    if lamps:
        result['lamps']={float(lamps[1])}
    for value,unit in re.findall(r'(\d+(?:\.\d+)?)\s*(mm2|mm|awg|gang|amps?|a\b|volts?|v\b|watts?|w\b|c\b)',text):
        unit={'a':'amp','amps':'amp','volts':'volt','v':'volt','watts':'watt','w':'watt'}.get(unit,unit)
        result.setdefault(unit,set()).add(float(value))
    return result


def specifications_match(source, offered):
    known, available=ratings(source),ratings(offered)
    explicit=set(re.findall(r'\b(?:pvc|emt|imc|rsc|rmc|thhn|thwn|xlpe|copper|aluminum|duplex|simplex|cat[5678](?:[ae])?)\b',source.casefold()))
    products=set(re.findall(r'\b(?:pvc|emt|imc|rsc|rmc|thhn|thwn|xlpe|copper|aluminum|duplex|simplex|cat[5678](?:[ae])?)\b',offered.casefold()))
    sizes = inch_sizes(source)
    return (explicit<=products and (not sizes or sizes <= inch_sizes(offered))
            and fitting_styles(source) <= fitting_styles(offered)
            and all(key in available and values<=available[key] for key,values in known.items()))


def compatible_product(row, material):
    if row.get('material_conflict') or row.get('electrical_assignment_required'):
        return False
    if row.get('material_id') == material['id']:
        return True
    if row['kind']=='device' and row.get('class_id') is None:
        return False
    source=source_specification(row)
    expected=row.get('material_kind') if row['kind']=='path' else family(source)
    actual=family(material.get('category','')+' '+material['name'])
    if expected not in ('wire','conduit','switch','outlet','light','data','panel','cctv','alarm','security','voice','box','chime') or actual!=expected:
        return False
    if row['unit']=='piece' and material['unit'] not in ('piece','unit'):
        return False
    if row['unit']=='meter' and material['unit']!='meter':
        return False  # Other purchase units need an explicit stored conversion.
    return specifications_match(source,material['name'])
