# Stock Image Auto Tagger / 画像アノテーションシステム

## Docker構成 技術仕様書

Version: 0.1  
対象: フォトストック向け画像タグ自動生成 / 画像アノテーション  
実行環境: Linux + Docker + NVIDIA GPU

---

# 1. システム概要

本システムは、デジタルカメラで撮影した写真に対し、
**フォトストックサイト向けタグ・タイトル・説明文を自動生成するサーバー**である。

主な目的は以下。

* 写真タグ付けの自動化
* 大量画像の処理
* リモートPCからの利用
* APIベース処理
* CSV出力（フォトストック登録用）

AIモデルとして **Vision-Language Model (VLM)** を使用する。

---

# 2. アノテーションの種類（拡張検討）

| 種類 | 説明 | 対応モデル | 用途 |
|------|------|------------|------|
| **タグ・キーワード** | 画像内容を表す単語群 | RAM++, Florence-2 | フォトストック |
| **キャプション** | 自然文での説明 | Florence-2 | タイトル・説明文 |
| **バウンディングボックス** | 物体の矩形検出 | Florence-2 `<OD>` | 物体位置アノテーション |
| **セグメンテーション** | ピクセル単位の領域分割 | OneFormer, SAM | 精密アノテーション |

**Florence-2** はプロンプトで複数タスクに対応可能:
- `<CAPTION>` / `<DETAILED_CAPTION>` … キャプション
- `<OD>` … Object Detection（バウンディングボックス）

---

# 3. システムアーキテクチャ

```
Remote PC
    │
    │ HTTP
    ▼
┌─────────────────────┐
│ FastAPI API Server  │
│  (stock-tagger)     │
│                     │
│  ├ image upload     │
│  ├ batch processing │
│  ├ CSV export       │
│  └ WebUI            │
└─────────┬───────────┘
          │
          │ GPU inference
          ▼
┌─────────────────────┐
│ Florence-2 Model    │
│ (image captioning)  │
└─────────────────────┘
```

---

# 4. Docker構成

docker-compose により1コンテナ構成で運用する。

```
stock-tagger
 ├ FastAPI
 ├ Florence-2 inference
 ├ CSV export
 └ Web UI
```

Docker構成ファイル

```
docker-compose.yml
Dockerfile
.env
```

---

# 5. 使用技術

## Backend

* Python 3.10
* FastAPI
* Uvicorn
* Pillow
* HuggingFace Transformers

### 理由

FastAPIは

* 高速
* 非同期
* OpenAPI対応

でありAPI用途に適している。

---

## AIモデル

使用モデル

```
microsoft/Florence-2-base-ft
```

用途

* Image Caption
* Scene理解
* 自然言語生成
* Object Detection（`<OD>` プロンプト）

出力例

```
A traditional Japanese temple illuminated at night with autumn foliage
```

---

# 6. GPU要件

推奨GPU

```
RTX 3060 12GB
```

最低

```
8GB VRAM
```

本環境

```
RTX3060 12GB
P106-100 6GB
```

Docker GPU設定

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          capabilities: [gpu]
```

---

# 7. API仕様

## Health Check

```
GET /health
```

レスポンス

```json
{"status":"ok"}
```

---

## 画像タグ生成

```
POST /tag
```

input

```
multipart/form-data
files=@image.jpg
```

output

```json
{
  "title": "",
  "caption": "",
  "keywords": []
}
```

---

## CSV生成

```
POST /tag.csv
```

複数画像入力

出力

```
title,caption,keywords
```

---

## バッチ処理

```
POST /batch.zip
```

入力

```
zip
```

出力

```
results.zip
```

---

# 8. WebUI

簡易UIを提供

機能

* 画像アップロード
* タグ生成
* CSVダウンロード

URL

```
http://server:7861
```

---

# 9. ディレクトリ構造

```
stock-tagger/
├── app/
│   ├── main.py
│   ├── tagger.py
│   └── utils.py
├── Dockerfile
├── docker-compose.yml
├── ARCHITECTURE.md
├── HANDOVER.md
├── README.md
└── .env
```

---

# 10. 処理フロー

1. 画像受信
2. PILで読み込み
3. Florence-2へ入力
4. caption生成
5. キーワード抽出
6. JSON生成
7. CSV整形

---

# 11. 懸念点

## 1 タグ精度

Florence-2は

* caption生成モデル

であり

**タグ専用モデルではない**

問題

* 抽象語が増える
* 重要タグが抜ける

例

```
temple
lantern
night
```

などが欠落する可能性。

---

## 2 処理速度

Florence-2は

比較的大きいモデル。

RTX3060でも

```
1枚 0.5〜1.5秒
```

大量処理ではボトルネックになる。

---

## 3 GPUメモリ

VRAM使用量

```
8GB前後
```

他サービス併用は難しい。

---

## 4 ストックサイト仕様

フォトストックサイトは

* キーワード順序
* 上位10語

の影響が大きい。

現在

```
ランキング処理なし
```

---

# 12. 課題解決の可能性

## 1 RAM++導入

画像タグ専用モデル

```
Recognize Anything Model (RAM++)
```

特徴

* 数千タグ認識
* object検出に強い
* RTX 2080で 309,000 images/$ の効率
* 推論 300ms 以下

導入効果

```
タグ精度向上
```

構成

```
RAM++ → Florence2 → 統合
```

---

## 2 CLIPタグ生成

CLIPで

```
タグ候補 × 類似度
```

によりランキング。

---

## 3 keyword ranking

LLMで

```
重要度順
```

並べ替え。

---

## 4 バッチキュー

現在

```
同期処理
```

改善

```
Redis + Celery
```

---

# 13. 改善提案

推奨構成

```
RAM++
   ↓
Florence-2
   ↓
Keyword ranking
   ↓
CSV export
```

---

# 14. 将来アーキテクチャ

```
              ┌────────────┐
              │   RAM++    │
              │ object tag │
              └──────┬─────┘
                     │
                     ▼
              ┌────────────┐
              │ Florence-2 │
              │ caption    │
              └──────┬─────┘
                     │
                     ▼
              ┌────────────┐
              │ keyword AI │
              │ ranking    │
              └──────┬─────┘
                     │
                     ▼
              ┌────────────┐
              │  CSV API   │
              └────────────┘
```

---

# 15. 実装の手がかり（参考リンク）

| 項目 | リンク・情報 |
|------|--------------|
| Florence-2 Docker例 | [askaresh/MS-Florence2](https://github.com/askaresh/ms-florence2) - Chainlit + Docker |
| Florence-2 公式 | [microsoft/Florence-2-base](https://huggingface.co/microsoft/Florence-2-base) |
| RAM++ HuggingFace | [xinyu1205/recognize-anything-plus-model](https://huggingface.co/xinyu1205/recognize-anything-plus-model) |
| RAM++ GitHub | [xinyu1205/recognize-anything](https://github.com/xinyu1205/recognize-anything) |
| サードパーティライセンス | [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md) |
| PyTorch CUDA Docker | `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel` |
| 必要パッケージ | `transformers`, `accelerate`, `einops`, `timm`, `flash-attn`（高速化） |

---

# 16. 今後の優先開発

優先順位

1. RAM++導入
2. タグランキング
3. WebUI改善
4. バッチ並列化
5. ストックサイトCSV対応

---

# 17. フォトストック対応予定

対応予定

```
Adobe Stock
Shutterstock
iStock
```

CSV形式

```
filename,title,keywords,category
```

---

# 18. 運用注意

注意点

* 人物写真はモデルリリース必要
* ロゴ検出なし
* ブランド判定なし

AIタグは

```
人間確認推奨
```

---

# 19. 参考モデル

使用可能VLM

```
Florence-2
BLIP2
JoyCaption
RAM++
```

---

# 20. 多方面からの追加提案

## A. 軽量モデルオプション

| モデル | VRAM | 速度 | 用途 |
|--------|------|------|------|
| Florence-2-base | 〜8GB | 中 | 汎用 |
| Florence-2-large | 〜12GB | 遅 | 高精度 |
| BLIP2 | 〜6GB | 速 | 軽量 |
| RAM++ | 〜4GB | 速 | タグ特化 |

**P106-100 6GB** 環境では BLIP2 または RAM++ 単体が現実的。

---

## B. バウンディングボックス出力（Florence-2 OD）

Florence-2 の `<OD>` プロンプトで物体検出可能。
COCO形式のJSON出力に変換すれば、LabelImg等のアノテーションツールと連携可能。

```python
# プロンプト例
prompt = "<OD>"
# 出力: [{"bbox": [x1,y1,x2,y2], "label": "..."}, ...]
```

---

## C. 既存環境との共存

同一ホストで SD WebUI (7860), Open WebUI (8888) 等が稼働する場合は、
ポート競合を避けるため **7861** を stock-tagger に割り当て。

---

## D. モデルキャッシュ

HuggingFace モデルは初回ダウンロードに時間がかかる。
`HF_HOME` または `TRANSFORMERS_CACHE` でボリュームマウントし、
再ビルド時もキャッシュを再利用する構成を推奨。

---

## E. バッチ処理の並列化

* **同一GPU内**: バッチサイズ増加（VRAM許容範囲）
* **マルチGPU**: 複数ワーカーで画像を分散
* **非同期**: Celery + Redis でキューイング

---
