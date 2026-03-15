# Stock Image Auto Tagger

フォトストック向け画像タグ・タイトル・説明文を自動生成するサーバー。

## 概要

* 画像をアップロードすると AI がタグ・キャプションを生成
* FastAPI + Florence-2 ベース
* Docker + NVIDIA GPU で動作

## クイックスタート

```bash
cd docker/stock-tagger
docker compose up -d
```

**URL**: http://localhost:7861 （WebUI）  
**API**: `POST /tag` （画像タグ生成）, `GET /health` （ヘルスチェック）

初回の画像処理時、Florence-2 モデルのダウンロード（約 1GB）が発生します。数分かかることがあります。

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 技術仕様・アーキテクチャ・実装の手がかり |
| [HANDOVER.md](./HANDOVER.md) | 引継ぎ用ドキュメント |
| [LICENSE](./LICENSE) | 本プロジェクトのライセンス（MIT） |
| [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md) | 使用コンポーネントのライセンス一覧 |

## 使用モデル・ライセンス

本プロジェクトは以下のオープンソースモデル・コードを使用しています。

| コンポーネント | 用途 | ライセンス |
|----------------|------|------------|
| [Florence-2](https://huggingface.co/florence-community/Florence-2-base-ft) | キャプション・タグ生成 | MIT (Microsoft) |
| [RAM++](https://github.com/xinyu1205/recognize-anything) | タグ生成（`ram/` に組み込み） | Apache 2.0 (OPPO) |

詳細なライセンス条文は [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md) を参照してください。

## 現状

**RAM++ 統合済み**。Florence-2 + RAM++ + FastAPI + Docker + WebUI が動作。

- **RAM++**: タグ専用モデルでキーワード精度を向上
- 初回のタグ生成時、RAM++ チェックポイント（約 3GB）を Hugging Face からダウンロード

## 次のステップ

1. タグランキング
3. WebUI 改善
4. バッチ並列化

詳細は ARCHITECTURE.md を参照。
