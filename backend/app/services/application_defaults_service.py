"""Admin-controlled defaults. Explicit project measurements always win."""
import logging
import re
from sqlalchemy import inspect,select
from pydantic import BaseModel,ConfigDict,Field,StrictBool
from typing import Literal
from app.models.application_defaults import ApplicationDefaults
from app.services.wiring_material_pairing import MaterialPair

logger=logging.getLogger(__name__)


class Defaults(BaseModel):
    model_config=ConfigDict(extra='forbid')
    paper_size:Literal['A1','A2','A3','A4','A5']='A1'
    scale_denominator:float=Field(default=100,ge=1,le=100000,allow_inf_nan=False)
    ceiling_height_meters:float=Field(default=3,gt=0,le=100,allow_inf_nan=False)
    outlet_center_height_meters:float=Field(default=.3,ge=0,le=100,allow_inf_nan=False)
    switch_center_height_meters:float=Field(default=1.2,ge=0,le=100,allow_inf_nan=False)
    display_units:Literal['metric','imperial']='metric'
    editor_snapping:StrictBool=True
    show_blueprint:StrictBool=True
    show_walls:StrictBool=True
    show_symbols:StrictBool=True
    show_wiring:StrictBool=True
    wire_conduit_pairs:list[MaterialPair]=Field(default_factory=list,max_length=500)
    lighting_wire_material_id:int|None=Field(default=None,gt=0)
    power_wire_material_id:int|None=Field(default=None,gt=0)
    data_wire_material_id:int|None=Field(default=None,gt=0)
    planning_conductor_count:int=Field(default=3,ge=1,le=1000,strict=True)


class DefaultsWrite(Defaults):
    expected_revision:int=Field(ge=0,strict=True)


class DefaultsResponse(BaseModel):
    settings:Defaults
    revision:int
    writable:bool


def retrieve(session):
    available=inspect(session.connection()).has_table(ApplicationDefaults.__tablename__)
    record=session.get(ApplicationDefaults,1) if available else None
    values=Defaults.model_validate(record.document).model_dump() if record else Defaults().model_dump()
    return dict(settings=values,revision=record.revision if record else 0,writable=available)


def effective(session):
    return retrieve(session)['settings']


def mounting_defaults(session):
    values=effective(session)
    return dict(outlet=values['outlet_center_height_meters'],switch=values['switch_center_height_meters'])


def save(session,user,data):
    from app.models import Material
    if getattr(getattr(user,'role',None),'name',None)!='ADMIN':
        raise PermissionError('Only an Admin can change shared defaults.')
    if not inspect(session.connection()).has_table(ApplicationDefaults.__tablename__):
        raise RuntimeError('Defaults storage needs administrator setup.')
    record=session.scalar(select(ApplicationDefaults).where(ApplicationDefaults.id==1).with_for_update())
    if data.expected_revision!=(record.revision if record else 0):
        raise ValueError('Defaults changed. Reload before saving.')
    values=Defaults.model_validate(data.model_dump(exclude={'expected_revision'})).model_dump()
    for key in ('lighting_wire_material_id','power_wire_material_id','data_wire_material_id'):
        if key not in data.model_fields_set and record:values[key]=record.document.get(key)
        if values[key]:
            from app.services.layout_materials import wire_allowed
            material=session.get(Material,values[key])
            if (not material or not material.is_active or material.unit not in ('meter','length','roll')
                or not re.search(r'\b(?:wire|cable|cables)\b',material.name+' '+material.category,re.I)
                or not wire_allowed({'name':material.name,'category':material.category},key.split('_')[0])):
                raise ValueError('Choose an active wire compatible with the default layout.')
    if 'wire_conduit_pairs' not in data.model_fields_set and record:
        values['wire_conduit_pairs']=record.document.get('wire_conduit_pairs',[])
    from app.models import Material
    pairs=values['wire_conduit_pairs']
    if len({p['wire_material_id'] for p in pairs})!=len(pairs):
        raise ValueError('Choose one default conduit per wire product.')
    for pair in pairs:
        wire=session.get(Material,pair['wire_material_id']);conduit=session.get(Material,pair['conduit_material_id'])
        from app.services.product_compatibility import family
        if not wire or not conduit or not wire.is_active or not conduit.is_active or not (re.search(r'wire|cable',wire.name,re.I) or re.search(r'(?:COPPER|FIBER)\s*(?:-\s*)?CABLES?',wire.category,re.I)) or wire.unit not in ('meter','length','roll') or conduit.unit not in ('meter','length','roll') or family(conduit.category+' '+conduit.name)!='conduit':
            raise ValueError('Pairs require active wire and conduit products.')
        if pair.get('under_floor_conduit_material_id'):
            floor_conduit=session.get(Material,pair['under_floor_conduit_material_id'])
            if not floor_conduit or not floor_conduit.is_active or floor_conduit.unit not in ('meter','length','roll') or family(floor_conduit.category+' '+floor_conduit.name)!='conduit':
                raise ValueError('Choose an active under-floor conduit product.')
        for option_id in pair.get('conduit_options',[]):
            option=session.get(Material,option_id)
            if not option or not option.is_active or option.unit not in ('meter','length','roll') or family(option.category+' '+option.name)!='conduit':
                raise ValueError('Conduit choices require active raceway products, not loose fittings.')
    if record and 'ceiling_height_meters' not in data.model_fields_set:
        values['ceiling_height_meters']=Defaults.model_validate(record.document).ceiling_height_meters
    if record and 'planning_conductor_count' not in data.model_fields_set:
        values['planning_conductor_count']=Defaults.model_validate(record.document).planning_conductor_count
    if record:
        record.document=values;record.revision+=1;record.updated_by_user_id=user.id
    else:
        session.add(ApplicationDefaults(id=1,revision=1,document=values,updated_by_user_id=user.id))
    from app.services.activity_log import record as log_activity
    log_activity(session,user,'DEFAULTS_UPDATED','defaults',1,'Updated shared planning defaults or wire/conduit pairs.')
    session.commit()
    result=retrieve(session)
    logger.info('APPLICATION_DEFAULTS_UPDATED user_id=%s revision=%s',user.id,result['revision'])
    return result
