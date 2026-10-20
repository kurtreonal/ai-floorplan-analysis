"""Explicit synthetic records, reusable only with the restricted test context."""
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.models import Material, MaterialPrice


def prepare(ctx):
    _,_,_,session,layout,_,_,admin=ctx
    assert session.get_bind().engine.url.database=='ved_electrical_verify'
    fixture=json.loads((Path(__file__).resolve().parents[2]/'fixtures/synthetic_pricing.json').read_text())
    floor=layout.project_floor_id
    geometry=deepcopy(layout.geometry_document)
    geometry['floor']['elevation_meters']=0
    geometry['coordinate_system'].update(width_meters=20,height_meters=10,image_width_pixels=2000,image_height_pixels=1000)
    geometry['symbols']=[dict(id=f'manual:{i+1}',source_type='manual',source_record_id=i+1,processing_job_id=103,
        status='manually_added',**{'class':dict(id=7 if i<2 else 2,name=fixture['materials'][0 if i<2 else 1][1])},position=dict(x=1+i*5,y=1)) for i in range(3)]
    geometry['routes']=[dict(id=i+1,points=[dict(project_floor_id=floor,x=x,y=y,elevation_meters=z) for x,y,z in points]) for i,points in enumerate(fixture['routes'])]
    layout.geometry_document=geometry
    layout.project.name='Synthetic testing only — BOM pricing'
    materials=[]
    for code,name,unit,category,amount in fixture['materials']:
        material=Material(code=code,name=name,unit=unit,category=category)
        session.add(material);session.flush();materials.append(material)
        session.add(MaterialPrice(material_id=material.id,version_number=1,unit_price=amount,unit=unit,currency='PHP',
            effective_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(seconds=2),changed_by_user_id=admin.id))
    session.commit()
    return fixture,materials
