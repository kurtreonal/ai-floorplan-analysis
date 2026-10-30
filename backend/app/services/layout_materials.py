"""Layout-specific catalogue choices; geometry and historical estimates are untouched."""
import re
from typing import Literal,Annotated
from pydantic import Field
from app.services.product_compatibility import family

LayoutType=Literal['lighting','power','data']
LayoutSelection=LayoutType | Annotated[list[LayoutType],Field(min_length=1,max_length=3)]
LABELS={'lighting':'Lighting layout','power':'Power layout','data':'Data layout'}
SUPPLY=re.compile(r'\bservice entrance\b',re.I)


def layout_values(layout):
    values=layout if isinstance(layout,list) else [layout] if layout else []
    return [key for key in LABELS if key in values]


def device_layout(name):
    kind=family(name or '')
    if kind in ('light','switch'):return 'lighting'
    if kind in ('data','voice','cctv','security','alarm'):return 'data'
    if kind in ('outlet','panel','box','chime') or SUPPLY.search(name or ''):return 'power'
    return None


def wire_layout(material):
    text=material.get('category','')+' '+material.get('name','')
    return 'data' if re.search(r'\b(?:cat[5678][ae]?|utp|ftp|sftp|fiber|fibre|coax|rg[- ]?\d+|communications?|telephone|alarm|signal|instrumentation)\b',text,re.I) else 'power'


def route_device_layout(name):
    # Panels and boxes can serve both lighting and power; they do not identify a load.
    return None if family(name or '') in ('panel','box') or SUPPLY.search(name or '') else device_layout(name)


def wire_allowed(material,layout):
    values=layout_values(layout)
    return not values or any((wire_layout(material)=='data')==(value=='data') for value in values)


def device_allowed(name,layout):
    category=device_layout(name)
    return not layout or category is None or category in layout_values(layout)


def project_layout(db,project_id):
    from app.models.client_workflow import ProjectAssignment
    from app.services.intake_schema import details
    return details(db,db.get(ProjectAssignment,project_id),'intake_details').get('layout_type')


def default_wire(defaults,layout):
    choices={defaults.get(f'{value}_wire_material_id') for value in layout_values(layout)}
    return choices.pop() if len(choices)==1 else None
