# SystemHouseRenderer

SystemHouseRenderer は、Dify workflow や Web/ローカル連携システムの構成を、「家の中を案内するような空間マップ」として可視化するためのモジュールです。

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

実行ログがある場合は、ツアー順序や active 表示に使えます。

```json
{
  "runtime": {
    "events": [
      { "nodeId": "input" },
      { "nodeId": "worker" },
      { "nodeId": "answer" }
    ]
  }
}
```

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

値そのものは隠し、存在だけを `diagnostics.hiddenItems` と `locked_box` ランドマークで示します。

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
- `--requirements`: 要求仕様JSON/YAMLを別ファイルで指定。
- `--mode`: `overview` / `tour` / `debug` / `cost` / `security`。
- `--detail-level`: `simple` / `normal` / `deep`。
- `--language`: `ja` / `en`。

## テスト

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

## 現在の制限

- プレビューはMVPの簡易HTML/SVGです。
- Dify export の実スキーマ差分には今後さらに対応が必要です。
- コスト、レイテンシ、エラー頻度の表現は、入力データがある場合の拡張余地として残しています。
- 3D表示や動画生成は行いません。
