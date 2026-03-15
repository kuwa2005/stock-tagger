"""Florence-2 による画像タグ・キャプション生成"""
import torch
from PIL import Image
from typing import Dict, List, Optional, Any

# グローバルにモデル・プロセッサを保持（遅延ロード）
_model = None
_processor = None
_device = None

# florence-community は transformers ネイティブ対応（trust_remote_code 不要）
MODEL_ID = "florence-community/Florence-2-base-ft"


def _get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_model(model_id: str = MODEL_ID):
    """モデルをロード（初回のみ）"""
    global _model, _processor, _device
    if _model is not None:
        return

    _device = _get_device()
    # bfloat16 は一部 GPU で未対応のため float16 を使用
    dtype = torch.float16 if _device == "cuda" else torch.float32

    from transformers import AutoProcessor, Florence2ForConditionalGeneration

    _processor = AutoProcessor.from_pretrained(model_id)
    # device_map="cuda:0" で単一GPUに固定（マルチGPU時のデバイス不一致を回避）
    _model = Florence2ForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map="cuda:0" if _device == "cuda" else None,
    )
    if _device == "cpu":
        _model = _model.to("cpu")


def generate_caption(image: Image.Image, task: str = "<DETAILED_CAPTION>") -> str:
    """キャプションを生成"""
    global _model, _processor, _device
    if _model is None:
        load_model()

    inputs = _processor(
        text=task,
        images=image.convert("RGB"),
        return_tensors="pt",
    )
    device = next(_model.parameters()).device
    inputs = {k: v.to(device, _model.dtype if k == "pixel_values" else v.dtype) for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = _model.generate(
            **inputs,
            max_new_tokens=1024,
            do_sample=False,
            num_beams=3,
        )

    generated_text = _processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = _processor.post_process_generation(
        generated_text,
        task=task,
        image_size=(image.width, image.height),
    )
    # CAPTION / DETAILED_CAPTION は pure_text で文字列が返る
    if isinstance(parsed, str):
        return parsed.strip()
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, str):
                return v.strip()
    return str(parsed).strip()


def generate_object_detection(image: Image.Image) -> Dict[str, Any]:
    """物体検出（バウンディングボックス）を生成"""
    global _model, _processor, _device
    if _model is None:
        load_model()

    task = "<OD>"
    inputs = _processor(
        text=task,
        images=image.convert("RGB"),
        return_tensors="pt",
    )
    device = next(_model.parameters()).device
    inputs = {k: v.to(device, _model.dtype if k == "pixel_values" else v.dtype) for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = _model.generate(
            **inputs,
            max_new_tokens=1024,
            do_sample=False,
            num_beams=3,
        )

    generated_text = _processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = _processor.post_process_generation(
        generated_text,
        task=task,
        image_size=(image.width, image.height),
    )
    return parsed if isinstance(parsed, dict) else {"objects": parsed}


def tag_image(
    image: Image.Image,
    max_keywords: int = 20,
    include_od: bool = False,
    use_ram: bool = True,
) -> Dict[str, any]:
    """
    画像から title, caption, keywords を生成。
    use_ram=True の場合は RAM++ でタグを補強（精度向上）。
    include_od=True の場合は物体検出結果も含める。
    """
    from .utils import caption_to_keywords, merge_keywords

    caption = generate_caption(image, task="<DETAILED_CAPTION>")
    title = generate_caption(image, task="<CAPTION>")
    if not title:
        title = caption[:80] if caption else ""

    # キーワード: RAM++ と Florence-2 のキャプションから統合
    caption_keywords = caption_to_keywords(caption, max_keywords=max_keywords * 2)
    if use_ram:
        try:
            from .ram_tag import get_ram_tags
            ram_tags = get_ram_tags(image)
            keywords = merge_keywords(ram_tags, caption_keywords, max_keywords=max_keywords)
        except Exception:
            keywords = caption_keywords[:max_keywords]
    else:
        keywords = caption_keywords[:max_keywords]

    result = {
        "title": title,
        "caption": caption,
        "keywords": keywords,
    }

    if include_od:
        try:
            od = generate_object_detection(image)
            result["objects"] = od
        except Exception:
            result["objects"] = {}

    return result
