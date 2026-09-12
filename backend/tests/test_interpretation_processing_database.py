"""Run the actual interpretation worker through the isolated MySQL fixture."""
from tests import test_demo_processing_worker as fixture
from app.services.interpretation_processing_service import process_interpretation_job


class InterpretationProcessingDatabaseTests(fixture.DemoProcessingWorkerTests):
    process = staticmethod(process_interpretation_job)
