import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import coupling_engine as engine  # noqa: E402
import nowcast_simulator as nowcast  # noqa: E402
from graph_builder import load_ward, ward_ids  # noqa: E402
from routing import plan_routes  # noqa: E402

WARMUP = nowcast.WARMUP_MIN // nowcast.STEP_MIN


def run(ward, pattern="steady", peak=50.0, backwater=False):
    return engine.simulate(ward, nowcast.design_hyetograph(pattern, peak), nowcast.STEP_MIN, WARMUP, backwater)


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ward = load_ward(ward_ids()[0])

    def test_no_rain_no_water(self):
        result = run(self.ward, peak=0.0)
        self.assertEqual(result["stats"][-1]["max_depth"], 0.0)
        self.assertEqual(result["balance"]["rain_m3"], 0.0)

    def test_water_is_conserved(self):
        b = run(self.ward, peak=80.0)["balance"]
        accounted = b["to_outfalls_m3"] + b["on_streets_m3"] + b["left_overland_m3"]
        self.assertAlmostEqual(b["rain_m3"], accounted, delta=b["rain_m3"] * 1e-4 + 1)

    def test_more_rain_floods_more(self):
        light = run(self.ward, peak=20.0)["stats"][-1]
        heavy = run(self.ward, peak=80.0)["stats"][-1]
        self.assertGreater(heavy["flooded_km"], light["flooded_km"])

    def test_backwater_never_helps(self):
        normal = run(self.ward, peak=50.0)["stats"][-1]["flooded_km"]
        blocked = run(self.ward, peak=50.0, backwater=True)["stats"][-1]["flooded_km"]
        self.assertGreaterEqual(blocked, normal)

    def test_frames_cover_three_hours(self):
        result = run(self.ward)
        self.assertEqual(result["frames"][0]["t"], 0)
        self.assertEqual(result["frames"][-1]["t"], nowcast.HORIZON_MIN)
        self.assertEqual(len(result["frames"][0]["depth"]), len(self.ward.segments))

    def test_risk_thresholds(self):
        self.assertEqual(engine.classify_risk(4.9), "low")
        self.assertEqual(engine.classify_risk(5.0), "moderate")
        self.assertEqual(engine.classify_risk(15.0), "high")
        self.assertEqual(engine.classify_risk(30.0), "critical")


class HyetographTests(unittest.TestCase):
    def test_patterns_have_full_length(self):
        for pattern in nowcast.PATTERNS:
            self.assertEqual(len(nowcast.design_hyetograph(pattern, 40)), nowcast.n_steps())

    def test_steady_is_constant(self):
        self.assertEqual(set(nowcast.design_hyetograph("steady", 42)), {42})


class RoutingTests(unittest.TestCase):
    def test_safe_route_avoids_impassable_roads(self):
        ward = load_ward(ward_ids()[0])
        depth = run(ward, peak=100.0)["frames"][-1]["depth"]
        s, w, n, e = ward.meta["bbox"]
        routes = plan_routes(ward, depth, (s + 0.2 * (n - s), w + 0.2 * (e - w)), (s + 0.8 * (n - s), w + 0.8 * (e - w)))
        by_id = {seg["id"]: i for i, seg in enumerate(ward.segments)}
        if routes["safe"]:
            for rid in routes["safe"]["segment_ids"]:
                self.assertLess(depth[by_id[rid]], 30.0)
        self.assertGreater(routes["normal"]["length_km"], 0)


if __name__ == "__main__":
    unittest.main()
