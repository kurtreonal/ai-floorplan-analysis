from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.material_import import ImportPreview, ImportResult, MaterialImportSelection
from app.services import material_import_service as service
from app.services.material_price_service import MaterialPriceError
from app.services.material_workbook import MAX_FILE, WorkbookError
from app.schemas.material_price import CatalogMaterial,CatalogPriceWrite,CatalogMaterialCreate
from app.services import material_price_service as price_service

router = APIRouter(prefix='/api/admin/materials', tags=['material pricing'])


@router.get('',response_model=list[CatalogMaterial])
def catalog(_user:User=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    return execute(session,lambda:price_service.catalog(session))


@router.post('',response_model=CatalogMaterial,status_code=201)
def create_item(data:CatalogMaterialCreate,request:Request,user:User=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    from app.services.local_accounts import require_same_origin
    require_same_origin(request)
    return execute(session,lambda:price_service.create_catalog_material(session,user,data))


@router.put('/{material_id}/price',status_code=204)
def save_price(material_id:int,data:CatalogPriceWrite,user:User=Depends(require_roles('ADMIN')),session:Session=Depends(get_db)):
    try:price_service.save_catalog_price(session,user,material_id,data)
    except MaterialPriceError as error:
        session.rollback()
        raise HTTPException(409 if error.code=='STALE_PRICE_REVISION' else 422,
            'Price changed. Reload and try again.' if error.code=='STALE_PRICE_REVISION' else 'This price cannot be changed.') from None
    except (PermissionError,SQLAlchemyError) as error:
        session.rollback()
        raise HTTPException(403 if isinstance(error,PermissionError) else 503,'Material prices are temporarily unavailable.') from None


def contents(file):
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise WorkbookError('Only .xlsx price workbooks are supported.')
    return file.file.read(MAX_FILE + 1)


def execute(session, action):
    try:
        return action()
    except (WorkbookError, ValidationError, SQLAlchemyError, MaterialPriceError, PermissionError) as error:
        session.rollback()
        status = 503 if isinstance(error, SQLAlchemyError) else 403 if isinstance(error, PermissionError) else 422
        code = 'MATERIAL_STORAGE_UNAVAILABLE' if status == 503 else 'AUTHORIZATION_DENIED' if status == 403 else 'MATERIAL_IMPORT_INVALID'
        message = str(error) if isinstance(error, WorkbookError) else 'The material import could not be completed.'
        raise HTTPException(status, detail={'error': {'code': code, 'message': message, 'details': {}}}) from None


@router.post('/import/preview', response_model=ImportPreview)
def preview(file: Annotated[UploadFile, File()], user: User = Depends(require_roles('ADMIN')), session: Session = Depends(get_db)):
    return execute(session, lambda: service.preview(session, user, contents(file)))


@router.post('/import/apply', response_model=ImportResult)
def apply(file: Annotated[UploadFile, File()], selection: Annotated[str, Form(max_length=300000)],
          user: User = Depends(require_roles('ADMIN')), session: Session = Depends(get_db)):
    return execute(session, lambda: service.apply(session, user, contents(file), MaterialImportSelection.model_validate_json(selection)))
