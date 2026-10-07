from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.routing.contracts import RoutingRequest, RouteResult
from app.routing.circuit import CircuitPlanningRequest, CircuitPlanningResult, CircuitSaveRequest, SavedCircuitResult
from app.routing.graph import RoutingError
from app.services.layout_service import LayoutServiceError
from app.services.project_service import ProjectNotFoundError
from app.services.routing_service import load_routes, create_route, preview_circuit, save_circuit

router = APIRouter(prefix='/api/projects', tags=['routing'])


class RoutingResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int
    project_id: int
    version_number: int
    layout_versions: dict[str, int]
    configuration: RoutingRequest
    result: RouteResult
    stale: bool


class CircuitPlanningResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: int
    layout_versions: dict[str, int]
    configuration: CircuitPlanningRequest
    result: CircuitPlanningResult
    stale: bool


class SavedCircuitResponse(CircuitPlanningResponse):
    id: int
    version_number: int
    configuration: CircuitSaveRequest
    result: SavedCircuitResult


def execute(session, action):
    try:
        return action()
    except (RoutingError, LayoutServiceError, ProjectNotFoundError, SQLAlchemyError) as error:
        session.rollback()
        if isinstance(error, SQLAlchemyError):
            code, status = 'ROUTING_STORAGE_UNAVAILABLE', 503
        elif isinstance(error, ProjectNotFoundError):
            code, status = 'PROJECT_NOT_FOUND', 404
        else:
            code = error.code if isinstance(error, LayoutServiceError) else str(error)
            status = 409 if code in {'STALE_LAYOUT_VERSION', 'STALE_ROUTE_VERSION', 'CIRCUIT_RETRY_CONFLICT'} else 422
            if code == 'AUTHORIZATION_DENIED':
                status = 403
            elif code == 'LAYOUT_NOT_FOUND':
                status = 404
        raise HTTPException(status, detail={'error': {'code': code, 'message': 'The routing operation could not be completed.', 'details': {}}}) from None


@router.get('/{project_id}/routes', response_model=RoutingResponse | SavedCircuitResponse | None)
def get_routes(project_id: Annotated[int, Path(gt=0)], user: User = Depends(require_roles('ADMIN', 'DESIGNER')), session: Session = Depends(get_db)):
    return execute(session, lambda: load_routes(session, user, project_id))


@router.post('/{project_id}/routes', response_model=RoutingResponse | SavedCircuitResponse | CircuitPlanningResponse, status_code=201)
def post_routes(project_id: Annotated[int, Path(gt=0)], payload: RoutingRequest | CircuitSaveRequest | CircuitPlanningRequest, response: Response, user: User = Depends(require_roles('DESIGNER')), session: Session = Depends(get_db)):
    if isinstance(payload, CircuitSaveRequest):
        return execute(session, lambda: save_circuit(session, user, project_id, payload))
    if isinstance(payload, CircuitPlanningRequest):
        # Preserve legacy route creation. Circuit requests return a preview,
        # never a misleading 201 or a persisted singleton-route replacement.
        response.status_code = 200
        return execute(session, lambda: preview_circuit(session, user, project_id, payload))
    return execute(session, lambda: create_route(session, user, project_id, payload))
