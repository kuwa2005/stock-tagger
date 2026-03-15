"""Stock Image Auto Tagger - FastAPI アプリケーション"""
import io
import csv
import os
from typing import List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from PIL import Image

from .tagger import tag_image

app = FastAPI(
    title="Stock Image Auto Tagger",
    description="フォトストック向け画像タグ・キャプション自動生成API",
    version="0.1.0",
)


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
            raise HTTPException(status_code=400, detail={"error": f"画像の読み込みに失敗しました: {e}"})
        try:
            result = tag_image(img, include_od=include_od, use_ram=use_ram_flag)
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": str(e)})
        result["filename"] = f.filename or "image"
        results.append(result)
    if not results:
        raise HTTPException(status_code=400, detail={"error": "有効な画像がありません"})
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
        raise HTTPException(status_code=400, detail={"error": "有効な画像がありません"})

    output.seek(0)
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tags.csv"},
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    """WebUI"""
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Image Auto Tagger</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        h1 { font-size: 1.5rem; }
        .upload { border: 2px dashed #ccc; border-radius: 8px; padding: 2rem; text-align: center; margin: 1rem 0; }
        .upload.dragover { border-color: #4a9; background: #f0fff0; }
        input[type="file"] { display: none; }
        .btn { background: #4a9; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 1rem; }
        .btn:hover { background: #389; }
        .btn:disabled { background: #999; cursor: not-allowed; }
        .fileCount { font-size: 0.9rem; color: #666; margin-bottom: 0.5rem; }
        #preview { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }
        #preview img { max-width: 120px; max-height: 120px; object-fit: cover; border-radius: 4px; }
        .btnClear { background: #888; }
        .btnClear:hover { background: #666; }
        .actionBar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 1rem 0; }
        .actionBar .btn { margin: 0; }
        .actionBar a.dl { margin: 0; }
        #result { margin-top: 1.5rem; padding: 1rem; background: #f8f8f8; border-radius: 8px; white-space: pre-wrap; }
        .resultItem { display: flex; gap: 1rem; margin-bottom: 1.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid #e0e0e0; }
        .resultItem:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .resultThumb { flex-shrink: 0; }
        .resultThumb img { max-width: 120px; max-height: 120px; object-fit: cover; border-radius: 4px; }
        .resultBody { flex: 1; min-width: 0; }
        .keyword { display: inline-block; background: #e0e0e0; padding: 0.2rem 0.5rem; margin: 0.2rem; border-radius: 4px; font-size: 0.9rem; cursor: context-menu; }
        .keyword.ng { text-decoration: line-through; opacity: 0.6; }
        a.dl { color: #4a9; }
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
    </style>
</head>
<body>
    <h1>Stock Image Auto Tagger</h1>
    <p>画像をアップロードすると、AIがタグ・タイトル・説明文を自動生成します。</p>
    <p><button type="button" class="btn btnNg" id="ngManageBtn">NGキーワード管理</button></p>

    <div class="upload" id="dropZone">
        <p>画像をドラッグ＆ドロップ（複数可）、または</p>
        <label><span class="btn">ファイルを選択</span><input type="file" id="fileInput" accept="image/*" multiple></label>
    </div>

    <div id="previewWrap">
        <p id="fileCount" class="fileCount"></p>
        <div id="preview"></div>
        <div class="actionBar">
            <button type="button" class="btn btnClear" id="clearBtn" style="display:none;">選択をクリア</button>
            <button class="btn" id="tagBtn" disabled>タグ生成</button>
            <a class="dl" id="csvLink" style="display:none;">CSV ダウンロード</a>
        </div>
    </div>

    <div id="result"></div>

    <div class="modal" id="ngModal">
        <div class="modalContent">
            <h2>NGキーワード管理</h2>
            <div class="ngAddRow">
                <input type="text" id="ngInput" placeholder="NGキーワードを入力" />
                <button type="button" class="btn" id="ngAddBtn">追加</button>
            </div>
            <ul class="ngList" id="ngList"></ul>
            <div class="modalActions">
                <button type="button" class="btn" id="ngExportBtn">Export</button>
                <button type="button" class="btn" id="ngImportBtn">Import</button>
                <input type="file" id="ngImportFile" accept=".json,.txt,application/json,text/plain" style="display:none" />
                <button type="button" class="btn btnClear" id="ngCloseBtn">閉じる</button>
            </div>
        </div>
    </div>

    <div class="ctxMenu" id="ctxMenu">
        <button type="button" id="ctxNgBtn">NGキーワードに追加</button>
    </div>

    <script>
        const NG_STORAGE_KEY = 'stock-tagger-ng-keywords';
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const preview = document.getElementById('preview');
        const fileCount = document.getElementById('fileCount');
        const clearBtn = document.getElementById('clearBtn');
        const tagBtn = document.getElementById('tagBtn');
        const result = document.getElementById('result');
        const csvLink = document.getElementById('csvLink');
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

        let selectedFiles = [];
        let lastTagResults = [];
        let lastThumbUrls = [];
        let ngKeywords = new Set();
        const IMG_EXTS = /\.(jpe?g|png|gif|webp|bmp)$/i;

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
                li.innerHTML = '<span>' + k + '</span><button type="button" class="removeBtn" data-k="' + k + '">削除</button>';
                li.querySelector('.removeBtn').onclick = () => { ngKeywords.delete(k); saveNgKeywords(); renderNgList(); if (lastTagResults.length) renderResults(lastTagResults); };
                ngList.appendChild(li);
            });
        }

        ngManageBtn.onclick = () => { ngModal.classList.add('show'); renderNgList(); };
        ngCloseBtn.onclick = () => ngModal.classList.remove('show');
        ngModal.onclick = e => { if (e.target === ngModal) ngModal.classList.remove('show'); };
        ngAddBtn.onclick = () => {
            const v = ngInput.value.trim().toLowerCase();
            if (v) { ngKeywords.add(v); saveNgKeywords(); renderNgList(); ngInput.value = ''; if (lastTagResults.length) renderResults(lastTagResults); }
        };
        ngInput.onkeydown = e => { if (e.key === 'Enter') ngAddBtn.click(); };

        ngExportBtn.onclick = () => {
            const data = JSON.stringify([...ngKeywords].sort(), null, 2);
            const blob = new Blob([data], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'ng-keywords.json';
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
                if (lastTagResults.length) renderResults(lastTagResults);
                alert('インポートしました: ' + arr.length + '件');
            } catch (err) { alert('インポートエラー: ' + err.message); }
            ngImportFile.value = '';
        };

        let ctxTargetKeyword = '';
        ctxMenu.onclick = e => e.stopPropagation();
        ctxNgBtn.onclick = () => {
            if (ctxTargetKeyword) { ngKeywords.add(ctxTargetKeyword.toLowerCase()); saveNgKeywords(); renderNgList(); if (lastTagResults.length) renderResults(lastTagResults); }
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

        function updatePreview() {
            preview.querySelectorAll('img').forEach(img => URL.revokeObjectURL(img.src));
            preview.innerHTML = '';
            selectedFiles.forEach(f => {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(f);
                img.alt = f.name;
                preview.appendChild(img);
            });
            fileCount.textContent = selectedFiles.length > 0 ? selectedFiles.length + '枚の画像を選択中' : '';
            clearBtn.style.display = selectedFiles.length > 0 ? 'inline-block' : 'none';
            tagBtn.disabled = selectedFiles.length === 0;
        }

        function addFiles(files) {
            const newFiles = Array.from(files).filter(isImageFile);
            const names = new Set(selectedFiles.map(f => f.name + f.size));
            newFiles.forEach(f => {
                if (!names.has(f.name + f.size)) {
                    selectedFiles.push(f);
                    names.add(f.name + f.size);
                }
            });
            updatePreview();
        }

        function replaceFiles(files) {
            selectedFiles = Array.from(files).filter(isImageFile);
            updatePreview();
        }

        function renderResults(results) {
            lastThumbUrls.forEach(u => URL.revokeObjectURL(u));
            lastThumbUrls = [];
            let html = '';
            results.forEach((item, i) => {
                const thumbUrl = selectedFiles[i] ? (lastThumbUrls.push(URL.createObjectURL(selectedFiles[i])), lastThumbUrls[lastThumbUrls.length-1]) : '';
                const filtered = filterKeywords(item.keywords);
                html += '<div class="resultItem">';
                if (thumbUrl) html += '<div class="resultThumb"><img src="' + thumbUrl + '" alt="" /></div>';
                html += '<div class="resultBody">';
                html += '<h3>' + (item.filename || '画像' + (i+1)) + '</h3>';
                html += '<p><strong>タイトル:</strong> ' + (item.title || '') + '</p>';
                html += '<p><strong>説明:</strong> ' + (item.caption || '') + '</p>';
                if (filtered.length) {
                    html += '<p><strong>キーワード:</strong> ';
                    filtered.forEach(k => html += '<span class="keyword">' + k + '</span>');
                    html += '</p>';
                }
                html += '</div></div>';
            });
            result.innerHTML = html;
        }

        dropZone.ondragover = e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.add('dragover'); };
        dropZone.ondragleave = e => { e.preventDefault(); if (!e.currentTarget.contains(e.relatedTarget)) dropZone.classList.remove('dragover'); };
        dropZone.ondrop = e => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
        };
        fileInput.onchange = () => { if (fileInput.files.length) replaceFiles(fileInput.files); fileInput.value = ''; };

        clearBtn.onclick = () => {
            lastThumbUrls.forEach(u => URL.revokeObjectURL(u));
            lastThumbUrls = [];
            selectedFiles = []; updatePreview(); result.innerHTML = ''; csvLink.style.display = 'none'; lastTagResults = [];
        };

        tagBtn.onclick = async () => {
            if (selectedFiles.length === 0) return;
            tagBtn.disabled = true;
            result.textContent = '処理中...';
            csvLink.style.display = 'none';
            const formData = new FormData();
            selectedFiles.forEach(f => formData.append('files', f));
            try {
                const res = await fetch('/tag', { method: 'POST', body: formData });
                const data = await res.json();
                if (!res.ok) {
                    const msg = data.detail?.error || data.detail || JSON.stringify(data);
                    result.innerHTML = '<p style="color:#c00;">エラー: ' + msg + '</p>';
                    tagBtn.disabled = false;
                    return;
                }
                const r = Array.isArray(data) ? data : (data.results || [data]);
                lastTagResults = r.map(item => ({ ...item, keywords: item.keywords || [] }));
                renderResults(lastTagResults);

                csvLink.download = 'tags.csv';
                csvLink.style.display = 'inline-block';
                csvLink.onclick = (e) => {
                    e.preventDefault();
                    const rows = [['filename', 'title', 'caption', 'keywords']];
                    lastTagResults.forEach(item => {
                        const kw = filterKeywords(item.keywords);
                        rows.push([item.filename || 'image', item.title || '', item.caption || '', kw.join(',')]);
                    });
                    const csv = rows.map(r => r.map(c => '"' + String(c).replace(/"/g, '""') + '"').join(',')).join('\\n');
                    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
                    const a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = 'tags.csv';
                    a.click();
                    URL.revokeObjectURL(a.href);
                };
            } catch (err) {
                result.innerHTML = '<p style="color:#c00;">エラー: ' + err.message + '</p>';
            }
            tagBtn.disabled = false;
        };

        loadNgKeywords();
    </script>
</body>
</html>
"""
