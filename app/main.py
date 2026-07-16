"""Stock Image Auto Tagger - FastAPI アプリケーション"""
import io
import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from .tagger import tag_image

app = FastAPI(
    title="Stock Image Auto Tagger",
    description="Auto-generate stock photo tags, titles, and captions",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

_FAVICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "favicon.ico")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(_FAVICON_PATH, media_type="image/x-icon")


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    source: str = "en"
    target: str = "ja"


@app.post("/translate")
async def translate_text(payload: TranslateRequest):
    """
    Fallback translation when Chrome Translator API is unavailable.
    Uses MyMemory free API (en→ja for display only).
    """
    source = (payload.source or "en").strip().lower()
    target = (payload.target or "ja").strip().lower()
    text = payload.text.strip()
    if not text:
        return {"translated": "", "engine": "none"}

    # Keep short requests; MyMemory has length limits
    chunk = text[:450]
    query = urllib.parse.urlencode({"q": chunk, "langpair": f"{source}|{target}"})
    url = f"https://api.mymemory.translated.net/get?{query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stock-tagger/0.1"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        translated = (
            (data.get("responseData") or {}).get("translatedText")
            or ""
        ).strip()
        if not translated:
            raise HTTPException(status_code=502, detail={"error": "Empty translation response"})
        return {"translated": translated, "engine": "mymemory"}
    except HTTPException:
        raise
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail={"error": f"Translation HTTP error: {e.code}"})
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": f"Translation failed: {e}"})


@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {"status": "ok"}


@app.post("/tag")
async def tag(
    files: List[UploadFile] = File(...),
    include_od: bool = Form(False),
    use_ram: bool = Form(default=None),
):
    """
    画像からタグ・タイトル・キャプションを生成。
    use_ram: RAM++ でタグ補強（未指定時は環境変数 USE_RAM、デフォルト True）
    """
    use_ram_flag = use_ram if use_ram is not None else os.environ.get("USE_RAM", "true").lower() in ("1", "true", "yes")
    results = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        data = await f.read()
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:
            raise HTTPException(status_code=400, detail={"error": f"Failed to read image: {e}"})
        try:
            result = tag_image(img, include_od=include_od, use_ram=use_ram_flag)
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": str(e)})
        result["filename"] = f.filename or "image"
        results.append(result)
    if not results:
        raise HTTPException(status_code=400, detail={"error": "No valid images"})
    return {"results": results} if len(results) > 1 else results[0]


@app.post("/tag.csv", response_class=PlainTextResponse)
async def tag_csv(files: List[UploadFile] = File(...)):
    """複数画像をタグ付けし、CSV形式で返す"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["filename", "title", "caption", "keywords"])
    row_count = 0

    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        data = await f.read()
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            continue
        try:
            use_ram_flag = os.environ.get("USE_RAM", "true").lower() in ("1", "true", "yes")
            result = tag_image(img, use_ram=use_ram_flag)
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": str(e)})
        keywords_str = ",".join(result["keywords"]) if result["keywords"] else ""
        writer.writerow([
            f.filename or "image",
            result["title"],
            result["caption"],
            keywords_str,
        ])
        row_count += 1

    if row_count == 0:
        raise HTTPException(status_code=400, detail={"error": "No valid images"})

    output.seek(0)
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=tags_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        },
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    """WebUI"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Image Auto Tagger</title>
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="icon" type="image/png" href="/static/favicon.png">
    <style>
        * { box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        h1 { font-size: 1.5rem; }
        .upload { border: 2px dashed #ccc; border-radius: 8px; padding: 2rem; text-align: center; margin: 1rem 0; }
        .upload.dragover { border-color: #4a9; background: #f0fff0; }
        .upload.busy { opacity: 0.85; }
        input[type="file"] { display: none; }
        .btn { background: #4a9; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 1rem; }
        .btn:hover { background: #389; }
        .btn:disabled { background: #999; cursor: not-allowed; }
        .topActions { display: flex; justify-content: flex-end; align-items: center; gap: 0.5rem; margin: 0.75rem 0 0; flex-wrap: wrap; }
        .btnClear { background: #888; }
        .btnClear:hover { background: #666; }
        #processingBar { display: none; margin-top: 1rem; padding: 0.75rem 1rem; background: #eef6ff; border: 1px solid #b7d4f0; border-radius: 8px; color: #245; font-size: 0.95rem; }
        #processingBar.show { display: block; }
        #processingText { margin-bottom: 0.45rem; }
        #processingFile { color: #567; font-size: 0.85rem; word-break: break-all; }
        .procTrack { height: 8px; background: #d7e8f8; border-radius: 999px; overflow: hidden; }
        .procFill { height: 100%; width: 0%; background: #4a9; border-radius: 999px; transition: width 0.2s ease; }
        #result { margin-top: 1rem; padding: 1rem; background: #f8f8f8; border-radius: 8px; white-space: pre-wrap; }
        #result:empty { display: none; }
        .resultItem { display: flex; gap: 1rem; margin-bottom: 1.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid #e0e0e0; }
        .resultItem:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .resultThumb { flex-shrink: 0; }
        .resultThumb img.thumb { max-width: 120px; max-height: 120px; object-fit: cover; border-radius: 4px; cursor: zoom-in; }
        .resultThumb img.thumb:hover { outline: 2px solid #4a9; outline-offset: 1px; }
        .resultBody { flex: 1; min-width: 0; }
        .keyword { display: inline-block; background: #e0e0e0; padding: 0.2rem 0.5rem; margin: 0.2rem; border-radius: 4px; font-size: 0.9rem; cursor: help; user-select: none; }
        .keyword.ng { text-decoration: line-through; opacity: 0.6; }
        .keyword.pending-block { text-decoration: line-through; opacity: 0.65; background: #f8d0d0; }
        body.block-mode .keyword { cursor: pointer; }
        body.block-mode .keyword:hover { outline: 1px solid #c66; }
        body.block-mode .resultThumb img.thumb { pointer-events: none; cursor: default; opacity: 0.85; }
        #resultToolbar { display: none; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin-top: 1.25rem; margin-bottom: 0.5rem; }
        #resultToolbar.show { display: flex; }
        .toggleRow { display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.95rem; cursor: pointer; user-select: none; }
        .toggleRow input { position: absolute; opacity: 0; width: 0; height: 0; }
        .toggleTrack { width: 2.5rem; height: 1.35rem; background: #ccc; border-radius: 999px; position: relative; transition: background 0.15s; flex-shrink: 0; }
        .toggleTrack::after { content: ''; position: absolute; top: 2px; left: 2px; width: 1.1rem; height: 1.1rem; background: #fff; border-radius: 50%; transition: transform 0.15s; box-shadow: 0 1px 3px rgba(0,0,0,0.25); }
        .toggleRow input:checked + .toggleTrack { background: #c66; }
        .toggleRow input:checked + .toggleTrack::after { transform: translateX(1.15rem); }
        .toggleRow input:focus-visible + .toggleTrack { outline: 2px solid #4a9; outline-offset: 2px; }
        #blockModeBanner { display: none; width: 100%; background: #fde8e8; border: 1px solid #e8a0a0; color: #722; border-radius: 6px; padding: 0.65rem 0.85rem; font-size: 0.9rem; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
        #blockModeBanner.show { display: flex; }
        #blockModeBanner .bannerActions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .btnApply { background: #c66; }
        .btnApply:hover { background: #a55; }
        .btnApply:disabled { background: #ccaaaa; cursor: not-allowed; }
        a.dl { color: #4a9; margin-left: 0.5rem; }
        .resultToolbarLinks { margin-left: auto; display: inline-flex; gap: 0.85rem; align-items: center; flex-wrap: wrap; }
        #translationStatus { width: 100%; font-size: 0.8rem; color: #666; margin: 0; }
        #translationStatus.active { color: #2a6; }
        #translationStatus.warn { color: #a60; }
        #translationStatus.error { color: #c44; }
        .btnNg { background: #c66; }
        .btnNg:hover { background: #a55; }
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1000; align-items: center; justify-content: center; }
        .modal.show { display: flex; }
        .modalContent { background: white; padding: 1.5rem; border-radius: 8px; max-width: 500px; width: 90%; max-height: 80vh; overflow: auto; }
        .modalContent h2 { margin-top: 0; font-size: 1.2rem; }
        .ngAddRow { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
        .ngAddRow input { flex: 1; padding: 0.5rem; }
        .ngList { list-style: none; padding: 0; margin: 0; max-height: 200px; overflow-y: auto; }
        .ngList li { display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0; border-bottom: 1px solid #eee; }
        .ngList li span { word-break: break-all; }
        .ngList .removeBtn { background: #c66; color: white; border: none; padding: 0.2rem 0.5rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
        .ngList .removeBtn:hover { background: #a55; }
        .modalActions { margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .modalActions .btn { margin: 0; }
        .ctxMenu { position: fixed; background: white; border: 1px solid #ccc; border-radius: 4px; padding: 0.25rem 0; box-shadow: 2px 2px 8px rgba(0,0,0,0.2); z-index: 2000; display: none; }
        .ctxMenu.show { display: block; }
        .ctxMenu button { display: block; width: 100%; padding: 0.4rem 1rem; border: none; background: none; text-align: left; cursor: pointer; font-size: 0.9rem; }
        .ctxMenu button:hover { background: #f0f0f0; }
        .lightbox { display: none; position: fixed; inset: 0; z-index: 3000; background: rgba(0,0,0,0.8); align-items: center; justify-content: center; padding: 0; }
        .lightbox.show { display: flex; }
        .lightboxPanel { position: relative; z-index: 1; display: flex; gap: 1.25rem; align-items: stretch; width: var(--lightbox-w, 95vw); height: var(--lightbox-h, 95vh); max-width: 95vw; max-height: 95vh; background: #1c1c1c; border-radius: 10px; padding: 1rem 1.1rem; box-shadow: 0 12px 40px rgba(0,0,0,0.5); box-sizing: border-box; }
        .lightboxMedia { position: relative; flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; align-items: center; justify-content: center; }
        .lightboxMedia img { display: block; max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; border-radius: 6px; background: #111; }
        .lightboxMeta { flex: 0 0 clamp(240px, 22vw, 360px); max-width: 360px; overflow: auto; color: #eee; font-size: 0.92rem; line-height: 1.45; min-height: 0; }
        .lightboxMeta h3 { margin: 0 0 0.85rem; font-size: 1.05rem; word-break: break-all; color: #fff; padding-right: 1.5rem; }
        .lightboxMeta .metaBlock { margin: 0 0 0.85rem; }
        .lightboxMeta .metaLabel { display: block; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: #aaa; margin-bottom: 0.2rem; }
        .lightboxMeta .metaValue { color: #f2f2f2; word-break: break-word; white-space: pre-wrap; }
        .lightboxKeywords { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.25rem; }
        .lightboxKeywords .keyword { background: #333; color: #eee; cursor: default; }
        .lightboxCounter { margin: 1rem 0 0; color: #999; font-size: 0.85rem; }
        .lightboxClose { position: absolute; top: 0.55rem; right: 0.55rem; width: 2rem; height: 2rem; border: none; border-radius: 50%; background: #fff; color: #333; font-size: 1.25rem; line-height: 1; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.3); z-index: 2; }
        .lightboxClose:hover { background: #eee; }
        .lightboxNav { position: absolute; top: 0; bottom: 0; width: 22%; max-width: 96px; border: none; background: transparent; color: #fff; font-size: 2.6rem; line-height: 1; cursor: pointer; opacity: 0; transition: opacity 0.15s, background 0.15s; z-index: 2; display: flex; align-items: center; justify-content: center; text-shadow: 0 2px 8px rgba(0,0,0,0.7); }
        .lightboxMedia:hover .lightboxNav:not(:disabled) { opacity: 0.45; }
        .lightboxNav:hover { opacity: 1 !important; }
        .lightboxNavPrev { left: 0; border-radius: 6px 0 0 6px; background: linear-gradient(to right, rgba(0,0,0,0.45), transparent); }
        .lightboxNavNext { right: 0; border-radius: 0 6px 6px 0; background: linear-gradient(to left, rgba(0,0,0,0.45), transparent); }
        .lightboxNav:disabled { display: none; }
        @media (max-width: 800px) {
            .lightboxPanel { flex-direction: column; }
            .lightboxMeta { flex: 0 0 auto; max-width: none; max-height: 32%; }
            .lightboxMedia { flex: 1 1 auto; min-height: 0; }
            .lightboxNav { width: 28%; font-size: 2rem; }
        }
    </style>
</head>
<body>
    <h1>Stock Image Auto Tagger</h1>
    <p>Drag and drop images to generate tags, titles, and captions.</p>

    <div class="upload" id="dropZone">
        <p>Drag and drop images (multiple allowed), or</p>
        <label><span class="btn">Choose files</span><input type="file" id="fileInput" accept="image/*" multiple></label>
    </div>

    <div class="topActions">
        <button type="button" class="btn btnNg" id="ngManageBtn">Manage blocked keywords</button>
        <button type="button" class="btn btnClear" id="clearBtn" disabled>Clear</button>
    </div>

    <div id="processingBar" role="status">
        <div id="processingText">Processing...</div>
        <div id="processingFile"></div>
        <div class="procTrack"><div class="procFill" id="processingFill"></div></div>
    </div>

    <div id="resultToolbar">
        <label class="toggleRow" title="Mark keywords to block from future results">
            <input type="checkbox" id="blockModeToggle" />
            <span class="toggleTrack" aria-hidden="true"></span>
            <span>Blocking mode</span>
        </label>
        <span class="resultToolbarLinks">
            <a class="dl" id="csvLink" style="display:none;">Download CSV</a>
            <a class="dl" id="zipLink" style="display:none;">Download ZIP</a>
        </span>
        <p id="translationStatus" aria-live="polite"></p>
        <div id="blockModeBanner" role="status">
            <span>Blocking mode — click tags to mark for blocking</span>
            <span class="bannerActions">
                <button type="button" class="btn btnApply" id="blockApplyBtn" disabled>Apply</button>
                <button type="button" class="btn btnClear" id="blockCancelBtn">Cancel</button>
            </span>
        </div>
    </div>
    <div id="result"></div>

    <div class="modal" id="ngModal">
        <div class="modalContent">
            <h2>Blocked keywords</h2>
            <div class="ngAddRow">
                <input type="text" id="ngInput" placeholder="Enter a keyword to block" />
                <button type="button" class="btn" id="ngAddBtn">Add</button>
            </div>
            <ul class="ngList" id="ngList"></ul>
            <div class="modalActions">
                <button type="button" class="btn" id="ngExportBtn">Export</button>
                <button type="button" class="btn" id="ngImportBtn">Import</button>
                <input type="file" id="ngImportFile" accept=".json,.txt,application/json,text/plain" style="display:none" />
                <button type="button" class="btn btnClear" id="ngCloseBtn">Close</button>
            </div>
        </div>
    </div>

    <div class="ctxMenu" id="ctxMenu">
        <button type="button" id="ctxNgBtn">Add to blocked keywords</button>
    </div>

    <div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="Image preview">
        <div class="lightboxPanel" id="lightboxPanel">
            <button type="button" class="lightboxClose" id="lightboxClose" aria-label="Close">&times;</button>
            <div class="lightboxMedia" id="lightboxMedia">
                <img id="lightboxImg" src="" alt="" />
                <button type="button" class="lightboxNav lightboxNavPrev" id="lightboxPrev" aria-label="Previous image">&#8249;</button>
                <button type="button" class="lightboxNav lightboxNavNext" id="lightboxNext" aria-label="Next image">&#8250;</button>
            </div>
            <div class="lightboxMeta">
                <h3 id="lightboxFilename"></h3>
                <div class="metaBlock">
                    <span class="metaLabel">Title</span>
                    <div class="metaValue" id="lightboxTitle"></div>
                </div>
                <div class="metaBlock">
                    <span class="metaLabel">Caption</span>
                    <div class="metaValue" id="lightboxCaptionText"></div>
                </div>
                <div class="metaBlock">
                    <span class="metaLabel">Keywords</span>
                    <div class="lightboxKeywords" id="lightboxKeywords"></div>
                </div>
                <p class="lightboxCounter" id="lightboxCounter"></p>
            </div>
        </div>
    </div>

    <script src="/static/jszip.min.js"></script>
    <script src="/static/piexif.min.js"></script>
    <script>
        const NG_STORAGE_KEY = 'stock-tagger-ng-keywords';
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const clearBtn = document.getElementById('clearBtn');
        const result = document.getElementById('result');
        const csvLink = document.getElementById('csvLink');
        const zipLink = document.getElementById('zipLink');
        const processingBar = document.getElementById('processingBar');
        const processingText = document.getElementById('processingText');
        const processingFile = document.getElementById('processingFile');
        const processingFill = document.getElementById('processingFill');
        const ngManageBtn = document.getElementById('ngManageBtn');
        const ngModal = document.getElementById('ngModal');
        const ngInput = document.getElementById('ngInput');
        const ngAddBtn = document.getElementById('ngAddBtn');
        const ngList = document.getElementById('ngList');
        const ngExportBtn = document.getElementById('ngExportBtn');
        const ngImportBtn = document.getElementById('ngImportBtn');
        const ngImportFile = document.getElementById('ngImportFile');
        const ngCloseBtn = document.getElementById('ngCloseBtn');
        const ctxMenu = document.getElementById('ctxMenu');
        const ctxNgBtn = document.getElementById('ctxNgBtn');
        const lightbox = document.getElementById('lightbox');
        const lightboxPanel = document.getElementById('lightboxPanel');
        const lightboxImg = document.getElementById('lightboxImg');
        const lightboxFilename = document.getElementById('lightboxFilename');
        const lightboxTitle = document.getElementById('lightboxTitle');
        const lightboxCaptionText = document.getElementById('lightboxCaptionText');
        const lightboxKeywords = document.getElementById('lightboxKeywords');
        const lightboxCounter = document.getElementById('lightboxCounter');
        const lightboxClose = document.getElementById('lightboxClose');
        const lightboxPrev = document.getElementById('lightboxPrev');
        const lightboxNext = document.getElementById('lightboxNext');
        const resultToolbar = document.getElementById('resultToolbar');
        const blockModeToggle = document.getElementById('blockModeToggle');
        const blockModeBanner = document.getElementById('blockModeBanner');
        const blockApplyBtn = document.getElementById('blockApplyBtn');
        const blockCancelBtn = document.getElementById('blockCancelBtn');
        const translationStatus = document.getElementById('translationStatus');

        let resultEntries = [];
        let lastThumbUrls = [];
        let ngKeywords = new Set();
        let blockMode = false;
        let pendingBlock = new Set();
        let busy = false;
        let fileQueue = [];
        let processCompleted = 0;
        let processTotal = 0;
        let lightboxIndex = -1;
        let lightboxObjectUrl = null;
        let translatorPromise = null;
        let translationEngine = ''; // 'chrome' | 'fallback' | ''
        const translationCache = new Map();
        const IMG_EXTS = /\.(jpe?g|png|gif|webp|bmp)$/i;

        function getBrowserLanguages() {
            const list = [];
            if (Array.isArray(navigator.languages)) list.push(...navigator.languages);
            if (navigator.language) list.push(navigator.language);
            return list.filter(Boolean).map(l => String(l).toLowerCase());
        }
        function isJapaneseDisplayLanguage() {
            return getBrowserLanguages().some(l => l === 'ja' || l.startsWith('ja-'));
        }
        function setTranslationStatus(message, kind) {
            if (!translationStatus) return;
            translationStatus.textContent = message || '';
            translationStatus.classList.remove('active', 'warn', 'error');
            if (kind) translationStatus.classList.add(kind);
        }
        function translationApiAvailable() {
            return typeof Translator !== 'undefined';
        }
        function translatorUnavailableReason() {
            const parts = [];
            if (!window.isSecureContext) {
                parts.push('page is not a secure context (use https:// or http://localhost)');
            }
            const ua = navigator.userAgent || '';
            const m = ua.match(/Chrome\\/(\\d+)/);
            if (m && parseInt(m[1], 10) < 138) {
                parts.push('Chrome ' + m[1] + ' detected (need 138+)');
            }
            if (typeof Translator === 'undefined') {
                parts.push('Translator global is missing');
            }
            return parts.join('; ') || 'unknown';
        }
        function normalizeAvailability(value) {
            if (value == null) return 'unavailable';
            if (typeof value === 'string') return value;
            if (typeof value === 'object') {
                return value.availability || value.status || value.state || String(value);
            }
            return String(value);
        }
        function canUseTranslator(availability) {
            const a = normalizeAvailability(availability);
            return (
                a === 'available' ||
                a === 'downloadable' ||
                a === 'downloading' ||
                a === 'readily' ||
                a === 'after-download'
            );
        }
        async function ensureTranslator() {
            if (!isJapaneseDisplayLanguage()) return null;
            if (!translationApiAvailable()) return null;
            if (translatorPromise) return translatorPromise;

            translatorPromise = (async () => {
                const opts = { sourceLanguage: 'en', targetLanguage: 'ja' };
                try {
                    const availability = normalizeAvailability(await Translator.availability(opts));
                    console.info('[stock-tagger] Translator.availability(en→ja):', availability, 'langs=', getBrowserLanguages());
                    if (!canUseTranslator(availability)) return null;
                    if (availability === 'downloadable' || availability === 'after-download' || availability === 'downloading') {
                        setTranslationStatus('Downloading Chrome Japanese translation model...', 'warn');
                    }
                    const translator = await Translator.create({
                        sourceLanguage: 'en',
                        targetLanguage: 'ja',
                        monitor(m) {
                            m.addEventListener('downloadprogress', (e) => {
                                const pct = Math.floor((e.loaded || 0) * 100);
                                setTranslationStatus('Downloading Chrome Japanese translation model... ' + pct + '%', 'warn');
                            });
                        },
                    });
                    translationEngine = 'chrome';
                    return translator;
                } catch (err) {
                    console.warn('[stock-tagger] Translator.create failed:', err);
                    translatorPromise = null;
                    return null;
                }
            })();
            return translatorPromise;
        }
        async function translateViaFallback(text) {
            const res = await fetch('/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, source: 'en', target: 'ja' }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail?.error || data.detail || JSON.stringify(data);
                throw new Error(msg);
            }
            translationEngine = 'fallback';
            return String(data.translated || '').trim() || text;
        }
        async function translateDisplayText(text) {
            const src = String(text || '');
            if (!src.trim()) return src;
            if (!isJapaneseDisplayLanguage()) return src;
            const cacheKey = 'ja::' + src;
            if (translationCache.has(cacheKey)) return translationCache.get(cacheKey);
            try {
                let translated = src;
                const translator = await ensureTranslator();
                if (translator) {
                    const out = await translator.translate(src);
                    translated = (out && String(out).trim()) ? String(out) : src;
                    translationEngine = 'chrome';
                } else {
                    translated = await translateViaFallback(src);
                }
                translationCache.set(cacheKey, translated);
                return translated;
            } catch (err) {
                console.warn('[stock-tagger] translate failed:', err);
                setTranslationStatus('Translation failed: ' + (err && err.message ? err.message : String(err)), 'error');
                return src;
            }
        }
        async function applyResultTranslations() {
            if (!isJapaneseDisplayLanguage()) {
                setTranslationStatus('Browser language is not Japanese — showing English title/caption.', 'warn');
                return;
            }
            const nodes = result.querySelectorAll('[data-display="title"], [data-display="caption"]');
            if (!nodes.length) return;

            if (translationApiAvailable()) {
                setTranslationStatus('Translating title/caption to Japanese (Chrome Translator)...', 'warn');
            } else {
                setTranslationStatus(
                    'Chrome Translator unavailable (' + translatorUnavailableReason() + '). Using online fallback...',
                    'warn'
                );
            }

            for (const el of nodes) {
                const original = el.dataset.original || '';
                if (!original) continue;
                el.textContent = await translateDisplayText(original);
            }

            if (translationStatus && !translationStatus.classList.contains('error')) {
                if (translationEngine === 'chrome') {
                    setTranslationStatus('Title/Caption translated to Japanese via Chrome Translator (keywords stay English).', 'active');
                } else if (translationEngine === 'fallback') {
                    setTranslationStatus('Title/Caption translated to Japanese via online fallback (keywords stay English).', 'active');
                }
            }
        }

        function updateLightboxNav() {
            const multi = resultEntries.length > 1;
            lightboxPrev.disabled = !multi;
            lightboxNext.disabled = !multi;
        }
        function syncLightboxViewportSize() {
            const w = Math.floor(window.innerWidth * 0.95);
            const h = Math.floor(window.innerHeight * 0.95);
            lightbox.style.setProperty('--lightbox-w', w + 'px');
            lightbox.style.setProperty('--lightbox-h', h + 'px');
        }
        async function openLightboxAt(index) {
            if (blockMode || index < 0 || index >= resultEntries.length) return;
            lightboxIndex = index;
            const item = resultEntries[index];
            if (lightboxObjectUrl) {
                URL.revokeObjectURL(lightboxObjectUrl);
                lightboxObjectUrl = null;
            }
            lightboxObjectUrl = item.file ? URL.createObjectURL(item.file) : '';
            lightboxImg.src = lightboxObjectUrl || '';
            lightboxImg.alt = item.filename || '';
            lightboxFilename.textContent = item.filename || ('Image ' + (index + 1));
            lightboxTitle.textContent = item.title || '';
            lightboxCaptionText.textContent = item.caption || '';
            const kws = filterKeywords(item.keywords || []);
            lightboxKeywords.innerHTML = '';
            kws.forEach(k => {
                const span = document.createElement('span');
                span.className = 'keyword';
                span.textContent = k;
                lightboxKeywords.appendChild(span);
            });
            lightboxCounter.textContent = (index + 1) + ' / ' + resultEntries.length;
            updateLightboxNav();
            syncLightboxViewportSize();
            lightbox.classList.add('show');
            // Display-only translation (keywords stay original)
            const [titleTr, captionTr] = await Promise.all([
                translateDisplayText(item.title || ''),
                translateDisplayText(item.caption || ''),
            ]);
            if (lightboxIndex === index) {
                lightboxTitle.textContent = titleTr;
                lightboxCaptionText.textContent = captionTr;
            }
        }
        function showLightboxPrev() {
            if (resultEntries.length < 2 || lightboxIndex < 0) return;
            openLightboxAt((lightboxIndex - 1 + resultEntries.length) % resultEntries.length);
        }
        function showLightboxNext() {
            if (resultEntries.length < 2 || lightboxIndex < 0) return;
            openLightboxAt((lightboxIndex + 1) % resultEntries.length);
        }
        function closeLightbox() {
            lightbox.classList.remove('show');
            lightboxIndex = -1;
            if (lightboxObjectUrl) {
                URL.revokeObjectURL(lightboxObjectUrl);
                lightboxObjectUrl = null;
            }
            lightboxImg.removeAttribute('src');
            lightboxImg.alt = '';
            lightboxFilename.textContent = '';
            lightboxTitle.textContent = '';
            lightboxCaptionText.textContent = '';
            lightboxKeywords.innerHTML = '';
            lightboxCounter.textContent = '';
        }
        lightboxClose.onclick = (e) => { e.stopPropagation(); closeLightbox(); };
        lightboxPrev.onclick = (e) => { e.stopPropagation(); showLightboxPrev(); };
        lightboxNext.onclick = (e) => { e.stopPropagation(); showLightboxNext(); };
        lightbox.onclick = (e) => { if (e.target === lightbox) closeLightbox(); };
        lightboxPanel.onclick = (e) => e.stopPropagation();
        window.addEventListener('resize', () => {
            if (lightbox.classList.contains('show')) syncLightboxViewportSize();
        });
        document.addEventListener('keydown', (e) => {
            if (lightbox.classList.contains('show')) {
                if (e.key === 'Escape') { closeLightbox(); return; }
                if (e.key === 'ArrowLeft') { e.preventDefault(); showLightboxPrev(); return; }
                if (e.key === 'ArrowRight') { e.preventDefault(); showLightboxNext(); return; }
            }
            if (e.key === 'Escape' && blockMode) {
                cancelBlockMode();
            }
        });
        document.addEventListener('click', (e) => {
            const thumb = e.target.closest('img.thumb');
            if (thumb) {
                if (blockMode) return;
                e.preventDefault();
                const idx = parseInt(thumb.dataset.index, 10);
                if (!Number.isNaN(idx)) openLightboxAt(idx);
            }
        });

        function updateBlockApplyState() {
            blockApplyBtn.disabled = pendingBlock.size === 0;
            blockApplyBtn.textContent = pendingBlock.size > 0
                ? 'Apply (' + pendingBlock.size + ')'
                : 'Apply';
        }
        function setBlockMode(on) {
            blockMode = !!on;
            document.body.classList.toggle('block-mode', blockMode);
            blockModeToggle.checked = blockMode;
            blockModeBanner.classList.toggle('show', blockMode);
            if (!blockMode) pendingBlock.clear();
            updateBlockApplyState();
            if (resultEntries.length) renderResults();
        }
        function enterBlockMode() {
            closeLightbox();
            setBlockMode(true);
        }
        function cancelBlockMode() {
            pendingBlock.clear();
            setBlockMode(false);
        }
        function applyBlockMode() {
            if (pendingBlock.size === 0) {
                setBlockMode(false);
                return;
            }
            pendingBlock.forEach(k => ngKeywords.add(k));
            saveNgKeywords();
            pendingBlock.clear();
            setBlockMode(false);
        }
        blockModeToggle.addEventListener('change', () => {
            if (blockModeToggle.checked) {
                enterBlockMode();
                return;
            }
            if (pendingBlock.size > 0) {
                const ok = confirm(
                    'You have ' + pendingBlock.size + ' marked keyword(s). Discard and exit Blocking mode?'
                );
                if (!ok) {
                    blockModeToggle.checked = true;
                    return;
                }
            }
            cancelBlockMode();
        });
        blockApplyBtn.onclick = () => applyBlockMode();
        blockCancelBtn.onclick = () => cancelBlockMode();

        function showResultToolbar(show) {
            resultToolbar.classList.toggle('show', !!show);
            csvLink.style.display = show ? 'inline-block' : 'none';
            zipLink.style.display = show ? 'inline-block' : 'none';
            clearBtn.disabled = !show;
            if (!show) {
                setTranslationStatus('');
                if (blockMode) cancelBlockMode();
            }
        }

        function loadNgKeywords() {
            try {
                const s = localStorage.getItem(NG_STORAGE_KEY);
                ngKeywords = new Set(s ? JSON.parse(s) : []);
            } catch (e) { ngKeywords = new Set(); }
        }
        function saveNgKeywords() {
            localStorage.setItem(NG_STORAGE_KEY, JSON.stringify([...ngKeywords].sort()));
        }
        function isNgKeyword(k) {
            return ngKeywords.has(k.toLowerCase());
        }
        function filterKeywords(kw) {
            return (kw || []).filter(k => !isNgKeyword(k));
        }

        function renderNgList() {
            ngList.innerHTML = '';
            [...ngKeywords].sort().forEach(k => {
                const li = document.createElement('li');
                li.innerHTML = '<span>' + k + '</span><button type="button" class="removeBtn" data-k="' + k + '">Remove</button>';
                li.querySelector('.removeBtn').onclick = () => { ngKeywords.delete(k); saveNgKeywords(); renderNgList(); if (resultEntries.length) renderResults(); };
                ngList.appendChild(li);
            });
        }

        ngManageBtn.onclick = () => { ngModal.classList.add('show'); renderNgList(); };
        ngCloseBtn.onclick = () => ngModal.classList.remove('show');
        ngModal.onclick = e => { if (e.target === ngModal) ngModal.classList.remove('show'); };
        ngAddBtn.onclick = () => {
            const v = ngInput.value.trim().toLowerCase();
            if (v) { ngKeywords.add(v); saveNgKeywords(); renderNgList(); ngInput.value = ''; if (resultEntries.length) renderResults(); }
        };
        ngInput.onkeydown = e => { if (e.key === 'Enter') ngAddBtn.click(); };

        ngExportBtn.onclick = () => {
            const data = JSON.stringify([...ngKeywords].sort(), null, 2);
            const blob = new Blob([data], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = withDownloadTimestamp('ng-keywords.json');
            a.click();
            URL.revokeObjectURL(a.href);
        };
        ngImportBtn.onclick = () => ngImportFile.click();
        ngImportFile.onchange = async (e) => {
            const f = e.target.files[0];
            if (!f) return;
            try {
                const text = await f.text();
                let arr = [];
                try {
                    const data = JSON.parse(text);
                    arr = Array.isArray(data) ? data : (typeof data === 'string' ? data.split(/[\\s,]+/) : []);
                } catch {
                    arr = text.split(/[\\n\\r,]+/).map(s => s.trim()).filter(Boolean);
                }
                arr.forEach(k => { const v = String(k).trim().toLowerCase(); if (v) ngKeywords.add(v); });
                saveNgKeywords();
                renderNgList();
                if (resultEntries.length) renderResults();
                alert('Imported: ' + arr.length + ' item(s)');
            } catch (err) { alert('Import error: ' + err.message); }
            ngImportFile.value = '';
        };

        let ctxTargetKeyword = '';
        ctxMenu.onclick = e => e.stopPropagation();
        ctxNgBtn.onclick = () => {
            if (ctxTargetKeyword) { ngKeywords.add(ctxTargetKeyword.toLowerCase()); saveNgKeywords(); renderNgList(); if (resultEntries.length) renderResults(); }
            ctxMenu.classList.remove('show');
            ctxTargetKeyword = '';
        };
        document.addEventListener('click', () => ctxMenu.classList.remove('show'));
        document.addEventListener('contextmenu', e => {
            const kw = e.target.closest('.keyword');
            if (kw) {
                e.preventDefault();
                ctxTargetKeyword = kw.textContent.trim();
                ctxMenu.style.left = e.pageX + 'px';
                ctxMenu.style.top = e.pageY + 'px';
                ctxMenu.classList.add('show');
            }
        });

        function isImageFile(f) {
            return f.type.startsWith('image/') || IMG_EXTS.test(f.name || '');
        }

        function escapeAttr(s) {
            return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
        }
        function escapeHtml(s) {
            return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
        function downloadTimestamp() {
            const d = new Date();
            const p = (n) => String(n).padStart(2, '0');
            return (
                d.getFullYear() +
                p(d.getMonth() + 1) +
                p(d.getDate()) +
                p(d.getHours()) +
                p(d.getMinutes()) +
                p(d.getSeconds())
            );
        }
        function withDownloadTimestamp(filename) {
            const name = String(filename || 'download');
            const m = name.match(/^(.*?)(\.[^.]+)?$/);
            const stem = m[1] || 'download';
            const ext = m[2] || '';
            return stem + '_' + downloadTimestamp() + ext;
        }

        function bindCsvDownload() {
            csvLink.onclick = (e) => {
                e.preventDefault();
                if (!resultEntries.length) return;
                const rows = [['filename', 'title', 'caption', 'keywords']];
                resultEntries.forEach(item => {
                    const kw = filterKeywords(item.keywords);
                    rows.push([item.filename || 'image', item.title || '', item.caption || '', kw.join(',')]);
                });
                const csv = rows.map(r => r.map(c => '"' + String(c).replace(/"/g, '""') + '"').join(',')).join('\\n');
                const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = withDownloadTimestamp('tags.csv');
                a.click();
                URL.revokeObjectURL(a.href);
            };
        }

        function toUcs2Bytes(str) {
            const out = [];
            const s = String(str || '');
            for (let i = 0; i < s.length; i++) {
                const c = s.charCodeAt(i);
                out.push(c & 0xff, (c >> 8) & 0xff);
            }
            out.push(0, 0);
            return out;
        }
        function isJpegFile(file) {
            if (!file) return false;
            const name = (file.name || '').toLowerCase();
            return file.type === 'image/jpeg' || /\.jpe?g$/.test(name);
        }
        function arrayBufferToBinaryString(buf) {
            const bytes = new Uint8Array(buf);
            let s = '';
            const chunk = 0x8000;
            for (let i = 0; i < bytes.length; i += chunk) {
                s += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
            }
            return s;
        }
        function binaryStringToUint8Array(bin) {
            const out = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i) & 0xff;
            return out;
        }
        function uniqueZipName(name, used) {
            let base = name || 'image.jpg';
            if (!used.has(base)) { used.add(base); return base; }
            const m = base.match(/^(.*?)(\.[^.]+)?$/);
            const stem = m[1] || 'image';
            const ext = m[2] || '';
            let i = 2;
            let candidate = stem + '_' + i + ext;
            while (used.has(candidate)) {
                i += 1;
                candidate = stem + '_' + i + ext;
            }
            used.add(candidate);
            return candidate;
        }
        function embedExifJpeg(jpegBinary, meta) {
            let exifObj;
            try {
                exifObj = piexif.load(jpegBinary);
            } catch (err) {
                exifObj = { '0th': {}, Exif: {}, GPS: {} };
            }
            if (!exifObj['0th']) exifObj['0th'] = {};
            if (!exifObj.Exif) exifObj.Exif = {};

            const title = (meta.title || '').trim();
            const caption = (meta.caption || '').trim();
            const keywords = meta.keywords || [];
            const desc = title || caption;

            if (desc) {
                exifObj['0th'][piexif.ImageIFD.ImageDescription] = desc;
            }
            if (title) {
                exifObj['0th'][piexif.ImageIFD.XPTitle] = toUcs2Bytes(title);
            }
            if (caption) {
                exifObj['0th'][piexif.ImageIFD.XPComment] = toUcs2Bytes(caption);
            }
            if (keywords.length) {
                exifObj['0th'][piexif.ImageIFD.XPKeywords] = toUcs2Bytes(keywords.join(';'));
            }
            exifObj['0th'][piexif.ImageIFD.Software] = 'Stock Image Auto Tagger';

            const exifBytes = piexif.dump(exifObj);
            return piexif.insert(exifBytes, jpegBinary);
        }

        async function createTaggedZipBlob() {
            if (typeof JSZip === 'undefined' || typeof piexif === 'undefined') {
                throw new Error('ZIP libraries failed to load. Refresh the page and try again.');
            }
            const zip = new JSZip();
            const usedNames = new Set();

            // Images only — do not bundle CSV inside ZIP.
            // Chrome Safe Browsing often flags ZIP+CSV as uncommon/dangerous.
            // Use "Download CSV" separately for metadata.
            for (let i = 0; i < resultEntries.length; i++) {
                const item = resultEntries[i];
                const keywords = filterKeywords(item.keywords || []);
                const zipName = uniqueZipName(item.filename || ('image_' + (i + 1) + '.jpg'), usedNames);

                if (!item.file) continue;
                let bytes;
                if (isJpegFile(item.file)) {
                    const bin = arrayBufferToBinaryString(await item.file.arrayBuffer());
                    const tagged = embedExifJpeg(bin, {
                        title: item.title || '',
                        caption: item.caption || '',
                        keywords: keywords,
                    });
                    bytes = binaryStringToUint8Array(tagged);
                } else {
                    bytes = new Uint8Array(await item.file.arrayBuffer());
                }
                zip.file(zipName, bytes);
            }

            return zip.generateAsync({
                type: 'blob',
                mimeType: 'application/zip',
            });
        }

        async function saveZipWithUserGesture(filename) {
            // Open save dialog first while the click gesture is still valid
            // (Chrome blocks async <a download> after long ZIP work as "dangerous")
            let fileHandle = null;
            if (typeof window.showSaveFilePicker === 'function') {
                try {
                    fileHandle = await window.showSaveFilePicker({
                        suggestedName: filename,
                        types: [{
                            description: 'ZIP archive',
                            accept: { 'application/zip': ['.zip'] },
                        }],
                    });
                } catch (err) {
                    if (err && err.name === 'AbortError') return;
                    console.warn('[stock-tagger] showSaveFilePicker failed, falling back:', err);
                }
            }

            const blob = await createTaggedZipBlob();
            if (fileHandle) {
                const writable = await fileHandle.createWritable();
                await writable.write(blob);
                await writable.close();
                return;
            }

            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.rel = 'noopener';
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
        }

        function bindZipDownload() {
            zipLink.onclick = async (e) => {
                e.preventDefault();
                if (!resultEntries.length) return;
                zipLink.style.pointerEvents = 'none';
                try {
                    await saveZipWithUserGesture(withDownloadTimestamp('stock-tagger-export.zip'));
                } catch (err) {
                    alert('ZIP error: ' + err.message);
                } finally {
                    zipLink.style.pointerEvents = '';
                }
            };
        }

        function renderResults() {
            lastThumbUrls.forEach(u => URL.revokeObjectURL(u));
            lastThumbUrls = [];
            let html = '';
            resultEntries.forEach((item, i) => {
                const thumbUrl = item.file
                    ? (lastThumbUrls.push(URL.createObjectURL(item.file)), lastThumbUrls[lastThumbUrls.length - 1])
                    : '';
                const filtered = filterKeywords(item.keywords);
                html += '<div class="resultItem">';
                if (thumbUrl) {
                    const name = escapeAttr(item.filename || '');
                    html += '<div class="resultThumb"><img class="thumb" src="' + thumbUrl + '" alt="' + name + '" data-name="' + name + '" data-index="' + i + '" title="Click to enlarge" /></div>';
                }
                html += '<div class="resultBody">';
                html += '<h3>' + escapeHtml(item.filename || 'Image ' + (i + 1)) + '</h3>';
                html += '<p><strong>Title:</strong> <span data-display="title" data-index="' + i + '" data-original="' + escapeAttr(item.title || '') + '">' + escapeHtml(item.title || '') + '</span></p>';
                html += '<p><strong>Caption:</strong> <span data-display="caption" data-index="' + i + '" data-original="' + escapeAttr(item.caption || '') + '">' + escapeHtml(item.caption || '') + '</span></p>';
                if (filtered.length) {
                    html += '<p><strong>Keywords:</strong> ';
                    filtered.forEach(k => {
                        const key = String(k).trim().toLowerCase();
                        const pending = pendingBlock.has(key);
                        const tip = blockMode
                            ? (pending ? 'Click to unmark' : 'Click to mark for blocking')
                            : 'Turn on Blocking mode to exclude tags';
                        const cls = 'keyword' + (pending ? ' pending-block' : '');
                        html += '<span class="' + cls + '" title="' + escapeAttr(tip) + '" data-keyword="' + escapeAttr(key) + '">' + escapeHtml(k) + '</span>';
                    });
                    html += '</p>';
                }
                html += '</div></div>';
            });
            result.innerHTML = html;
            showResultToolbar(resultEntries.length > 0);
            updateBlockApplyState();
            applyResultTranslations();
        }

        result.addEventListener('click', (e) => {
            const kw = e.target.closest('.keyword');
            if (!kw || !blockMode) return;
            e.preventDefault();
            e.stopPropagation();
            const key = (kw.dataset.keyword || kw.textContent || '').trim().toLowerCase();
            if (!key) return;
            if (pendingBlock.has(key)) pendingBlock.delete(key);
            else pendingBlock.add(key);
            const pending = pendingBlock.has(key);
            const tip = pending ? 'Click to unmark' : 'Click to mark for blocking';
            result.querySelectorAll('.keyword').forEach(el => {
                if ((el.dataset.keyword || '').toLowerCase() !== key) return;
                el.classList.toggle('pending-block', pending);
                el.title = tip;
            });
            updateBlockApplyState();
        });

        async function processOneFile(file, current, total) {
            showProcessingProgress(
                'Processing ' + current + '/' + total + ' image(s)...',
                file.name || ('image ' + current),
                current,
                total
            );
            const formData = new FormData();
            formData.append('files', file);
            const res = await fetch('/tag', { method: 'POST', body: formData });
            const data = await res.json();
            if (!res.ok) {
                const msg = data.detail?.error || data.detail || JSON.stringify(data);
                throw new Error(msg);
            }
            const row = Array.isArray(data) ? data[0] : (data.results ? data.results[0] : data);
            return {
                file: file,
                filename: (row && row.filename) || file.name || 'image',
                title: (row && row.title) || '',
                caption: (row && row.caption) || '',
                keywords: (row && row.keywords) || [],
            };
        }

        function showProcessingProgress(text, filename, current, total) {
            const safeTotal = Math.max(total || 0, 1);
            const safeCurrent = Math.max(0, Math.min(current || 0, safeTotal));
            const pct = Math.round((safeCurrent / safeTotal) * 100);
            processingText.textContent = text;
            processingFile.textContent = filename || '';
            processingFill.style.width = pct + '%';
            processingBar.classList.add('show');
        }
        function hideProcessingBar() {
            processingBar.classList.remove('show');
            processingText.textContent = 'Processing...';
            processingFile.textContent = '';
            processingFill.style.width = '0%';
        }

        async function drainQueue() {
            if (busy) return;
            busy = true;
            dropZone.classList.add('busy');
            let lastError = '';
            try {
                while (fileQueue.length) {
                    const file = fileQueue.shift();
                    const current = processCompleted + 1;
                    const total = processTotal;
                    try {
                        const entry = await processOneFile(file, current, total);
                        resultEntries = [entry].concat(resultEntries);
                        renderResults();
                        processCompleted = current;
                        showProcessingProgress(
                            'Processing ' + processCompleted + '/' + processTotal + ' image(s)...',
                            file.name || '',
                            processCompleted,
                            processTotal
                        );
                    } catch (err) {
                        lastError = err.message || String(err);
                        processCompleted = current;
                        showProcessingProgress(
                            'Error on ' + current + '/' + total + ': ' + lastError,
                            file.name || '',
                            processCompleted,
                            processTotal
                        );
                    }
                }
            } finally {
                dropZone.classList.remove('busy');
                busy = false;
                if (fileQueue.length) {
                    drainQueue();
                    return;
                }
                if (lastError) {
                    showProcessingProgress('Completed with errors: ' + lastError, '', processCompleted, processTotal || 1);
                } else {
                    hideProcessingBar();
                }
                processCompleted = 0;
                processTotal = 0;
            }
        }

        function enqueueFiles(fileList) {
            const files = Array.from(fileList).filter(isImageFile);
            if (!files.length) return;
            if (blockMode) cancelBlockMode();
            ensureTranslator();
            fileQueue.push(...files);
            processTotal += files.length;
            drainQueue();
        }

        dropZone.ondragover = e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.add('dragover'); };
        dropZone.ondragleave = e => { e.preventDefault(); if (!e.currentTarget.contains(e.relatedTarget)) dropZone.classList.remove('dragover'); };
        dropZone.ondrop = e => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) enqueueFiles(e.dataTransfer.files);
        };
        fileInput.onchange = () => {
            if (fileInput.files.length) enqueueFiles(fileInput.files);
            fileInput.value = '';
        };

        clearBtn.onclick = () => {
            closeLightbox();
            lastThumbUrls.forEach(u => URL.revokeObjectURL(u));
            lastThumbUrls = [];
            resultEntries = [];
            fileQueue = [];
            processCompleted = 0;
            processTotal = 0;
            result.innerHTML = '';
            hideProcessingBar();
            showResultToolbar(false);
        };

        bindCsvDownload();
        bindZipDownload();
        loadNgKeywords();
    </script>
</body>
</html>
"""
