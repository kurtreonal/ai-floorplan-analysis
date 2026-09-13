from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FloorPlanPage, InterpretationPageOutcome, ProcessingJob
from app.repositories.interpretation_page_outcome_repository import (
    list_page_outcomes,
    list_pages_for_floor_plan,
)


class PageSelectionError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def configure_page_outcomes(
    session: Session,
    *,
    processing_job: ProcessingJob,
    page_numbers: list[int] | tuple[int, ...] | None,
) -> list[InterpretationPageOutcome]:
    pages = list_pages_for_floor_plan(session, floor_plan_id=processing_job.floor_plan_id)
    if not pages:
        raise PageSelectionError("PROCESSING_PAGES_NOT_FOUND")
    available = {page.page_number: page for page in pages}
    selected = set(available) if page_numbers is None else set(page_numbers)
    if not selected or len(selected) != len(page_numbers or selected):
        raise PageSelectionError("PROCESSING_PAGE_SELECTION_INVALID")
    if not selected.issubset(available):
        raise PageSelectionError("PROCESSING_PAGE_NOT_FOUND")
    existing = list_page_outcomes(session, processing_job_id=processing_job.id)
    if existing:
        if {row.page_number for row in existing if row.selection_state == "selected"} != selected:
            raise PageSelectionError("PROCESSING_PAGE_SELECTION_IMMUTABLE")
        return existing
    outcomes = []
    for number, page in sorted(available.items()):
        is_selected = number in selected
        outcomes.append(InterpretationPageOutcome(
            processing_job_id=processing_job.id,
            floor_plan_page_id=page.id,
            page_number=number,
            selection_state="selected" if is_selected else "skipped",
            status="queued" if is_selected else "skipped",
            progress=0 if is_selected else 100,
            failure_code=None if is_selected else "PAGE_NOT_SELECTED",
        ))
    session.add_all(outcomes)
    session.flush()
    return outcomes


def next_selected_page(session: Session, *, processing_job_id: int) -> InterpretationPageOutcome | None:
    return session.scalar(select(InterpretationPageOutcome)
        .where(InterpretationPageOutcome.processing_job_id == processing_job_id,
               InterpretationPageOutcome.selection_state == "selected",
               InterpretationPageOutcome.status == "queued")
        .order_by(InterpretationPageOutcome.page_number.asc()).limit(1).with_for_update())


def has_open_selected_pages(session: Session, *, processing_job_id: int) -> bool:
    return session.scalar(select(func.count()).select_from(InterpretationPageOutcome).where(
        InterpretationPageOutcome.processing_job_id == processing_job_id,
        InterpretationPageOutcome.selection_state == "selected",
        InterpretationPageOutcome.status.in_(("queued", "processing")),
    )) > 0


def requeue_retryable_pages(
    session: Session, *, processing_job_id: int
) -> int:
    """Make a failed/abandoned selected page eligible for its next PRE9 attempt."""
    rows = session.scalars(
        select(InterpretationPageOutcome)
        .where(
            InterpretationPageOutcome.processing_job_id == processing_job_id,
            InterpretationPageOutcome.selection_state == "selected",
            InterpretationPageOutcome.status.in_(("failed", "timeout", "processing")),
        )
        .with_for_update()
    ).all()
    for row in rows:
        row.status = "queued"
        row.progress = 0
        row.failure_code = None
        row.candidate_run_id = None
        row.source_artifact_id = None
    return len(rows)
