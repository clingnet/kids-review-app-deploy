"""语音转文字 + 通顺化:音频 → 去停顿/纠正的通顺中文。"""
from __future__ import annotations

import uuid
from pathlib import Path

from ..config import get_settings
from ..llm import get_llm, mock, prompts

# content-type / 后缀 → input_audio 的 format
_FMT = {
    "audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav",
    "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3",
    "audio/mp4": "mp4", "audio/m4a": "m4a", "audio/aac": "aac",
    "audio/x-m4a": "m4a", "audio/flac": "flac",
}


def _save(raw: bytes, content_type: str | None, filename: str | None) -> tuple[str, str]:
    ext = "webm"
    if content_type and content_type in _FMT:
        ext = _FMT[content_type]
    elif filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    path = get_settings().uploads_path / f"voice_{uuid.uuid4().hex}.{ext}"
    path.write_bytes(raw)
    return str(path), ext


def transcribe(raw: bytes, content_type: str | None = None,
               filename: str | None = None) -> dict:
    path, fmt = _save(raw, content_type, filename)
    res = get_llm().run(
        role="asr",
        system=prompts.ASR_SYSTEM,
        user=prompts.ASR_USER,
        audio=(Path(path), fmt),
        json_mode=True,
        mock_fn=mock.asr,
    )
    return {"text": (res.get("text") or "").strip()}
