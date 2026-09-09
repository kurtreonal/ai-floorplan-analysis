"""Strict local-VLM floor-plan interpretation boundary."""

from app.ai.floor_plan_interpretation.candidate import (
    CandidateContractError,
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
    FloorPlanInterpretationPayload,
    build_candidate_envelope,
    parse_candidate_payload_json,
    review_record_identity,
)
from app.ai.floor_plan_interpretation.demo_cv import (
    DemoCVError,
    DemoCVParameters,
    interpret_floor_plan_demo,
)

__all__ = [
    "CandidateContractError",
    "CandidateHostProvenance",
    "FloorPlanInterpretationCandidate",
    "FloorPlanInterpretationPayload",
    "build_candidate_envelope",
    "parse_candidate_payload_json",
    "review_record_identity",
    "DemoCVError",
    "DemoCVParameters",
    "interpret_floor_plan_demo",
]
