from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DatasetApproverAssignment, User
from app.repositories import dataset_approver_assignment_repository as repository
from app.schemas.dataset_approver_assignment import DatasetApproverAssignmentWrite


ERROR_MESSAGES = {
    "DATASET_APPROVER_ASSIGNMENTS_RETRIEVAL_FAILED": (
        "Dataset-approver assignments could not be retrieved."
    ),
    "DATASET_APPROVER_ASSIGNEE_NOT_FOUND": "The assignee was not found.",
    "DATASET_APPROVER_ASSIGNMENT_NOT_FOUND": "The assignment was not found.",
    "DATASET_APPROVER_ASSIGNMENT_CONFLICT": (
        "An active dataset approver is already assigned."
    ),
    "DATASET_APPROVER_SELF_ASSIGNMENT_DENIED": (
        "An Admin cannot assign themselves as dataset approver."
    ),
    "DATASET_APPROVER_ASSIGNMENT_WRITE_FAILED": (
        "The dataset-approver assignment could not be saved."
    ),
}


class DatasetApproverAssignmentServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class SafeDatasetApproverAssignment:
    assignment_id: int
    assignee_user_id: int
    authority_scope: Literal["VED_AI_DATASET_APPROVER"]
    active_from: datetime


@dataclass(frozen=True)
class ManagedDatasetApproverAssignment(SafeDatasetApproverAssignment):
    qualification_category: Literal["PEE", "SENIOR_REE"]
    professional_reference: str
    assigned_by_user_id: int
    deactivated_by_user_id: int | None
    inactive_at: datetime | None
    is_active: bool


def _safe(
    assignment: DatasetApproverAssignment,
) -> SafeDatasetApproverAssignment:
    return SafeDatasetApproverAssignment(
        assignment_id=assignment.id,
        assignee_user_id=assignment.assignee_user_id,
        authority_scope=cast(
            Literal["VED_AI_DATASET_APPROVER"],
            assignment.authority_scope,
        ),
        active_from=assignment.active_from,
    )


def _managed(
    assignment: DatasetApproverAssignment,
) -> ManagedDatasetApproverAssignment:
    return ManagedDatasetApproverAssignment(
        **_safe(assignment).__dict__,
        qualification_category=cast(
            Literal["PEE", "SENIOR_REE"],
            assignment.qualification_category,
        ),
        professional_reference=assignment.professional_reference,
        assigned_by_user_id=assignment.assigned_by_user_id,
        deactivated_by_user_id=assignment.deactivated_by_user_id,
        inactive_at=assignment.inactive_at,
        is_active=assignment.active_marker is True,
    )


def retrieve_current_dataset_approver(
    database_session: Session,
) -> SafeDatasetApproverAssignment | None:
    try:
        assignment = repository.find_current_assignment(database_session)
        return _safe(assignment) if assignment is not None else None
    except SQLAlchemyError:
        database_session.rollback()
        raise DatasetApproverAssignmentServiceError(
            "DATASET_APPROVER_ASSIGNMENTS_RETRIEVAL_FAILED"
        ) from None


def retrieve_dataset_approver_history(
    database_session: Session,
) -> tuple[ManagedDatasetApproverAssignment, ...]:
    try:
        return tuple(_managed(item) for item in repository.list_assignments(database_session))
    except SQLAlchemyError:
        database_session.rollback()
        raise DatasetApproverAssignmentServiceError(
            "DATASET_APPROVER_ASSIGNMENTS_RETRIEVAL_FAILED"
        ) from None


def create_dataset_approver_assignment(
    database_session: Session,
    *,
    current_user: User,
    data: DatasetApproverAssignmentWrite,
) -> ManagedDatasetApproverAssignment:
    if current_user.id == data.assignee_user_id:
        raise DatasetApproverAssignmentServiceError(
            "DATASET_APPROVER_SELF_ASSIGNMENT_DENIED"
        )
    try:
        if repository.find_eligible_assignee(
            database_session,
            user_id=data.assignee_user_id,
        ) is None:
            raise DatasetApproverAssignmentServiceError(
                "DATASET_APPROVER_ASSIGNEE_NOT_FOUND"
            )
        if repository.find_current_assignment(database_session) is not None:
            raise DatasetApproverAssignmentServiceError(
                "DATASET_APPROVER_ASSIGNMENT_CONFLICT"
            )
        assignment = repository.add_and_flush(
            database_session,
            DatasetApproverAssignment(
                assignee_user_id=data.assignee_user_id,
                assigned_by_user_id=current_user.id,
                qualification_category=data.qualification_category,
                professional_reference=data.professional_reference,
                authority_scope="VED_AI_DATASET_APPROVER",
                active_marker=True,
            ),
        )
        database_session.commit()
        database_session.refresh(assignment)
        return _managed(assignment)
    except DatasetApproverAssignmentServiceError:
        database_session.rollback()
        raise
    except IntegrityError:
        database_session.rollback()
        raise DatasetApproverAssignmentServiceError(
            "DATASET_APPROVER_ASSIGNMENT_CONFLICT"
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise DatasetApproverAssignmentServiceError(
            "DATASET_APPROVER_ASSIGNMENT_WRITE_FAILED"
        ) from None


def deactivate_dataset_approver_assignment(
    database_session: Session,
    *,
    current_user: User,
    assignment_id: int,
) -> ManagedDatasetApproverAssignment:
    try:
        assignment = repository.find_assignment(
            database_session,
            assignment_id=assignment_id,
            lock=True,
        )
        if assignment is None:
            raise DatasetApproverAssignmentServiceError(
                "DATASET_APPROVER_ASSIGNMENT_NOT_FOUND"
            )
        if assignment.active_marker is None:
            database_session.rollback()
            return _managed(assignment)
        assignment.active_marker = None
        assignment.inactive_at = datetime.now(UTC).replace(tzinfo=None)
        assignment.deactivated_by_user_id = current_user.id
        database_session.commit()
        database_session.refresh(assignment)
        return _managed(assignment)
    except DatasetApproverAssignmentServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise DatasetApproverAssignmentServiceError(
            "DATASET_APPROVER_ASSIGNMENT_WRITE_FAILED"
        ) from None
