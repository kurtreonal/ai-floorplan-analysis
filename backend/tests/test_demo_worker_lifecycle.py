import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.main import lifespan
from app.workers.interpretation_worker import run_interpretation_worker


class InterpretationWorkerLifecycleTests(unittest.TestCase):
    def test_default_starts_only_in_development(self):
        self.assertTrue(
            Settings.model_fields["auto_start_interpretation_worker"].default
        )
        for environment, enabled in (("production", True), ("development", False)):
            app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
                app_env=environment, auto_start_interpretation_worker=enabled,
            )))
            async def exercise():
                async with lifespan(app):
                    pass
            with patch("app.main.threading.Thread") as worker:
                asyncio.run(exercise())
                worker.assert_not_called()

    def test_development_starts_once_and_signals_shutdown(self):
        settings = SimpleNamespace(app_env="development", auto_start_interpretation_worker=True)
        app = SimpleNamespace(state=SimpleNamespace(settings=settings))
        async def exercise():
            async with lifespan(app):
                worker.return_value.start.assert_called_once()
                self.assertFalse(worker.call_args.kwargs["kwargs"]["stop_event"].is_set())
        with patch("app.main.threading.Thread") as worker, patch(
            "app.main.asyncio.to_thread", new=AsyncMock(side_effect=lambda call, *args: call(*args))
        ):
            asyncio.run(exercise())
            self.assertIs(worker.call_args.kwargs["target"], run_interpretation_worker)
            self.assertEqual(worker.call_args.kwargs["name"], "ved-interpretation-worker")
            self.assertTrue(worker.call_args.kwargs["kwargs"]["stop_event"].is_set())
            worker.return_value.join.assert_called_once_with(5)

    def test_idle_worker_stops_without_claiming_or_processing_a_job(self):
        stop = threading.Event()
        factory = MagicMock()
        settings = object()
        with patch("app.workers.interpretation_worker._next_queued_job_id", return_value=None), patch(
            "app.workers.interpretation_worker.process_interpretation_job"
        ) as process, patch.object(stop, "wait", side_effect=lambda _: stop.set()):
            run_interpretation_worker(stop_event=stop, worker_identity="test-worker", session_factory=factory, settings=settings)
        process.assert_not_called()
        factory.assert_called_once()
