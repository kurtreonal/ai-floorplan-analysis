from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.services import application_defaults_service as service

router=APIRouter(tags=['application defaults'])

@router.get('/api/application-defaults',response_model=service.DefaultsResponse)
def get_defaults(_user=Depends(require_roles('ADMIN','DESIGNER')),session:Session=Depends(get_db)):
    try:return service.retrieve(session)
    except SQLAlchemyError:
        session.rollback();raise HTTPException(503,'Defaults are temporarily unavailable.') from None

@router.put('/api/admin/application-defaults',response_model=service.DefaultsResponse)
def put_defaults(data:service.DefaultsWrite,request:Request,user=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    from app.services.local_accounts import require_same_origin
    require_same_origin(request)
    try:return service.save(session,user,data)
    except PermissionError:
        session.rollback();raise HTTPException(403,'Only an Admin can change shared defaults.') from None
    except (IntegrityError,ValueError):
        session.rollback();raise HTTPException(409,'Defaults changed. Reload and try again.') from None
    except (RuntimeError,SQLAlchemyError):
        session.rollback();raise HTTPException(503,'Defaults storage needs administrator setup.') from None


@router.get('/api/admin/application-defaults/pairing-proposals')
def pairing_proposals(user=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    from app.services.material_price_service import catalog
    from app.services.wiring_material_pairing import provisional_pairs
    return provisional_pairs([m for m in catalog(session) if m['is_active']])
