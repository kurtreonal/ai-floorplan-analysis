"""Synthetic testing only. Local browser fixture; exact fixture rows removed on exit.

Run with the normal frontend using VITE_AUTH_ENABLED=true and API URL
http://127.0.0.1:8001 on port 5174. Never bind this test identity to a public host.
"""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

root=Path(__file__).resolve().parents[1]
url=make_url(os.environ.get('TEST_DATABASE_URL') or dotenv_values(root/'.env').get('TEST_DATABASE_URL') or '')
if (url.username!='ved_test' or url.database!='ved_electrical_verify' or url.host not in ('localhost','127.0.0.1')):
    raise SystemExit('Refusing anything except the restricted local verification database.')
engine=create_engine(url)
with engine.connect() as db:
    grants={r.split(' TO ')[0] for r in db.execute(text('SHOW GRANTS')).scalars()}
    if not grants or not grants<={'GRANT USAGE ON *.*','GRANT ALL PRIVILEGES ON `ved_electrical_verify`.*'}:
        raise SystemExit('Verification grants are not restricted.')
    for table in inspect(db).get_table_names():
        quoted=engine.dialect.identifier_preparer.quote(table)
        if table!='roles' and db.execute(text(f'SELECT COUNT(*) FROM {quoted}')).scalar_one():
            raise SystemExit('Verification database is not empty; no fixture writes performed.')
engine.dispose()
os.environ['DATABASE_URL']=url.render_as_string(hide_password=False)
os.environ['AUTO_START_DEMO_WORKER']='false';os.environ['AUTO_START_INTERPRETATION_WORKER']='false'
with TemporaryDirectory(prefix='ved-synthetic-pricing-') as folder:
    for name in ('UPLOAD_DIR','PROCESSED_DIR','DETECTION_DIR','PREVIEW_DIR','REPORT_DIR'):
        os.environ[name]=str(Path(folder)/name.lower())
    sys.path.insert(0,str(root/'backend'))
    from tests.test_routing_api import context
    from tests.synthetic_pricing import prepare
    from app.core.database import get_engine
    from app.models import ProjectPriceVersion,ItemPriceAssignment,LayoutVersion,FloorPlan,ProjectFloor,Project,MaterialPrice,Material,User
    from app.api.dependencies import get_current_user
    from app.core.database import get_db
    from app.core.config import Settings
    from app.main import create_app
    from fastapi import Depends
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    import uvicorn
    for table in (ProjectPriceVersion.__table__,ItemPriceAssignment.__table__):
        table.create(get_engine(),checkfirst=True)
    generator=context.__wrapped__()
    ctx=next(generator)
    try:
        fixture,materials=prepare(ctx)
        project_id=ctx[4].project_id;floor_id=ctx[4].project_floor_id;plan_id=ctx[4].floor_plan_id
        user_ids=[ctx[5].dependency_overrides[get_current_user]().id,ctx[6].id,ctx[7].id]
        material_ids=[m.id for m in materials]
        # Browser requests run concurrently: each needs a normal independent
        # session, not the single transaction shared by synchronous API tests.
        ctx[3].get_bind().commit()
        app=create_app(Settings(_env_file=None,frontend_url='http://127.0.0.1:5174',cors_allowed_origins='http://127.0.0.1:5174',auto_start_demo_worker=False,auto_start_interpretation_worker=False))
        def identity(db=Depends(get_db)):
            return db.get(User,user_ids[0])
        app.dependency_overrides[get_current_user]=identity
        print(f'Synthetic testing only: http://127.0.0.1:5174/#/app/projects/{project_id}/estimates',flush=True)
        print('Expected after selected pricing: PHP '+fixture['expected']['priced_total_php']+'. Ctrl+C removes only these fixture records.',flush=True)
        uvicorn.run(app,host='127.0.0.1',port=8001,log_level='warning')
    finally:
        generator.close()
        if 'material_ids' in locals():
            with Session(get_engine()) as db:
                for model in (ItemPriceAssignment,ProjectPriceVersion,LayoutVersion):
                    db.execute(delete(model).where(model.project_id==project_id))
                db.execute(delete(FloorPlan).where(FloorPlan.id==plan_id))
                db.execute(delete(ProjectFloor).where(ProjectFloor.id==floor_id))
                db.execute(delete(Project).where(Project.id==project_id))
                db.execute(delete(MaterialPrice).where(MaterialPrice.material_id.in_(material_ids)))
                db.execute(delete(Material).where(Material.id.in_(material_ids)))
                db.execute(delete(User).where(User.id.in_(user_ids)))
                db.commit()
        print('Exact synthetic fixture records removed. Real projects were not used.',flush=True)
