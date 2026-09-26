"""Integrity checks on the committed ward datasets, so a bad rebuild fails CI instead of the demo."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import networkx as nx  # noqa: E402

from graph_builder import DATA_DIR, load_index, load_ward  # noqa: E402

REQUIRED_FILES = ["roads.geojson", "drainage_nodes.json", "drainage_edges.json", "elevation.json", "boundary.geojson"]


class DataTests(unittest.TestCase):
    def test_every_ward_has_all_files(self):
        for meta in load_index()["wards"]:
            for name in REQUIRED_FILES:
                path = DATA_DIR / "wards" / meta["id"] / name
                self.assertTrue(path.exists(), path)
                json.loads(path.read_text(encoding="utf-8"))

    def test_wards_are_consistent(self):
        for meta in load_index()["wards"]:
            with self.subTest(ward=meta["id"]):
                ward = load_ward(meta["id"])
                node_ids = {n["id"] for n in ward.drain_nodes}
                road_ids = [s["id"] for s in ward.segments]

                self.assertEqual(len(road_ids), meta["road_count"])
                self.assertEqual(len(road_ids), len(set(road_ids)), "duplicate road ids")
                self.assertTrue(all(s["nearest_drain"] in node_ids for s in ward.segments))
                self.assertTrue(all(e["from"] in node_ids and e["to"] in node_ids for e in ward.drain_edges))
                self.assertTrue(nx.is_directed_acyclic_graph(ward.drainage))
                self.assertGreater(sum(1 for n in ward.drain_nodes if n["type"] == "outfall"), 0)
                self.assertTrue(all(n["capacity"] > 0 for n in ward.drain_nodes))
                self.assertTrue(nx.is_connected(nx.Graph(ward.road_graph)), "street network is split")

    def test_geometry_inside_ward(self):
        pad = 0.002
        for meta in load_index()["wards"]:
            s, w, n, e = meta["bbox"]
            ward = load_ward(meta["id"])
            for seg in ward.segments:
                for lon, lat in seg["coords"]:
                    self.assertTrue(s - pad <= lat <= n + pad and w - pad <= lon <= e + pad, (meta["id"], seg["id"]))


if __name__ == "__main__":
    unittest.main()
