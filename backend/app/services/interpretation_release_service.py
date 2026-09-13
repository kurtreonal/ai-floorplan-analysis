"""Versioned local interpretation release, shadow, promotion and rollback controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InterpretationRelease


LOCAL_PROVIDER = "local_vlm_gateway"
MANUAL_REVIEW_PROVIDER = "manual_review_required"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class InterpretationReleaseError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PromotionEvidence:
    """Evidence supplied by the release-review workflow.

    This object intentionally does not manufacture a signature.  The caller
    must provide a private VED decision reference and its digest; actual human
    approval remains a release gate outside synthetic tests.
    """

    manifest_sha256: str
    evaluation_report_sha256: str
    signed_decision_ref: str
    signed_decision_sha256: str
    metrics_passed: bool
    schema_passed: bool
    privacy_passed: bool
    resource_passed: bool
    rollback_target_release_id: str | None = None


def _require_sha(value: str, code: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise InterpretationReleaseError(code)
    return value


def _validate_release_id(value: str) -> str:
    if not isinstance(value, str) or not _RELEASE_ID.fullmatch(value):
        raise InterpretationReleaseError("RELEASE_ID_INVALID")
    return value


def _canonical_report(report: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(report, Mapping):
        raise InterpretationReleaseError("SHADOW_REPORT_INVALID")
    try:
        serialized = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError):
        raise InterpretationReleaseError("SHADOW_REPORT_INVALID") from None
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def register_release(
    session: Session,
    *,
    release_id: str,
    provider: str,
    model_revision: str,
    manifest_sha256: str,
    adapter_revision: str | None = None,
    evaluation_report_sha256: str | None = None,
    created_by_user_id: int | None = None,
) -> InterpretationRelease:
    """Register a frozen candidate without making it executable."""
    _validate_release_id(release_id)
    if provider != LOCAL_PROVIDER:
        raise InterpretationReleaseError("RELEASE_PROVIDER_UNSUPPORTED")
    if not isinstance(model_revision, str) or not model_revision.strip() or len(model_revision) > 128:
        raise InterpretationReleaseError("RELEASE_MODEL_REVISION_INVALID")
    _require_sha(manifest_sha256, "RELEASE_MANIFEST_SHA256_INVALID")
    if evaluation_report_sha256 is not None:
        _require_sha(evaluation_report_sha256, "RELEASE_EVALUATION_SHA256_INVALID")
    row = InterpretationRelease(
        release_id=release_id,
        provider=provider,
        model_revision=model_revision.strip(),
        adapter_revision=adapter_revision,
        manifest_sha256=manifest_sha256,
        evaluation_report_sha256=evaluation_report_sha256,
        status="registered",
        created_by_user_id=created_by_user_id,
    )
    try:
        session.add(row)
        session.flush()
    except IntegrityError:
        session.rollback()
        raise InterpretationReleaseError("RELEASE_ALREADY_REGISTERED") from None
    return row


def record_shadow_result(
    session: Session,
    *,
    release_id: str,
    report: Mapping[str, Any],
    evaluation_report_sha256: str | None = None,
) -> InterpretationRelease:
    """Persist a non-authoritative shadow result and its exact digest."""
    serialized, digest = _canonical_report(report)
    if evaluation_report_sha256 is not None and _require_sha(
        evaluation_report_sha256, "RELEASE_EVALUATION_SHA256_INVALID"
    ) != digest:
        raise InterpretationReleaseError("SHADOW_REPORT_HASH_MISMATCH")
    row = _lock_release(session, release_id)
    if row.status not in ("registered", "shadow"):
        raise InterpretationReleaseError("RELEASE_SHADOW_STATE_INVALID")
    row.status = "shadow"
    row.shadow_report_json = serialized
    row.shadow_report_sha256 = digest
    row.evaluation_report_sha256 = digest
    row.shadowed_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    return row


def build_shadow_report(
    *,
    vlm_result: Mapping[str, Any],
    legacy_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a deterministic, non-authoritative VLM/legacy comparison report.

    The inputs are outputs from the approved evaluation harness.  This helper
    never invents legacy metrics: when YOLO weights/results are unavailable it
    records that limitation and leaves discrepancies empty.
    """
    if not isinstance(vlm_result, Mapping):
        raise InterpretationReleaseError("SHADOW_VLM_RESULT_INVALID")
    if legacy_result is not None and not isinstance(legacy_result, Mapping):
        raise InterpretationReleaseError("SHADOW_LEGACY_RESULT_INVALID")
    discrepancies: dict[str, dict[str, float]] = {}
    if legacy_result is not None:
        for key in sorted(set(vlm_result).intersection(legacy_result)):
            candidate = vlm_result[key]
            baseline = legacy_result[key]
            if isinstance(candidate, (int, float)) and isinstance(baseline, (int, float)):
                discrepancies[key] = {
                    "vlm": float(candidate),
                    "legacy": float(baseline),
                    "absolute_delta": abs(float(candidate) - float(baseline)),
                }
    return {
        "status": "compared" if legacy_result is not None else "legacy_unavailable",
        "vlm": dict(vlm_result),
        "legacy": dict(legacy_result) if legacy_result is not None else None,
        "discrepancies": discrepancies,
    }


def promote_release(
    session: Session,
    *,
    release_id: str,
    evidence: PromotionEvidence,
) -> InterpretationRelease:
    """Activate a shadowed release only when every hard gate is explicit."""
    row = _lock_release(session, release_id)
    if row.status != "shadow":
        raise InterpretationReleaseError("RELEASE_NOT_SHADOWED")
    if evidence.manifest_sha256 != row.manifest_sha256:
        raise InterpretationReleaseError("RELEASE_MANIFEST_MISMATCH")
    if row.evaluation_report_sha256 != evidence.evaluation_report_sha256:
        raise InterpretationReleaseError("RELEASE_EVALUATION_MISMATCH")
    _require_sha(evidence.evaluation_report_sha256, "RELEASE_EVALUATION_SHA256_INVALID")
    if not evidence.signed_decision_ref.strip():
        raise InterpretationReleaseError("SIGNED_RELEASE_DECISION_REQUIRED")
    _require_sha(evidence.signed_decision_sha256, "SIGNED_RELEASE_DECISION_HASH_INVALID")
    if not all((evidence.metrics_passed, evidence.schema_passed, evidence.privacy_passed, evidence.resource_passed)):
        raise InterpretationReleaseError("RELEASE_GATES_FAILED")

    active = session.scalar(
        select(InterpretationRelease)
        .where(InterpretationRelease.active_marker.is_(True))
        .with_for_update()
    )
    if active is not None and active.id != row.id:
        row.rollback_target_release_id = evidence.rollback_target_release_id or active.release_id
        active.status = "retired"
        active.active_marker = None
        # Clear the unique active marker before assigning it to the candidate;
        # this ordering is required by both MySQL and SQLite.
        session.flush()
    elif evidence.rollback_target_release_id:
        row.rollback_target_release_id = evidence.rollback_target_release_id
    row.status = "active"
    row.active_marker = True
    row.signed_decision_ref = evidence.signed_decision_ref.strip()
    row.signed_decision_sha256 = evidence.signed_decision_sha256
    row.activated_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    return row


def rollback_release(
    session: Session,
    *,
    release_id: str,
    reason: str,
    target_release_id: str | None = None,
) -> InterpretationRelease:
    """Fence a bad active release and restore a retained target or manual review."""
    if not isinstance(reason, str) or not reason.strip():
        raise InterpretationReleaseError("ROLLBACK_REASON_REQUIRED")
    row = _lock_release(session, release_id)
    if row.status != "active" or row.active_marker is not True:
        raise InterpretationReleaseError("RELEASE_NOT_ACTIVE")
    target_id = target_release_id or row.rollback_target_release_id
    target = None
    if target_id is not None:
        target = _lock_release(session, target_id)
        if target.id == row.id or target.status not in ("retired", "rolled_back"):
            raise InterpretationReleaseError("ROLLBACK_TARGET_INVALID")
        if target.provider != LOCAL_PROVIDER:
            raise InterpretationReleaseError("ROLLBACK_TARGET_INVALID")
    row.status = "rolled_back" if target is not None else "manual_review"
    row.active_marker = None
    row.rollback_reason = reason.strip()[:1000]
    row.rolled_back_at = datetime.now(UTC).replace(tzinfo=None)
    if target is not None:
        session.flush()
        target.status = "active"
        target.active_marker = True
        target.activated_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    return row


def current_runtime_release(session: Session) -> InterpretationRelease | None:
    """Return the active release, or the manual-review fence after rollback."""
    active = session.scalar(
        select(InterpretationRelease)
        .where(InterpretationRelease.active_marker.is_(True), InterpretationRelease.status == "active")
        .order_by(InterpretationRelease.id.desc())
        .limit(1)
    )
    if active is not None:
        return active
    return session.scalar(
        select(InterpretationRelease)
        .where(InterpretationRelease.status == "manual_review")
        .order_by(InterpretationRelease.id.desc())
        .limit(1)
    )


def _lock_release(session: Session, release_id: str) -> InterpretationRelease:
    _validate_release_id(release_id)
    row = session.scalar(
        select(InterpretationRelease)
        .where(InterpretationRelease.release_id == release_id)
        .with_for_update()
    )
    if row is None:
        raise InterpretationReleaseError("RELEASE_NOT_FOUND")
    return row
