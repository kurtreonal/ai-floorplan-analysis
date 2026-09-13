from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterpretationPageOutcome, ProcessingJob
from app.services.interpretation_release_service import (
    MANUAL_REVIEW_PROVIDER,
    current_runtime_release,
)


DEMO_PROVIDER = "demo_cv_baseline"
LOCAL_PROVIDER = "local_vlm_gateway"


class InterpretationConfigurationError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _safe_release(value: str | None, fallback: str) -> str:
    candidate = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return candidate[:128] or fallback


def requested_configuration(settings) -> tuple[str, str, str]:
    runtime_url = getattr(settings, "local_vlm_runtime_url", None)
    model_path = getattr(settings, "local_vlm_model_path", None)
    if runtime_url is None and model_path is None:
        provider = DEMO_PROVIDER
        release = DEMO_PROVIDER
        values = {"provider": provider, "release": release}
    else:
        provider = LOCAL_PROVIDER
        release = _safe_release(
            getattr(settings, "local_vlm_model_name", None), LOCAL_PROVIDER
        )
        values = {
            "provider": provider,
            "release": release,
            "model_revision": getattr(settings, "local_vlm_model_revision", None),
            "model_path": str(model_path) if model_path is not None else None,
            "adapter_path": (
                str(getattr(settings, "local_vlm_adapter_path", None))
                if getattr(settings, "local_vlm_adapter_path", None) is not None
                else None
            ),
            "runtime_url": runtime_url,
            "timeout_seconds": getattr(settings, "local_vlm_timeout_seconds", None),
        }
    digest = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return provider, release, digest


def pin_job_configuration(
    session: Session, *, processing_job: ProcessingJob, settings
) -> InterpretationPageOutcome:
    active_release = current_runtime_release(session)
    if active_release is not None and active_release.status == "manual_review":
        provider = MANUAL_REVIEW_PROVIDER
        release = "manual_review"
        values = {
            "provider": provider,
            "release": release,
            "rollback_reason": active_release.rollback_reason,
        }
        digest = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    elif active_release is not None:
        provider = active_release.provider
        release = active_release.release_id
        values = {
            "provider": provider,
            "release": release,
            "model_revision": active_release.model_revision,
            "adapter_revision": active_release.adapter_revision,
            "manifest_sha256": active_release.manifest_sha256,
            "evaluation_report_sha256": active_release.evaluation_report_sha256,
        }
        digest = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    else:
        provider, release, digest = requested_configuration(settings)
    current = session.scalar(
        select(InterpretationPageOutcome)
        .where(InterpretationPageOutcome.processing_job_id == processing_job.id)
        .order_by(InterpretationPageOutcome.page_number.asc())
        .with_for_update()
    )
    if current is None:
        raise InterpretationConfigurationError("PROCESSING_PAGES_NOT_FOUND")
    if current is not None:
        if current.configuration_sha256 is not None and current.configuration_sha256 != digest:
            raise InterpretationConfigurationError(
                "PROCESSING_CONFIGURATION_CONFLICT"
            )
        if current.configuration_sha256 is None:
            outcomes = session.scalars(
                select(InterpretationPageOutcome)
                .where(InterpretationPageOutcome.processing_job_id == processing_job.id)
                .with_for_update()
            ).all()
            for outcome in outcomes:
                outcome.provider = provider
                outcome.model_release_id = release
                outcome.configuration_sha256 = digest
    session.flush()
    return current
