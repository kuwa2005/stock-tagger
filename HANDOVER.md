# Stock Image Auto Tagger 引継ぎドキュメント

Version: 0.1  
最終更新: 2025-03

---

# 1. プロジェクト概要

**目的**: 画像を読み込み、フォトストック向けのタグ・タイトル・説明文を自動生成するサーバー

**現状**: 企画段階。ARCHITECTURE.md に技術仕様を記載済み。

---

# 2. 担当者が理解すべき技術

| 分野 | 内容 |
|------|------|
| Docker | docker-compose, マルチステージビルド, GPU デバイス割り当て |
| GPU推論 | CUDA, VRAM 管理, NVIDIA Container Toolkit |
| HuggingFace | Transformers, モデルキャッシュ, プロンプト設計 |
| FastAPI | 非同期API, マルチパートアップロード, バックグラウンドタスク |

---

# 3. ディレクトリ構成

```
<プロジェクトルート>/
├── ARCHITECTURE.md   # 技術仕様・アーキテクチャ
├── HANDOVER.md       # 本ドキュメント（引継ぎ用）
├── README.md         # プロジェクト概要（未作成）
├── docker-compose.yml
├── Dockerfile
├── .env
└── app/
    ├── main.py
    ├── tagger.py
    └── utils.py
```

---

# 4. 開発環境セットアップ（想定）

```bash
# 1. ディレクトリへ移動
cd <プロジェクトルート>

# 2. 環境変数設定
cp .env.example .env
# .env を編集（ポート、GPU等）

# 3. ビルド
docker compose build

# 4. 起動
docker compose up -d

# 5. 動作確認
curl http://localhost:7861/health
```

---

# 5. 保守・定期作業

| 作業 | 頻度 | 内容 |
|------|------|------|
| docker pull | 月次 | ベースイメージ更新 |
| model update | 四半期 | HuggingFace モデル新バージョン確認 |
| GPU driver | 四半期 | `nvidia-smi` でドライバー状態確認 |
| ログ確認 | 随時 | `docker compose logs -f` |

---

# 6. 既知の懸念点（実装時に考慮）

1. **タグ精度**: Florence-2 はキャプション用。タグ専用ではない → RAM++ 導入検討
2. **処理速度**: 1枚 0.5〜1.5秒程度。大量処理時はキュー・並列化が必要
3. **VRAM**: 8GB前後使用。他サービス（SD WebUI等）との同時稼働は要確認
4. **キーワード順序**: ストックサイトは上位10語が重要。ランキング処理未実装

---

# 7. 次のステップ（優先順）

1. **MVP 実装**: Florence-2 単体で FastAPI + Docker 構成を構築
2. **RAM++ 導入**: タグ精度向上のためパイプラインに追加
3. **タグランキング**: LLM またはルールで重要度順に並べ替え
4. **WebUI 改善**: ドラッグ&ドロップ、プレビュー、一括ダウンロード
5. **バッチ並列化**: Redis + Celery または 非同期キュー

---

# 8. 関連リソース

| リソース | URL |
|----------|-----|
| ARCHITECTURE.md | 同ディレクトリ |
| Florence-2 Docker例 | https://github.com/askaresh/ms-florence2 |
| RAM++ GitHub | https://github.com/xinyu1205/recognize-anything |
| HuggingFace Florence-2 | https://huggingface.co/microsoft/Florence-2-base |

---

# 9. 連絡・問い合わせ

* プロジェクトオーナー: [担当者名を記載]
* リポジトリ: [Git URL を記載]
* ドキュメント更新: 変更時は本ファイルの「最終更新」を更新すること

---

# 10. 結論

現システムは

```
動作優先の最小構成（企画段階）
```

であり

**実用化には**

* タグ精度向上（RAM++）
* ランキング処理
* バッチ並列化

の導入が必要。

RAM++ を組み込んだ完全版、RTX3060 最速化、フォトストック特化ロジックまで実装すると、
**フォトストック用途でかなり強い構成**になる。
