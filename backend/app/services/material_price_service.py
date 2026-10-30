"""Price changes append history; the caller owns commit/rollback."""
from datetime import datetime, timezone
import logging

from app.repositories import material_price_repository as repository
from app.schemas.material_price import MaterialPriceWrite
from sqlalchemy import select,func
from app.models import Material,MaterialPrice

logger=logging.getLogger(__name__)


class MaterialPriceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def create_catalog_material(session,user,data):
    if user.role.name!='ADMIN':raise PermissionError('Only Admin can add catalog items.')
    from app.repositories import material_catalog_repository as catalog_repository
    from app.repositories.material_assembly_repository import records
    from app.services.material_workbook import WorkbookError
    records(session,lock=True)
    if data.unit in ('roll','length') and data.meters_per_unit is None:raise WorkbookError('Enter metres supplied in one roll or length.')
    if data.unit not in ('roll','length') and data.meters_per_unit is not None:raise WorkbookError('Purchase length is only used for rolls and lengths.')
    name=data.name+(f' ({data.meters_per_unit:g}m/{data.unit})' if data.meters_per_unit is not None else '')
    values=dict(code=data.code,name=name,category=data.category,unit=data.unit)
    material=catalog_repository.by_code(session,data.code,lock=True)
    if material:
        previous=repository.last_revision(session,material.id)
        if material.is_active and all(getattr(material,key)==value for key,value in values.items()) and previous and previous.unit_price==data.unit_price and previous.currency==data.currency:return next(row for row in catalog(session) if row['id']==material.id)
        raise WorkbookError('This item code already exists. Use another code or edit the existing catalog item.')
    material=catalog_repository.create(session,values)
    update_material_price(session,current_user=user,material_id=material.id,request=MaterialPriceWrite(unit_price=data.unit_price,currency=data.currency,effective_at=datetime.now(timezone.utc)))
    from app.services.activity_log import record
    record(session,user,'MATERIAL_CREATED','material',material.id,'Added a priced catalog item. Existing estimates unchanged.')
    session.commit()
    return next(row for row in catalog(session) if row['id']==material.id)


def catalog(session):
    latest=select(MaterialPrice.material_id,func.max(MaterialPrice.version_number).label('revision')).group_by(MaterialPrice.material_id).subquery()
    rows=session.execute(select(Material,MaterialPrice).outerjoin(latest,latest.c.material_id==Material.id)
        .outerjoin(MaterialPrice,(MaterialPrice.material_id==Material.id)&(MaterialPrice.version_number==latest.c.revision))
        .order_by(Material.name,Material.id))
    from app.repositories.material_assembly_repository import records as assembly_records
    assembly_ids={r.material_id for r in assembly_records(session)}
    return [dict(id=material.id,code=material.code,name=material.name,unit=material.unit,category=material.category,is_assembly=material.id in assembly_ids,
        is_active=material.is_active,unit_price=price.unit_price if price else None,currency=price.currency if price else None,
        revision=price.version_number if price else 0) for material,price in rows]


def save_catalog_price(session,user,material_id,data):
    if getattr(getattr(user,'role',None),'name',None)!='ADMIN':raise PermissionError('Only an Admin can change prices.')
    # Match recipe-save lock order before taking any component material lock.
    from app.repositories.material_assembly_repository import records as assembly_records
    assembly_records(session,lock=True)
    material=repository.lock_material(session,material_id)
    if material is None:raise MaterialPriceError('MATERIAL_NOT_FOUND')
    previous=repository.last_revision(session,material_id)
    if data.expected_revision!=(previous.version_number if previous else 0):raise MaterialPriceError('STALE_PRICE_REVISION')
    update_material_price(session,current_user=user,material_id=material_id,
        request=MaterialPriceWrite(unit_price=data.unit_price,currency=data.currency,effective_at=datetime.now(timezone.utc)))
    session.commit()
    logger.info('MATERIAL_PRICE_UPDATED user_id=%s material_id=%s',user.id,material_id)


def update_material_price(session, *, current_user, material_id, request: MaterialPriceWrite, _assembly_total=False):
    if getattr(getattr(current_user, "role", None), "name", None) != "ADMIN":
        raise MaterialPriceError("AUTHORIZATION_DENIED")
    from app.repositories.material_assembly_repository import records as assembly_records
    assemblies=assembly_records(session,lock=True) if not _assembly_total else []
    if any(r.material_id==material_id for r in assemblies):
        raise MaterialPriceError('ASSEMBLY_PRICE_IS_DERIVED')
    material = repository.lock_material(session, material_id)
    if material is None:
        raise MaterialPriceError("MATERIAL_NOT_FOUND")
    if not material.is_active:
        raise MaterialPriceError("MATERIAL_INACTIVE")
    effective = request.effective_at.replace(tzinfo=None)
    if effective > datetime.now(timezone.utc).replace(tzinfo=None):
        raise MaterialPriceError("FUTURE_PRICE_NOT_SUPPORTED")
    previous = repository.last_revision(session, material_id)
    if previous and effective < previous.effective_at:
        raise MaterialPriceError("PRICE_EFFECTIVE_TIME_PRECEDES_CURRENT")
    if previous and (previous.unit_price, previous.currency, previous.unit, previous.effective_at) == (
            request.unit_price, request.currency, material.unit, effective):
        return previous
    price=repository.append_price(session, material_id=material_id,
        version_number=previous.version_number + 1 if previous else 1,
        unit_price=request.unit_price, currency=request.currency, unit=material.unit,
        effective_at=effective, changed_by_user_id=current_user.id)
    from app.services.activity_log import record
    record(session,current_user,'PRICE_UPDATED','material',material_id,'Appended a material price revision. Historical estimates unchanged.')
    affected=[r for r in assemblies if any(p['material_id']==material_id for p in r.document['components'])]
    if affected:
        from app.services.material_assembly_service import refresh,AssemblyError
        try:
            refresh(session,current_user,affected)
        except AssemblyError:
            raise MaterialPriceError('ASSEMBLY_COMPONENT_PRICE_INVALID') from None
    return price
