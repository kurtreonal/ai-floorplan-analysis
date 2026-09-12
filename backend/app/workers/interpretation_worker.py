from __future__ import annotations

import argparse
import os
import threading
import time
from collections.abc import Callable

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import ProcessingJob
from app.services.interpretation_processing_service import InterpretationProcessingError, process_interpretation_job


def _next_queued_job_id(session) -> int | None:
    return session.scalar(
        select(ProcessingJob.id)
        .where(
            ProcessingJob.job_type == "floor_plan_analysis",
            ProcessingJob.status == "queued",
        )
        .order_by(ProcessingJob.created_at.asc(), ProcessingJob.id.asc())
        .limit(1)
    )


def run_interpretation_worker(
    *,
    stop_event: threading.Event,
    worker_identity: str,
    poll_seconds: float = 1.0,
    session_factory: Callable | None = None,
    settings=None,
) -> None:
    factory = session_factory or get_session_factory()
    worker_settings = settings or get_settings()
    while not stop_event.is_set():
        try:
            with factory() as session:
                job_id = _next_queued_job_id(session)
                if job_id is not None:
                    try:
                        run = process_interpretation_job(
                            session,
                            job_id=job_id,
                            worker_identity=worker_identity,
                            settings=worker_settings,
                        )
                    except InterpretationProcessingError as error:
                        print(
                            f"job_id={job_id} status=failed code={error.code}",
                            flush=True,
                        )
                    else:
                        print(
                            f"job_id={job_id} status=completed "
                            f"candidate_run_id={run.candidate_run_id}",
                            flush=True,
                        )
        except Exception as error:
            print(f"demo worker unavailable: {type(error).__name__}", flush=True)
        stop_event.wait(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded local demo worker.")
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    arguments = parser.parse_args()
    if arguments.job_id is not None and arguments.job_id <= 0:
        parser.error("--job-id must be positive")
    if not 0.2 <= arguments.poll_seconds <= 30:
        parser.error("--poll-seconds must be between 0.2 and 30")

    worker_identity = f"demo-worker:{os.getpid()}"
    session_factory = get_session_factory()
    settings = get_settings()
    requested_job_id = arguments.job_id
    while True:
        with session_factory() as session:
            job_id = requested_job_id or _next_queued_job_id(session)
            if job_id is not None:
                try:
                    run = process_interpretation_job(
                        session,
                        job_id=job_id,
                        worker_identity=worker_identity,
                        settings=settings,
                    )
                except InterpretationProcessingError as error:
                    print(f"job_id={job_id} status=failed code={error.code}", flush=True)
                    if requested_job_id is not None:
                        return 1
                else:
                    print(
                        f"job_id={job_id} status=completed candidate_run_id={run.candidate_run_id}",
                        flush=True,
                    )
                    if requested_job_id is not None:
                        return 0
        if arguments.once:
            return 0
        time.sleep(arguments.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
