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
from app.ai.floor_plan_interpretation.corpus_intake import (
    CorpusIntakeError,
    CorpusIntakeRequest,
    PermissionRecord,
    build_private_corpus_manifest,
)

__all__ = [
    "CandidateContractError",
    "CandidateHostProvenance",
    "FloorPlanInterpretationCandidate",
    "FloorPlanInterpretationPayload",
    "build_candidate_envelope",
    "parse_candidate_payload_json",
    "review_record_identity",
    "CorpusIntakeError",
    "CorpusIntakeRequest",
    "PermissionRecord",
    "build_private_corpus_manifest",
]
