"""Strict local-VLM floor-plan interpretation boundary."""

from app.ai.floor_plan_interpretation.candidate import (
    CandidateContractError,
    CandidateHostProvenance,
    FloorPlanInterpretationCandidate,
    FloorPlanInterpretationPayload,
    InferenceParameter,
    build_candidate_envelope,
    parse_candidate_payload_json,
    review_record_identity,
)
from app.ai.floor_plan_interpretation.corpus_intake import (
    CorpusIntakeError,
    CorpusIntakeRequest,
    PageIntakeMetadata,
    PermissionRecord,
    QualityReviewDecision,
    build_private_corpus_manifest,
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
    "InferenceParameter",
    "build_candidate_envelope",
    "parse_candidate_payload_json",
    "review_record_identity",
    "CorpusIntakeError",
    "CorpusIntakeRequest",
    "PageIntakeMetadata",
    "PermissionRecord",
    "QualityReviewDecision",
    "build_private_corpus_manifest",
    "DemoCVError",
    "DemoCVParameters",
    "interpret_floor_plan_demo",
]
