"""RAM++ (Recognize Anything Model++) による画像タグ生成"""
import sys
from pathlib import Path

# ram パッケージを import するために /app を path に追加
_app_root = Path(__file__).resolve().parents[1]
if str(_app_root) not in sys.path:
    sys.path.insert(0, str(_app_root))

import torch
from PIL import Image
from typing import List

_ram_model = None
_ram_transform = None
_device = None
_ram_root = _app_root / "ram"


def _get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _get_checkpoint_path() -> Path:
    """Hugging Face からダウンロードしたチェックポイントのパス"""
    import os
    cache_dir = Path(os.environ.get("HF_HOME", "/data/hf_cache"))
    checkpoint_dir = cache_dir / "ram_plus"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / "ram_plus_swin_large_14m.pth"
    if not path.exists():
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id="xinyu1205/recognize-anything-plus-model",
            filename="ram_plus_swin_large_14m.pth",
            local_dir=str(checkpoint_dir),
            local_dir_use_symlinks=False,
        )
        path = Path(downloaded)
    return path


def load_ram_model():
    """RAM++ モデルをロード（初回のみ）"""
    global _ram_model, _ram_transform, _device
    if _ram_model is not None:
        return

    _device = _get_device()
    checkpoint_path = _get_checkpoint_path()

    # ram パッケージのパスを設定（CONFIG_PATH は ram/models/utils で使用）
    from ram.models import ram_plus
    from ram import inference_ram, get_transform

    _ram_transform = get_transform(image_size=384)
    _ram_model = ram_plus(
        pretrained=str(checkpoint_path),
        image_size=384,
        vit="swin_l",
    )
    _ram_model.eval()
    _ram_model = _ram_model.to(_device)


def get_ram_tags(image: Image.Image) -> List[str]:
    """
    画像から RAM++ でタグを生成。
    戻り値: 英語タグのリスト
    """
    global _ram_model, _ram_transform, _device
    if _ram_model is None:
        load_ram_model()

    from ram import inference_ram

    img_tensor = _ram_transform(image.convert("RGB")).unsqueeze(0).to(_device)
    with torch.no_grad():
        tags_en, _tags_zh = inference_ram(img_tensor, _ram_model)

    # "tag1 | tag2 | tag3" 形式をリストに変換
    if tags_en:
        return [t.strip() for t in tags_en.split("|") if t.strip()]
    return []
