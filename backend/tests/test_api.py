import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402
from graph_builder import ward_ids  # noqa: E402


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.ward = ward_ids()[0]

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_wards_listed_with_patterns(self):
        data = self.client.get("/api/wards").get_json()
        self.assertEqual({w["id"] for w in data["wards"]}, set(ward_ids()))
        self.assertIn("burst", data["patterns"])

    def test_ward_detail_is_index_aligned_with_simulation(self):
        detail = self.client.get(f"/api/wards/{self.ward}").get_json()
        body = {"ward": self.ward, "pattern": "burst", "intensity": 60}
        sim = self.client.post("/api/simulate", json=body).get_json()
        self.assertEqual(len(sim["frames"][0]["depth"]), len(detail["roads"]))
        self.assertEqual(len(sim["frames"][0]["load"]), len(detail["drainage_nodes"]))
        self.assertEqual([r["id"] for r in sim["roads"]], [r["id"] for r in detail["roads"]])

    def test_simulate_is_gzipped_when_accepted(self):
        res = self.client.post("/api/simulate", json={"ward": self.ward}, headers={"Accept-Encoding": "gzip"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Encoding"), "gzip")

    def test_predict_compat_endpoint(self):
        res = self.client.post("/api/predict", json={"ward": self.ward, "rainfall_intensity": 60, "timeline": 2})
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(data["timeline_hours"], 2)
        self.assertIn(data["roads"][0]["flood_risk"], {"low", "moderate", "high", "critical"})

    def test_route_between_two_points(self):
        meta = next(w for w in self.client.get("/api/wards").get_json()["wards"] if w["id"] == self.ward)
        s, w, n, e = meta["bbox"]
        body = {"ward": self.ward, "intensity": 30, "frame": 6,
                "start": [s + 0.25 * (n - s), w + 0.25 * (e - w)], "end": [s + 0.75 * (n - s), w + 0.75 * (e - w)]}
        data = self.client.post("/api/route", json=body).get_json()
        self.assertGreater(data["normal"]["length_km"], 0)
        self.assertEqual(data["t"], 30)

    def test_rejects_bad_input(self):
        cases = [
            ("/api/simulate", {"ward": "atlantis"}),
            ("/api/simulate", {"pattern": "tsunami"}),
            ("/api/simulate", {"intensity": "lots"}),
            ("/api/route", {"ward": self.ward, "start": "here"}),
        ]
        for path, body in cases:
            res = self.client.post(path, json=body)
            self.assertEqual(res.status_code, 400, body)
            self.assertIn("error", res.get_json())

    def test_unknown_endpoint_is_json_404(self):
        res = self.client.get("/api/nope")
        self.assertEqual(res.status_code, 404)
        self.assertIn("error", res.get_json())


if __name__ == "__main__":
    unittest.main()
