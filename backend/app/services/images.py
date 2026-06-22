"""图片预处理：压缩长边、转 JPEG，降低模型视觉 token 成本（最大省钱杠杆）。"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from ..config import get_settings


def save_and_compress(raw: bytes, orig_name: str) -> tuple[str, str]:
    """保存上传图片（压缩后）。返回 (相对文件名, 绝对路径)。"""
    s = get_settings()
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)        # 修正手机拍照方向
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    edge = s.max_image_edge
    w, h = img.size
    if max(w, h) > edge:
        scale = edge / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    fname = f"{uuid.uuid4().hex}.jpg"
    path = s.uploads_path / fname
    img.save(path, "JPEG", quality=s.jpeg_quality, optimize=True)
    return fname, str(path)
