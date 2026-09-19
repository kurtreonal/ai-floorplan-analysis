from app.repositories.routing_repository import latest_route, current_layout_ids, lock_context, append_route
from app.routing.engine import generate_route
from app.routing.graph import RoutingError
from app.services.layout_service import retrieve_accessible_current_layout
from app.services.project_service import get_accessible_project


def response(session, record):
    if record is None:
        return None
    current = current_layout_ids(session, record.project_id, [int(x) for x in record.layout_versions])
    return dict(id=record.id, project_id=record.project_id, version_number=record.version_number,
                layout_versions=record.layout_versions, configuration=record.configuration,
                result=record.result, stale=current != record.layout_versions)


def load_routes(session, user, project_id):
    get_accessible_project(session, current_user=user, project_id=project_id)
    return response(session, latest_route(session, project_id))


def create_route(session, user, project_id, request):
    if user.role.name != 'DESIGNER':
        raise RoutingError('AUTHORIZATION_DENIED')
    get_accessible_project(session, current_user=user, project_id=project_id)
    documents, versions = {}, {}
    for config in request.floors:
        record = retrieve_accessible_current_layout(session, current_user=user,
                    project_id=project_id, project_floor_id=config.floor_id)
        if record.version_number != config.expected_layout_version:
            raise RoutingError('STALE_LAYOUT_VERSION')
        documents[config.floor_id] = record.geometry
        versions[str(config.floor_id)] = record.id
    generated = generate_route(request, documents)
    # Computation precedes locks; recheck every pinned snapshot under the same
    # floor locks used by canonical saves before publishing the route version.
    lock_context(session, project_id, sorted(documents))
    if current_layout_ids(session, project_id, list(documents), lock=True) != versions:
        raise RoutingError('STALE_LAYOUT_VERSION')
    previous = latest_route(session, project_id, lock=True)
    record = append_route(session, project_id=project_id, version_number=previous.version_number + 1 if previous else 1,
        created_by_user_id=user.id, layout_versions=versions,
        configuration=request.model_dump(mode='json'), result=generated.model_dump(mode='json'))
    payload = response(session, record)
    session.commit()
    return payload
