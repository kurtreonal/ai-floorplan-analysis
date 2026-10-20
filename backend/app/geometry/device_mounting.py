"""VED-confirmed AFF defaults. These are not universal electrical-code rules."""
from copy import deepcopy
import re

VED_CENTER_HEIGHTS={'outlet':0.30,'switch':1.20}


def default_family(name):
    if re.search(r'\b(?:data|telephone|network|panel|switchboard|home.?run|notation)\b',name,re.I):
        return None
    if re.search(r'\b(?:outlet|receptacle|socket)\b',name,re.I):return 'outlet'
    if re.search(r'\bswitch(?:es)?\b',name,re.I):return 'switch'


def resolved_mounting(symbol, name=None):
    """Return a copy, preserving explicit heights and unknown historical references."""
    result=dict(symbol)
    family=default_family(name or symbol.get('class_name') or '')
    height=symbol.get('mounting_height_meters')
    reference=symbol.get('mounting_reference')
    if (symbol.get('disposition')!='rejected' and family and
        (name is not None or symbol.get('symbol_legend_id') or symbol.get('class_id') is not None) and
        (height is None or symbol.get('mounting_height_source')=='ved_default') and
        reference in (None,'device_center')):
        result.update(mounting_height_meters=VED_CENTER_HEIGHTS[family],mounting_reference='device_center',mounting_height_source='ved_default')
    return result


def mounting_document(document, legends):
    result=deepcopy(document)
    result['symbols']=[resolved_mounting(symbol,legends[symbol['symbol_legend_id']].name)
        if symbol.get('symbol_legend_id') in legends else dict(symbol)
        for symbol in document.get('symbols',[])]
    return result


def connection_height(symbol):
    """Reference-point height plus an explicitly supplied terminal offset.

    Without an offset, route geometry terminates at the declared mounting
    reference (center for VED defaults), not a claimed manufacturer terminal.
    """
    height=symbol.get('mounting_height_meters')
    return None if height is None else height+(symbol.get('terminal_offset_meters') or 0)
