# System House Renderer

System topology and runtime trace renderer. It turns Dify workflow exports or generic topology JSON into a house-like map for inspection.

## Responsibility

- Normalize workflow / topology input.
- Convert nodes and edges into semantic graph, spatial map, scene, and tour JSON.
- Render a simple HTML preview.
- Redact common secret patterns and local absolute paths in generated diagnostics.
- Optionally attach runtime trace metrics.

System House Renderer is a short-lived CLI. It does not run a server and does not control any module.

## Quick Start

```powershell
cd <workspace>\system-house-renderer
uv sync
uv run python -m system_house_renderer `
  --input examples\sword_topology.json `
  --output out\sword
```

Output files include:

- `semantic-graph.json`
- `spatial-map.json`
- `scene.json`
- `tour.json`
- `diagnostics.json`
- `runtime-metrics.json`
- `index.html`

## Inputs

Supported input types:

- Dify workflow export.
- Generic topology JSON.
- Runtime trace JSON/YAML supplied separately.

Generic topology should describe nodes, edges, node types, labels, and optional metadata. Runtime trace can add active path, latency, error, cost, and token metrics.

## CLI

Common options:

| Option | Purpose |
|---|---|
| `--input` | Workflow or topology input |
| `--output` | Output directory |
| `--runtime` | Runtime trace file |
| `--runtime-adapter` | `auto`, `generic`, or `sword-events` |
| `--turn-id` | Filter runtime trace by turn ID |
| `--requirements` | Requirements JSON/YAML |
| `--mode` | `overview`, `tour`, `trace`, `debug`, `cost`, `security` |
| `--detail-level` | `simple`, `normal`, `deep` |
| `--language` | `ja` or `en` |
| `--runtime-status-file` | Write short-lived CLI status JSON |

## Runtime Status

When `--runtime-status-file` is set, the CLI writes `running`, then `stopped` or `failed`. This is for integration launchers. There is no HTTP health or shutdown endpoint.

## Security

The renderer redacts common secret keys, bearer tokens, JWT-like strings, private key blocks, and local absolute paths. Redaction is best-effort; do not feed unreviewed secrets into shareable artifacts.

## Tests

```powershell
uv run python -m unittest discover -s tests
```
