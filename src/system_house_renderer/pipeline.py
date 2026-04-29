from __future__ import annotations

from pathlib import Path
from typing import Any

from system_house_renderer.adapters import normalize_payload_to_topology
from system_house_renderer.diagnostics import new_diagnostics
from system_house_renderer.house import build_spatial_map
from system_house_renderer.loader import load_document, write_json
from system_house_renderer.preview import build_preview_html
from system_house_renderer.scene import build_render_scene
from system_house_renderer.semantic import build_semantic_graph
from system_house_renderer.tour import build_tour


def render_file(
    input_path: str | Path,
    *,
    runtime_path: str | Path | None = None,
    requirements_path: str | Path | None = None,
    view_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = load_document(input_path)
    if runtime_path is not None:
        runtime = load_document(runtime_path)
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["runtime"] = runtime
    if requirements_path is not None:
        requirements = load_document(requirements_path)
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["requirements"] = requirements
    return render_payload(payload, source_path=input_path, view_options=view_options)


def render_payload(
    payload: Any,
    *,
    source_path: str | Path | None = None,
    view_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = {
        "mode": "overview",
        "metaphor": "house",
        "detailLevel": "normal",
        "language": "ja",
    }
    if view_options:
        options.update({key: value for key, value in view_options.items() if value is not None})
    diagnostics = new_diagnostics()
    topology = normalize_payload_to_topology(payload, diagnostics, source_path=source_path)
    semantic_graph = build_semantic_graph(topology, diagnostics)
    spatial_map = build_spatial_map(
        semantic_graph,
        topology.get("runtime") or {},
        diagnostics,
        language=str(options.get("language") or "ja"),
    )
    render_scene = build_render_scene(semantic_graph, spatial_map)
    tour = build_tour(
        semantic_graph,
        spatial_map,
        topology.get("runtime") or {},
        language=str(options.get("language") or "ja"),
    )
    return {
        "semanticGraph": semantic_graph,
        "spatialMap": spatial_map,
        "renderScene": render_scene,
        "tour": tour,
        "diagnostics": diagnostics,
        "viewOptions": options,
    }


def write_render_output(output: dict[str, Any], out_dir: str | Path) -> dict[str, Path]:
    resolved = Path(out_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    files = {
        "semanticGraph": resolved / "semantic-graph.json",
        "spatialMap": resolved / "spatial-map.json",
        "renderScene": resolved / "scene.json",
        "tour": resolved / "tour.json",
        "diagnostics": resolved / "diagnostics.json",
    }
    for key, path in files.items():
        write_json(path, output[key])
    index_path = resolved / "index.html"
    index_path.write_text(build_preview_html(output), encoding="utf-8")
    files["preview"] = index_path
    return files
