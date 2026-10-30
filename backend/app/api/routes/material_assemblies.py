from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.schemas.material_assembly import AssemblyCatalog, AssemblyWrite
from app.services import material_assembly_service as service
from app.services.material_price_service import MaterialPriceError

router=APIRouter(prefix='/api/admin/material-assemblies',tags=['material pricing'])


def execute(session,action):
    try:
        return action()
    except PermissionError:
        session.rollback();raise HTTPException(403,'Only an Admin can change assemblies.') from None
    except service.AssemblyConflict as error:
        session.rollback();raise HTTPException(409,str(error)) from None
    except (service.AssemblyError,MaterialPriceError) as error:
        session.rollback();raise HTTPException(422,str(error) if isinstance(error,service.AssemblyError) else 'The component price is unavailable.') from None
    except IntegrityError:
        session.rollback();raise HTTPException(409,'Assemblies changed. Reload before saving.') from None
    except (RuntimeError,SQLAlchemyError):
        session.rollback();raise HTTPException(503,'Device assembly storage is temporarily unavailable. Ask your administrator to check setup.') from None


@router.get('',response_model=AssemblyCatalog)
def listing(_user=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    return execute(session,lambda:service.listing(session,include_coverage=True))


@router.post('',response_model=AssemblyCatalog,status_code=201)
def create(data:AssemblyWrite,user=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    return execute(session,lambda:service.save(session,user,data))


@router.get('/price-list.csv')
def price_list(_user=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    from app.services.bom_export import assembly_price_csv
    content=execute(session,lambda:assembly_price_csv(service.listing(session)['assemblies']))
    return Response(content,media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':'attachment; filename="VED-Device-Price-List.csv"','Cache-Control':'no-store'})


@router.put('/{material_id}',response_model=AssemblyCatalog)
def update(material_id:int,data:AssemblyWrite,user=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    return execute(session,lambda:service.save(session,user,data,material_id))
