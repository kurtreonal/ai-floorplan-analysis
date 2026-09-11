import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.main import lifespan
from app.workers.demo_worker import run_demo_worker


class DemoWorkerLifecycleTests(unittest.TestCase):
    def test_default_and_production_never_start_demo_processing(self):
        self.assertFalse(Settings(_env_file=None).auto_start_demo_worker)
        for environment, enabled in (("production", True), ("development", False)):
            app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
                app_env=environment, auto_start_demo_worker=enabled,
            )))
            async def exercise():
                async with lifespan(app):
                    pass
            with patch("app.main.threading.Thread") as worker:
                asyncio.run(exercise())
                worker.assert_not_called()

    def test_opted_in_development_starts_once_and_signals_shutdown(self):
        settings = SimpleNamespace(app_env="development", auto_start_demo_worker=True)
        app = SimpleNamespace(state=SimpleNamespace(settings=settings))
        async def exercise():
            async with lifespan(app):
                worker.return_value.start.assert_called_once()
                self.assertFalse(worker.call_args.kwargs["kwargs"]["stop_event"].is_set())
        with patch("app.main.threading.Thread") as worker, patch(
            "app.main.asyncio.to_thread", new=AsyncMock(side_effect=lambda call, *args: call(*args))
        ):
            asyncio.run(exercise())
            self.assertTrue(worker.call_args.kwargs["kwargs"]["stop_event"].is_set())
            worker.return_value.join.assert_called_once_with(5)

    def test_idle_worker_stops_without_claiming_or_processing_a_job(self):
        stop = threading.Event()
        factory = MagicMock()
        settings = object()
        with patch("app.workers.demo_worker._next_queued_job_id", return_value=None), patch(
            "app.workers.demo_worker.process_demo_job"
        ) as process, patch.object(stop, "wait", side_effect=lambda _: stop.set()):
            run_demo_worker(stop_event=stop, worker_identity="test-worker", session_factory=factory, settings=settings)
        process.assert_not_called()
        factory.assert_called_once()
