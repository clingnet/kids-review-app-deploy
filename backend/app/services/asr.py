"""语音转文字:音频 → 通顺中文。

优先走火山大模型语音识别(seedasr WebSocket)；asr_model 不是 volcengine 时回退到
原 LLM(OpenAI 兼容 input_audio)路径。统一用 ffmpeg 把上传音频转 16k 单声道 WAV。
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from pathlib import Path

from ..config import get_settings
from ..llm import get_llm, mock, prompts, volc_asr

log = logging.getLogger("asr")

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


def _to_wav16k(path: str) -> bytes:
    """用 ffmpeg 把任意音频转成 16k 单声道 16bit WAV 字节。"""
    cmd = ["ffmpeg", "-v", "quiet", "-y", "-i", path,
           "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-f", "wav", "-"]
    try:
        r = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.stdout
    except FileNotFoundError:
        raise RuntimeError("未安装 ffmpeg，无法转换音频（请在服务器安装 ffmpeg）")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"音频转码失败: {e.stderr.decode('utf-8', 'replace')[:200]}")


async def transcribe(raw: bytes, content_type: str | None = None,
                     filename: str | None = None) -> dict:
    s = get_settings()
    if s.llm_dry_run:
        return {"text": (mock.asr().get("text") or "").strip()}

    path, fmt = _save(raw, content_type, filename)
    provider = (s.asr_model or "").split(":", 1)[0]

    if provider in ("volcengine", "ark"):
        wav = await asyncio.to_thread(_to_wav16k, path)
        text = await volc_asr.transcribe_wav(wav)
        return {"text": (text or "").strip()}

    # 回退：原 OpenAI 兼容 input_audio 路径（同步，放线程池）
    def _old():
        return get_llm().run(
            role="asr", system=prompts.ASR_SYSTEM, user=prompts.ASR_USER,
            audio=(Path(path), fmt), json_mode=True, mock_fn=mock.asr,
        )
    res = await asyncio.to_thread(_old)
    return {"text": (res.get("text") or "").strip()}
