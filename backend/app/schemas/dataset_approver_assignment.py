from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


DatabaseId = Annotated[int, Field(gt=0, le=9_223_372_036_854_775_807)]
ProfessionalReference = Annotated[str, Field(min_length=1, max_length=64)]


class DatasetApproverAssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_user_id: DatabaseId
    qualification_category: Literal["PEE", "SENIOR_REE"]
    professional_reference: ProfessionalReference

    @field_validator("professional_reference")
    @classmethod
    def normalized_professional_reference(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value or any(
            not character.isprintable() for character in value
        ):
            raise ValueError("Professional references must be normalized.")
        return value


class CurrentDatasetApproverAssignment(BaseModel):
    assignment_id: DatabaseId
    assignee_user_id: DatabaseId
    authority_scope: Literal["VED_AI_DATASET_APPROVER"]
    active_from: datetime


class CurrentDatasetApproverResponse(BaseModel):
    assignment: CurrentDatasetApproverAssignment | None


class DatasetApproverAssignmentAdminResponse(CurrentDatasetApproverAssignment):
    qualification_category: Literal["PEE", "SENIOR_REE"]
    professional_reference: ProfessionalReference
    assigned_by_user_id: DatabaseId
    deactivated_by_user_id: DatabaseId | None
    inactive_at: datetime | None
    is_active: bool
