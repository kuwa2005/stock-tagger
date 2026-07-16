# Stock Image Auto Tagger 引継ぎドキュメント

Version: 0.2  
最終更新: 2026-07

---

# 1. プロジェクト概要

**目的**: 画像を読み込み、フォトストック向けのタグ・タイトル・説明文を自動生成するサーバー

**現状**: MVP 稼働中（Docker + GPU + WebUI + API）。開発確認は `docker compose` のテスト環境（ポート 7861）で実施。

**リポジトリ**: https://github.com/kuwa2005/stock-tagger

---

# 2. 担当者が理解すべき技術

| 分野 | 内容 |
|------|------|
| Docker | docker compose、NVIDIA Container Toolkit、ボリューム（`data/hf_cache`） |
| GPU 推論 | CUDA、VRAM（Florence-2 + RAM++ で 8GB 前後） |
| HuggingFace | Transformers、モデルキャッシュ（`HF_HOME`） |
| FastAPI | multipart アップロード、静的ファイル、翻訳フォールバック API |
| フロント | 組み込み WebUI（`app/main.py` 内 HTML）、Playwright E2E |

---

# 3. ディレクトリ構成

```
stock-tagger/
├── ARCHITECTURE.md
├── HANDOVER.md
├── README.md
├── THIRD_PARTY_LICENSES.md
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── package.json / playwright.config.ts
├── app/
│   ├── main.py      # API + WebUI
│   ├── tagger.py    # Florence-2
│   ├── ram_tag.py   # RAM++
│   └── utils.py
├── ram/             # Recognize Anything
├── static/          # favicon, jszip, piexif
├── e2e/             # Playwright
└── data/hf_cache/   # モデルキャッシュ（永続化・gitignore）
```

---

# 4. 開発・テスト環境

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:7861/health

# E2E（ホスト側）
npm install && npx playwright install --with-deps chromium
npm run test:smoke
npm run test:gpu
```

コード変更後は `docker compose up -d --build` で反映。

| 変数 | 意味 |
|------|------|
| `WEBUI_PORT` | 公開ポート（既定 7861） |
| `USE_RAM` | RAM++ 有効（`true`/`false`） |
| `HF_HOME` | コンテナ内 `/data/hf_cache` |

---

# 5. 保守・定期作業

| 作業 | 頻度 | 内容 |
|------|------|------|
| ログ | 随時 | `docker compose logs -f` |
| モデル / ベースイメージ | 四半期 | HF 更新、`pytorch` ベース確認 |
| GPU | 四半期 | `nvidia-smi` |
| E2E | 改修時 | `npm test` |

---

# 6. 既知の注意点

1. **VRAM**: 他 GPU サービス（SD WebUI 等）との同時稼働は要確認
2. **翻訳**: Chrome Translator は 138+・セキュアコンテキスト必須。無い場合は `/translate` フォールバック
3. **ZIP**: 画像のみ同梱（CSV 同梱は Chrome にブロックされやすい）。メタは CSV 別ダウンロード + JPEG Exif
4. **NG キーワード**: ブラウザ `localStorage`（端末依存）。Import/Export あり
5. **人物・ロゴ**: モデルリリース / ブランド判定なし。人間確認推奨

---

# 7. 次のステップ（Issue 管理）

GitHub Issues で追跡:

1. タグランキング
2. ストックサイト別 CSV
3. バッチ並列化
4. キーワード翻訳（保留判断）

---

# 8. 関連リソース

| リソース | URL |
|----------|------|
| リポジトリ | https://github.com/kuwa2005/stock-tagger |
| Florence-2 | https://huggingface.co/florence-community/Florence-2-base-ft |
| RAM++ | https://github.com/xinyu1205/recognize-anything |

---

# 9. 結論

動作優先の MVP は一通り揃っている。実用強化の主眼は **タグランキング** と **サイト別 CSV**、大量処理時の **並列化**。
