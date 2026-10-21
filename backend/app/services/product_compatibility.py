"""Conservative product-family and explicit-rating checks, not electrical sizing."""
import re


def family(text):
    if re.search(r'\b(?:data|datacom|telephone|network|rj45)\b',text,re.I) and not re.search(r'\b(?:wire|wiring|cable|conduit|pipe)\b',text,re.I):
        return 'data'
    for kind, pattern in [('conduit',r'\b(?:conduit|pipe)\b'),('wire',r'\b(?:wire|wiring|cable)\b'),
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
    return explicit<=products and all(key in available and values<=available[key] for key,values in known.items())


def compatible_product(row, material):
    if row.get('material_conflict') or row.get('electrical_assignment_required'):
        return False
    if row.get('material_id') == material['id']:
        return True
    if row['kind']=='device' and row.get('class_id') is None:
        return False
    source=row['name']+' '+(row.get('material_name') or '')
    expected=row.get('material_kind') if row['kind']=='path' else family(source)
    actual=family(material.get('category','')+' '+material['name'])
    if expected not in ('wire','conduit','switch','outlet','light','data','panel') or actual!=expected:
        return False
    if row['unit']=='piece' and material['unit'] not in ('piece','unit'):
        return False
    if row['unit']=='meter' and material['unit']!='meter':
        return False  # Other purchase units need an explicit stored conversion.
    return specifications_match(source,material['name'])
