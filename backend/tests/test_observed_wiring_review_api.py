"""Synthetic machine wiring follows the real append-only review/save API."""
from tests import test_demo_interpretation_api as fixture
from app.ai.floor_plan_interpretation.candidate import (
    FloorPlanInterpretationPayload, ObservedRoutes, ObservedRouteSegment, PixelPoint,
)


class ObservedWiringReviewApiTests(fixture.DemoInterpretationApiTests):
    @staticmethod
    def candidate_payload():
        base = fixture.DemoInterpretationApiTests.candidate_payload()
        routes = ObservedRoutes(state="partial", segments=(ObservedRouteSegment(
            id="segment-0001", points=(PixelPoint(x=20, y=30), PixelPoint(x=80, y=90)),
            evidence_refs=("region:region-0001",), ambiguity="ambiguous",
        ),))
        values = base.model_dump(mode="json")
        values["document_state"] = "partial"
        values["observed_routes"] = routes.model_dump(mode="json")
        return FloorPlanInterpretationPayload.model_validate(values)

    def _review_payload(self, *args, **kwargs):
        payload = super()._review_payload(*args, **kwargs)
        payload["observed_wiring"] = [{
            "id": "segment-0001", "disposition": "rejected",
            "points": [{"x": 20., "y": 30.}, {"x": 80., "y": 90.}],
            "completeness": "complete", "elevation_meters": None,
        }]
        return payload

    def test_observed_wiring_revision_save_reload_and_elevation_gate(self):
        # The inherited test replaces the wiring collection with a manual route;
        # exercise actual machine identity coverage separately instead.
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload()
        wire = payload["observed_wiring"][0]
        wire.update(disposition="corrected", elevation_meters=2.8)
        wire["points"][1]["x"] = 100.
        saved = self.client.post(path, json=payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        loaded = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertIn('segment-0001', loaded.text)
        payload["expected_revision_number"] = 1
        payload["observed_wiring"] = []
        rejected = self.client.post(path, json=payload)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(rejected.json()["detail"]["error"]["code"], "REVIEW_INCOMPLETE")
        from uuid import uuid4
        saved_layout = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={"candidate_run_id": self.candidate.provenance.candidate_run_id,
                  "review_revision_number": 1, "expected_layout_version_number": None,
                  "idempotency_key": str(uuid4())},
        )
        self.assertEqual(saved_layout.status_code, 201, saved_layout.text)
        self.assertEqual(saved_layout.json()["geometry"]["routes"][0]["points"][1]["x"], 1.)
        self.assertEqual(saved_layout.json()["extension"]["route_details"][0]["route_kind"], "observed")
