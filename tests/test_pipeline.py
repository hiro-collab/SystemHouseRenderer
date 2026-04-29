from __future__ import annotations

import json
from pathlib import Path
import unittest

from system_house_renderer.pipeline import render_file, render_payload, write_render_output


ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_dify_fixture_generates_expected_outputs(self) -> None:
        output = render_file(ROOT / "examples" / "dify_workflow.json")
        self.assertIn("semanticGraph", output)
        self.assertIn("spatialMap", output)
        self.assertIn("tour", output)
        kinds = {node["kind"] for node in output["semanticGraph"]["nodes"]}
        self.assertTrue({"input", "llm", "knowledge", "external", "output"}.issubset(kinds))
        room_roles = {room["role"] for room in output["spatialMap"]["rooms"]}
        self.assertTrue({"entrance", "thinking_room", "library", "workshop", "exit"}.issubset(room_roles))
        self.assertGreater(len(output["tour"]["steps"]), 0)

    def test_secret_values_do_not_leak(self) -> None:
        payload = {
            "system": {"id": "secret-test", "name": "Secret Test"},
            "components": [
                {"id": "a", "label": "Input", "kind": "input"},
                {
                    "id": "b",
                    "label": "External API",
                    "kind": "external",
                    "api_key": "sk-very-secret-value",
                },
                {"id": "c", "label": "Output", "kind": "output"},
            ],
            "flows": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        }
        output = render_payload(payload)
        text = json.dumps(output, ensure_ascii=False)
        self.assertNotIn("sk-very-secret-value", text)
        self.assertTrue(output["diagnostics"]["hiddenItems"])
        landmarks = output["spatialMap"]["landmarks"]
        self.assertTrue(any(item["type"] == "locked_box" for item in landmarks))

    def test_secret_value_patterns_are_redacted_from_labels_and_summaries(self) -> None:
        secret = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.K7xU9QmV2p4rS8tW0yZaBcDeFgHiJkLmNoPqRsTuVw"
        payload = {
            "system": {"id": "value-secret-test", "name": "Value Secret Test"},
            "components": [
                {"id": "a", "label": f"Input {secret}", "kind": "input"},
                {
                    "id": "b",
                    "label": "External API",
                    "kind": "external",
                    "summary": f"Authorization: Bearer {jwt}",
                },
                {"id": "c", "label": "Output", "kind": "output"},
            ],
            "flows": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        }
        output = render_payload(payload)
        text = json.dumps(output, ensure_ascii=False)
        self.assertNotIn(secret, text)
        self.assertNotIn(jwt, text)
        self.assertIn("[redacted]", text)
        self.assertTrue(output["diagnostics"]["hiddenItems"])
        nodes = {node["id"]: node for node in output["semanticGraph"]["nodes"]}
        self.assertTrue(nodes["a"]["secretPresent"])
        self.assertTrue(nodes["b"]["secretPresent"])
        directory = ROOT / "out" / "test-redact"
        write_render_output(output, directory)
        html = (directory / "index.html").read_text(encoding="utf-8")
        self.assertNotIn(secret, html)
        self.assertNotIn(jwt, html)

    def test_layout_is_deterministic(self) -> None:
        path = ROOT / "examples" / "generic_system.json"
        first = render_file(path)["spatialMap"]
        second = render_file(path)["spatialMap"]
        self.assertEqual(first, second)

    def test_unknown_node_type_does_not_crash(self) -> None:
        payload = {
            "app": {"name": "Unknown Node"},
            "graph": {
                "nodes": [
                    {"id": "start", "data": {"type": "start", "title": "Start"}},
                    {"id": "mystery", "data": {"type": "quantum-widget", "title": "Mystery"}},
                    {"id": "end", "data": {"type": "answer", "title": "Answer"}},
                ],
                "edges": [
                    {"source": "start", "target": "mystery"},
                    {"source": "mystery", "target": "end"},
                ],
            },
        }
        output = render_payload(payload)
        nodes = {node["id"]: node for node in output["semanticGraph"]["nodes"]}
        self.assertEqual(nodes["mystery"]["kind"], "unknown")
        self.assertTrue(
            any(
                warning["code"] == "unknown_component_kind"
                for warning in output["diagnostics"]["warnings"]
            )
        )

    def test_tour_uses_runtime_order_when_available(self) -> None:
        payload = {
            "system": {"name": "Runtime"},
            "components": [
                {"id": "a", "label": "A", "kind": "input"},
                {"id": "b", "label": "B", "kind": "tool"},
                {"id": "c", "label": "C", "kind": "output"},
            ],
            "flows": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
            "runtime": {"events": [{"nodeId": "b"}, {"nodeId": "a"}]},
        }
        output = render_payload(payload)
        focus_order = [step["focusNodeId"] for step in output["tour"]["steps"]]
        self.assertEqual(focus_order, ["b", "a"])

    def test_tour_falls_back_without_runtime(self) -> None:
        payload = {
            "system": {"name": "No Runtime"},
            "components": [
                {"id": "a", "label": "A", "kind": "input"},
                {"id": "b", "label": "B", "kind": "tool"},
                {"id": "c", "label": "C", "kind": "output"},
            ],
            "flows": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        }
        output = render_payload(payload)
        focus_order = [step["focusNodeId"] for step in output["tour"]["steps"]]
        self.assertEqual(focus_order, ["a", "b", "c"])

    def test_runtime_stats_affect_status_scene_and_tour(self) -> None:
        payload = {
            "system": {"name": "Runtime Metrics"},
            "components": [
                {"id": "a", "label": "A", "kind": "input"},
                {"id": "b", "label": "B", "kind": "llm"},
                {"id": "c", "label": "C", "kind": "output"},
            ],
            "flows": [{"id": "ab", "from": "a", "to": "b"}, {"id": "bc", "from": "b", "to": "c"}],
            "runtime": {
                "events": [
                    {"nodeId": "a"},
                    {"nodeId": "b", "latencyMs": 3500, "cost": 0.12, "tokens": 9000},
                    {"nodeId": "c", "error": True},
                ]
            },
        }
        output = render_payload(payload, view_options={"mode": "cost", "detailLevel": "deep"})
        node_metrics = output["runtimeMetrics"]["nodeMetrics"]
        self.assertIn("high_latency", node_metrics["b"]["signals"])
        self.assertIn("high_cost", node_metrics["b"]["signals"])
        self.assertEqual(node_metrics["c"]["errorCount"], 1)
        rooms = {room["role"]: room for room in output["spatialMap"]["rooms"]}
        self.assertEqual(rooms["thinking_room"]["status"], "warning")
        self.assertEqual(rooms["exit"]["status"], "error")
        self.assertTrue(
            any(item["type"] == "cost_marker" for item in output["spatialMap"]["landmarks"])
        )
        scene_rooms = [
            item
            for layer in output["renderScene"]["layers"]
            if layer["id"] == "rooms"
            for item in layer["items"]
        ]
        self.assertTrue(any(item["metrics"].get("cost") for item in scene_rooms))
        self.assertTrue(any("3500ms" in step["narration"] for step in output["tour"]["steps"]))

    def test_security_mode_highlights_risky_nodes(self) -> None:
        payload = {
            "system": {"name": "Security Mode"},
            "components": [
                {"id": "a", "label": "A", "kind": "input"},
                {"id": "b", "label": "External API", "kind": "external"},
                {"id": "c", "label": "Mystery", "kind": "unknown"},
                {"id": "d", "label": "D", "kind": "output"},
            ],
            "flows": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "c"},
                {"from": "c", "to": "d"},
            ],
        }
        output = render_payload(payload, view_options={"mode": "security"})
        self.assertEqual(output["viewOptions"]["mode"], "security")
        self.assertIn("security", output["spatialMap"]["view"]["appliedPolicies"])
        risky_rooms = [
            room
            for room in output["spatialMap"]["rooms"]
            if "security_focus" in room.get("signals", [])
        ]
        self.assertGreaterEqual(len(risky_rooms), 2)
        self.assertTrue(
            any(item["type"] == "security_marker" for item in output["spatialMap"]["landmarks"])
        )

    def test_detail_level_changes_spatial_output(self) -> None:
        payload = {
            "system": {"name": "Detail Levels"},
            "components": [
                {"id": "a", "label": "A", "kind": "input"},
                {"id": "b", "label": "B", "kind": "tool"},
                {"id": "c", "label": "C", "kind": "output"},
            ],
            "flows": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        }
        simple = render_payload(payload, view_options={"detailLevel": "simple"})
        deep = render_payload(payload, view_options={"detailLevel": "deep"})
        simple_room = simple["spatialMap"]["rooms"][0]
        deep_room = deep["spatialMap"]["rooms"][0]
        self.assertIn("summary", simple_room)
        self.assertNotIn("nodeDetails", simple_room)
        self.assertIn("nodeDetails", deep_room)
        self.assertNotEqual(simple["spatialMap"], deep["spatialMap"])

    def test_requirement_drift_is_reported(self) -> None:
        payload = {
            "system": {"name": "Requirement Drift"},
            "components": [
                {"id": "a", "label": "A", "kind": "input"},
                {"id": "c", "label": "C", "kind": "output"},
            ],
            "flows": [{"from": "a", "to": "c"}],
            "requirements": {
                "requiredComponentKinds": ["llm"],
                "requiredFlows": [{"from": "a", "to": "missing"}],
            },
        }
        output = render_payload(payload)
        codes = {warning["code"] for warning in output["diagnostics"]["warnings"]}
        self.assertIn("requirement_missing_kind", codes)
        self.assertIn("requirement_missing_flow", codes)

    def test_cli_output_files_can_be_written(self) -> None:
        output = render_file(ROOT / "examples" / "dify_workflow.json")
        directory = ROOT / "out" / "test-write"
        files = write_render_output(output, directory)
        for path in files.values():
            self.assertTrue(path.exists(), path)
        self.assertIn(
            "Sample Dify Workflow",
            (directory / "index.html").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
