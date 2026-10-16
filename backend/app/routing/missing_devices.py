"""Complete explicit circuit assignments without inferring source connectivity.

Observed/reviewed canonical paths are never modified. Only version-matched
saved generated branches of the SAME circuit can be retained in a new version.
"""
import math

from app.routing.circuit import CircuitBranch, CircuitPlanningResult, CircuitTargetIssue, SavedCircuitResult
from app.routing.contracts import Point, Segment
from app.routing.engine import generate_route, segment, validate_target
from app.routing.graph import RoutingError


def _key(point):
    return (point.floor_id, point.x, point.y, point.elevation_meters)


def _connected(document, extension):
    """Require persisted identities and an aligned route anchor, never proximity."""
    if extension is None:
        return set()
    routes = {route.id: route for route in document.routes}
    symbols = {symbol.id: symbol for symbol in document.symbols}
    result = set()
    for detail in extension.route_details:
        route = routes.get(detail.route_id)
        if route is None or len(route.points) < 2:
            continue
        for contact in detail.device_connections or ():
            symbol = symbols.get(contact.symbol_id)
            if symbol is None or not 0 <= contact.point_index < len(route.points):
                continue
            point, anchor = route.points[contact.point_index], contact.anchor
            if (point.project_floor_id == document.floor.project_floor_id
                and all(math.isclose(a, b, abs_tol=1e-9, rel_tol=0) for a, b in (
                    (point.x, anchor['x']), (point.y, anchor['y']),
                    (point.elevation_meters, anchor['elevation_meters']),
                    (symbol.position.x, anchor['x']), (symbol.position.y, anchor['y'])))
                and any((other.x, other.y, other.elevation_meters) !=
                        (point.x, point.y, point.elevation_meters) for other in route.points)):
                result.add(contact.symbol_id)
    return result


def _unreferenced_contact(document, target):
    # A literal on-path symbol with no identity binding is ambiguous, not proof
    # of an electrical junction and not permission to generate a duplicate.
    for route in document.routes:
        for a, b in zip(route.points, route.points[1:]):
            if a.project_floor_id != target.floor_id or b.project_floor_id != target.floor_id:
                continue
            dx, dy = b.x-a.x, b.y-a.y
            length2 = dx*dx+dy*dy
            if not length2:
                continue
            t = ((target.x-a.x)*dx+(target.y-a.y)*dy)/length2
            if 0 <= t <= 1 and math.hypot(target.x-a.x-t*dx, target.y-a.y-t*dy) <= 1e-9:
                return True
    return False


def _retained(request, previous, versions):
    if previous is None:
        return []
    try:
        SavedCircuitResult.model_validate(previous.result)
    except ValueError:
        raise RoutingError('EXISTING_ROUTE_REVIEW_REQUIRED') from None
    old = previous.configuration
    if (previous.layout_versions != versions or old.get('circuit_id') != request.circuit_id
        or previous.result.get('status') != 'saved_planning'
        or old.get('installation_method') != request.installation_method
        or old.get('panel') != request.panel.model_dump(mode='json')
        or old.get('floors') != [floor.model_dump(mode='json') for floor in request.floors]
        or old.get('obstacles', []) != [obstacle.model_dump(mode='json') for obstacle in request.obstacles]
        or old.get('connectors', []) != [connector.model_dump(mode='json') for connector in request.connectors]
        or old.get('grid_step_meters') != request.grid_step_meters):
        raise RoutingError('EXISTING_ROUTE_REVIEW_REQUIRED')
    targets = {(target.floor_id, target.symbol_id): target.model_dump(mode='json') for target in request.targets}
    old_targets = {(target['floor_id'], target['symbol_id']): target for target in old.get('targets', [])}
    branches = previous.result.get('branches', [])
    if any(targets.get((branch['floor_id'], branch['symbol_id'])) != old_targets.get((branch['floor_id'], branch['symbol_id']))
           or (branch['floor_id'], branch['symbol_id']) not in old_targets for branch in branches):
        raise RoutingError('EXISTING_ROUTE_REVIEW_REQUIRED')
    return branches


def _combine(paths):
    """Split shared collinear spans consistently for unique physical lengths.

    This indexes paths inside the new proposal only; source canonical routes
    and previous immutable route versions remain unchanged.
    """
    points = { _key(point): point for _, path in paths for point in path.points }
    segments, identities, branches = [], {}, []
    for target, path in paths:
        ordered, indices = [], []
        if not path.segments:
            ordered = list(path.points)
        for original in path.segments:
            a, b = original.start, original.end
            values_a, values_b = (a.x, a.y, a.elevation_meters), (b.x, b.y, b.elevation_meters)
            axes = [i for i in range(3) if values_a[i] != values_b[i]]
            cuts = []
            if a.floor_id == b.floor_id and len(axes) == 1:
                axis = axes[0]
                for point in points.values():
                    values = (point.x, point.y, point.elevation_meters)
                    t = (values[axis]-values_a[axis])/(values_b[axis]-values_a[axis])
                    if (point.floor_id == a.floor_id and 0 < t < 1
                        and all(values[i] == values_a[i] for i in range(3) if i != axis)):
                        cuts.append((t, point))
            chain = [a, *(point for _, point in sorted(cuts, key=lambda item: item[0])), b]
            if not ordered:
                ordered.append(a)
            for first, last in zip(chain, chain[1:]):
                identity = (tuple(sorted((_key(first), _key(last)))), original.connector_id)
                if identity not in identities:
                    identities[identity] = len(segments)
                    segments.append(segment(first, last, original.kind, original.connector_id))
                indices.append(identities[identity])
                ordered.append(last)
        horizontal = sum(segments[index].horizontal_meters for index in indices)
        vertical = sum(segments[index].vertical_meters for index in indices)
        branches.append(CircuitBranch(floor_id=target.floor_id, symbol_id=target.symbol_id,
            points=ordered, segment_indices=indices, horizontal_meters=horizontal,
            vertical_meters=vertical, total_meters=horizontal+vertical))
    return segments, branches


def plan_missing_devices(request, documents, extensions, previous, versions):
    from types import SimpleNamespace

    retained = {(branch['floor_id'], branch['symbol_id']): branch for branch in _retained(request, previous, versions)}
    connected = {floor: _connected(document, extensions.get(floor)) for floor, document in documents.items()}
    paths, skipped, unresolved = [], [], []
    # Expand the already validated saved tree before considering new targets,
    # independent of lexical device order. Its layout/configuration/assignments
    # were checked by _retained; no observed circuit identity is guessed.
    configs = {config.floor_id: config for config in request.floors}
    service_sources = set()
    for branch in retained.values():
        for raw in branch['points']:
            point = Point.model_validate(raw)
            if point.elevation_meters == configs[point.floor_id].service_elevation_meters:
                service_sources.add(point)
    for target in sorted(request.targets, key=lambda item: (item.floor_id, item.symbol_id)):
        identity = (target.floor_id, target.symbol_id)
        issue = dict(floor_id=target.floor_id, symbol_id=target.symbol_id)
        validate_target(request.single_target(target), documents)
        if identity in retained:
            branch = retained[identity]
            paths.append((target, SimpleNamespace(
                points=[Point.model_validate(point) for point in branch['points']],
                segments=[Segment.model_validate(previous.result['segments'][index]) for index in branch['segment_indices']],
            )))
            continue
        if target.symbol_id in connected[target.floor_id]:
            skipped.append(CircuitTargetIssue(**issue, reason='EXISTING_CANONICAL_CONNECTION'))
            continue
        if _unreferenced_contact(documents[target.floor_id], target):
            unresolved.append(CircuitTargetIssue(**issue, reason='SOURCE_ATTACHMENT_REVIEW_REQUIRED'))
            continue
        try:
            generated = generate_route(request.single_target(target), documents, service_sources=service_sources)
            paths.append((target, generated))
            service_sources.update(point for point in generated.points
                if point.elevation_meters == configs[point.floor_id].service_elevation_meters)
        except RoutingError as error:
            if str(error) not in {'NO_ROUTE', 'WALL_ATTACHMENT_REQUIRED', 'ENDPOINT_NOT_ON_WALL',
                                 'ENDPOINT_OUTSIDE_WALL_HEIGHT', 'ZERO_LENGTH_ROUTE'}:
                raise
            unresolved.append(CircuitTargetIssue(**issue, reason=str(error)))
    segments, branches = _combine(paths)
    horizontal = sum(item.horizontal_meters for item in segments)
    vertical = sum(item.vertical_meters for item in segments)
    return CircuitPlanningResult(circuit_id=request.circuit_id, installation_method=request.installation_method,
        algorithm='assigned_missing_device_astar_v2', segments=segments, branches=branches,
        skipped_targets=skipped, unresolved_targets=unresolved,
        horizontal_meters=horizontal, vertical_meters=vertical, total_meters=horizontal+vertical)
