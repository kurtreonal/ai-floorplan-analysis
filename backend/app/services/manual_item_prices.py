"""Versioned, item-scoped price overrides; no catalog or quantity mutation."""
from copy import deepcopy
from app.repositories import item_price_repository as repository
from app.repositories.estimate_repository import floor_ids
from app.repositories.routing_repository import lock_context
from app.services import project_pricing_service as pricing
from app.services.material_workbook import WorkbookError


def quantity_unit(row):
    return 'meter' if row['unit']=='source pixel' else row['unit']


def quote(assignment,row):
    from app.services.automatic_client_pricing import target_fingerprint
    if row is None or assignment.get('fingerprint')!=target_fingerprint(row) or assignment['unit']!=quantity_unit(row):
        return None
    return dict(row_id=assignment['price_row_id'],name=assignment['name'],code='',specification='',
        unit=assignment['unit'],quantity_unit=assignment['unit'],units_per_purchase='1',
        unit_price=assignment['unit_price'],currency=assignment['currency'])


def save(session,user,project_id,request):
    from app.services.item_pricing_service import inventory
    from app.services.automatic_client_pricing import target_fingerprint
    pricing._access(session,user,project_id,write=True)
    lock_context(session,project_id,floor_ids(session,project_id))
    identity=pricing._hash(request.model_dump(mode='json',exclude={'request_id'}))
    retry=repository.retry(session,project_id,str(request.request_id))
    if retry:
        if retry.request_hash!=identity:
            raise pricing.PricingConflict('Retry prices changed. Reload before saving.')
        session.commit()
        return dict(id=retry.id,version_number=retry.version_number)
    current=repository.current(session,project_id,lock=True)
    version=current.version_number if current else 0
    if version!=request.expected_version:
        raise pricing.PricingConflict('Prices changed in another session. Reopen Edit prices.')
    rows={r['item_key']:r for r in inventory(session,user,project_id)['items']}
    if any(item.item_key not in rows for item in request.items):
        raise pricing.PricingConflict('Saved items changed. Save the plan and reopen Edit prices.')
    saved=deepcopy(current.document['assignments']) if current else {}
    for item in request.items:
        row=rows[item.item_key]
        saved[item.item_key]=dict(source_kind='manual_price',price_version_id=None,
            price_row_id='manual:'+item.item_key,fingerprint=target_fingerprint(row),
            name=row.get('client_product_name') or row.get('material_name') or row['name'],
            unit=quantity_unit(row),unit_price=str(item.unit_price),currency=item.currency)
    if len(saved)>20000:
        raise WorkbookError('This project has reached the saved item-price limit.')
    record=repository.append(session,project_id=project_id,version_number=version+1,
        created_by_user_id=user.id,request_id=str(request.request_id),request_hash=identity,
        document=dict(current.document if current else {},assignments=saved,application=dict(kind='manual_prices',applied=len(request.items))))
    session.commit()
    return dict(id=record.id,version_number=record.version_number)
