# System House Renderer

System House Renderer は、Dify workflow や Web/ローカル連携システムの構成を、「家の中を案内するような空間マップ」として可視化するためのモジュールです。

単なるノードグラフではなく、構成要素を部屋・廊下・ランドマークへ変換します。構成の不具合、無駄な経路、セキュリティ上の注意点、要求仕様とのずれを見つけやすくすることを目的にしています。

中核の入力形式は Dify 専用ではありません。Dify export JSON は入力アダプタの1つとして扱い、内部では汎用的な topology に正規化してから描画データを生成します。

## クイックスタート

```powershell
$env:PYTHONPATH = "src"
python -m system_house_renderer map --input examples\dify_workflow.json --out out\house-map
```

生成されるファイル:

- `semantic-graph.json`: 構成要素と接続を一般化した意味グラフ。
- `spatial-map.json`: 部屋、廊下、ランドマークへ変換した空間マップ。
- `scene.json`: SVG/Canvasなどの描画に使う抽象描画データ。
- `tour.json`: 構成を順に案内するツアーデータ。
- `diagnostics.json`: 警告、未対応要素、隠した機密情報の一覧。
- `runtime-metrics.json`: 実行ログや統計をノード/フロー単位に正規化したメトリクス。
- `index.html`: ブラウザで確認できる簡易プレビュー。

プレビューは `out\house-map\index.html` をブラウザで開いて確認します。

## 入力形式

### Dify Workflow Export

Dify アダプタは、よくある次の構造を受け付けます。

- `graph.nodes` / `graph.edges`
- `workflow.graph.nodes` / `workflow.graph.edges`
- ネストされたオブジェクト内の `nodes` / `edges`

未知のノード種別は失敗させず、`unknown` として扱います。

### 汎用 Topology

Dify 以外のシステムは、次のような汎用JSONで記述できます。

```json
{
  "system": { "id": "sample", "name": "Sample System" },
  "components": [
    { "id": "input", "label": "Webhook", "kind": "input" },
    { "id": "worker", "label": "Worker", "kind": "tool" },
    { "id": "answer", "label": "Response", "kind": "output" }
  ],
  "flows": [
    { "from": "input", "to": "worker", "kind": "event" },
    { "from": "worker", "to": "answer", "kind": "data" }
  ]
}
```

### Runtime Trace Adapter

`--runtime` には、汎用runtime JSON/YAMLに加えて、JSONL形式のイベントログやSSE URLを指定できます。

```powershell
$env:PYTHONPATH = "src"
python -m system_house_renderer map `
  --runtime examples\sword_events.jsonl `
  --runtime-adapter sword-events `
  --turn-id turn-demo `
  --mode trace `
  --detail-level deep `
  --out out\sword-trace
```

`sword-events` adapter は、`sword-voice-agent` の `events.jsonl` や `/api/events?once=1` が返すSSEを、汎用runtime traceへ正規化します。入力topologyを指定しない場合は、次の標準経路を持つ簡易topologyを自動生成します。

```text
Gesture -> STT -> Handoff -> Dify -> TTS -> Avatar
```

本文は出力しません。`transcript`、`command`、`response_text`、`delta` などは `length` と短いhashだけに変換します。`--turn-id` を指定すると、その `turn_id` のイベントだけを可視化します。

実行ログがある場合は、ツアー順序、active 表示、遅延、コスト、トークン数、エラー表示に使えます。

```json
{
  "runtime": {
    "events": [
      { "nodeId": "input" },
      { "nodeId": "worker", "latencyMs": 2800, "cost": 0.07, "tokens": 9000 },
      { "nodeId": "answer", "error": true }
    ],
    "thresholds": {
      "latencyWarningMs": 2000,
      "costWarning": 0.05,
      "tokenWarning": 8000
    }
  }
}
```

runtime の主な反映:

- `error` または `status: "error"` があるノード/経路は `status: error`。
- `latencyMs` がしきい値以上の部屋は `high_latency` signal。
- `cost` がしきい値以上の部屋は `high_cost` signal と `cost_marker`。
- `tokens` がしきい値以上のノードは `high_tokens` signal。
- 同じ経路を複数回通った場合、廊下の `width` が太くなります。

要求仕様を渡すと、欠落や乖離を `diagnostics.json` に出します。

```json
{
  "requirements": {
    "requiredComponentKinds": ["input", "output"],
    "requiredFlows": [{ "from": "input", "to": "answer" }]
  }
}
```

## 部屋への変換

現在の house metaphor では、主に次のように分類します。

- `input`: 玄関
- `llm`: 思考室
- `knowledge`: 図書室
- `tool` / `external`: 作業場
- `condition`: 制御室
- `memory` / `variable`: 記憶室
- `output`: 出口
- `unknown`: 設備室

接続は部屋間の廊下へ集約します。同じ入力なら同じ座標になるよう、決定的なレイアウト規則を使います。

## セキュリティ上の扱い

次のようなキー名を持つ値は、出力JSONやHTMLにコピーしません。

- `api_key`
- `token`
- `secret`
- `password`
- `credential`
- `authorization`
- `private_key`

また、キー名だけでなく値そのものも検査します。`label`、`summary`、`description`、prompt などに次のような文字列が混ざった場合も `[redacted]` に置き換えます。

- `sk-` で始まるOpenAI風キー。
- `Bearer ...` や `Authorization: Bearer ...`。
- JWT風文字列。
- 長いランダムAPIキー風文字列。
- private key block。
- `api_key=...`、`token: ...` などの代入風文字列。
- Windows / Unix のローカル絶対パス。

値そのものは隠し、存在だけを `diagnostics.hiddenItems` と `locked_box` ランドマークで示します。

## 表示モード

`--mode` は、同じ構造データをどの観点で強調するかを決めます。

- `overview`: 全体構造を標準表示します。
- `tour`: 実行順や active な部屋を案内向けに強調します。
- `trace`: runtime trace の active 経路と `turn_id` 情報を強調します。
- `debug`: `diagnostics` の `relatedId` が付いた部屋を強調します。
- `cost`: cost がある部屋を見つけやすくし、cost marker を表示します。
- `security`: secret、外部API、unknown、高リスクノードを強調し、security marker を表示します。

`--detail-level` は出力の細かさを変えます。

- `simple`: 部屋ごとの概要を優先します。
- `normal`: 標準的な部屋/廊下/ノード情報を出します。
- `deep`: 部屋内に `nodeDetails` と個別メトリクスを含めます。

このモジュールは構成確認と説明のための補助ツールです。脅威モデリング、依存関係スキャン、正式なセキュリティレビューの代替ではありません。

## CLI

```powershell
$env:PYTHONPATH = "src"
python -m system_house_renderer map `
  --input examples\dify_workflow.json `
  --out out\house-map `
  --language ja
```

追加オプション:

- `--runtime`: 実行ログJSON/YAMLを別ファイルで指定。
- `--runtime-adapter`: `auto` / `generic` / `sword-events`。
- `--turn-id`: runtime trace を特定の `turn_id` に絞り込み。
- `--requirements`: 要求仕様JSON/YAMLを別ファイルで指定。
- `--mode`: `overview` / `tour` / `trace` / `debug` / `cost` / `security`。
- `--detail-level`: `simple` / `normal` / `deep`。
- `--language`: `ja` / `en`。
- `--runtime-status-file`: 統合ランチャー向けの短命CLI status JSONを書きます。

## Runtime Status

SystemHouseRenderer は短命CLIなので、HTTP `/health` や `POST /shutdown` は実装していません。将来 watch/server mode を追加する場合は、長時間プロセス向けの共通停止契約に従う必要があります。

現時点では、統合起動側が実行状態を把握しやすいよう、任意で `--runtime-status-file` を指定できます。

```powershell
python -m system_house_renderer map `
  --input examples\dify_workflow.json `
  --out out\house-map `
  --runtime-status-file out\system-house-status.json
```

status file には次のようなJSONを書きます。

```json
{
  "module": "system_house_renderer.map",
  "pid": 1234,
  "parent_pid": 1000,
  "started_at": "2026-04-29T00:00:00+00:00",
  "host": null,
  "port": null,
  "health_url": null,
  "shutdown_url": null,
  "shutdown_command": null,
  "command_line": ["system-house-renderer", "map", "..."],
  "state": "stopped",
  "uptime_s": 0.123
}
```

正常終了時は `state: "stopped"`、例外終了時は `state: "failed"` を書きます。status file は削除しません。

## テスト

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

## 現在の制限

- プレビューはMVPの簡易HTML/SVGです。
- Dify export の実スキーマ差分には今後さらに対応が必要です。
- コスト、レイテンシ、エラー頻度の表現は基本対応です。実サービスごとの詳細な課金体系や独自ログ形式は、入力アダプタ側での追加正規化が必要です。
- 3D表示や動画生成は行いません。
