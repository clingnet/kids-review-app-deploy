"""火山大模型语音识别(seedasr) —— WebSocket 单流(nostream)客户端。

鉴权：单个 X-Api-Key（即 ARK key）+ X-Api-Resource-Id=volc.seedasr.sauc.duration。
协议：二进制帧(header4字节 + seq + payloadSize + gzip(json/audio))。
输入：16k 单声道 16bit PCM 的 WAV 字节。返回：转写文本。
依赖 websockets（uvicorn[standard] 已自带）。
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import struct
import uuid

from ..config import get_settings

log = logging.getLogger("volc_asr")

_PROTO = 0x11  # version=1, header_size=1(=4字节)


def _header(msg_type: int, flags: int) -> bytes:
    # serialization=JSON(1), compression=gzip(1) -> 0x11
    return bytes([_PROTO, (msg_type << 4) | flags, 0x11, 0x00])


def _full_client_request(seq: int, fmt: str = "wav", rate: int = 16000) -> bytes:
    cfg = {
        "user": {"uid": "kids-review"},
        "audio": {"format": fmt, "codec": "raw", "rate": rate, "bits": 16, "channel": 1},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
        },
    }
    payload = gzip.compress(json.dumps(cfg).encode("utf-8"))
    return _header(0b0001, 0b0001) + struct.pack(">i", seq) + struct.pack(">I", len(payload)) + payload


def _audio_request(audio: bytes, seq: int, last: bool) -> bytes:
    payload = gzip.compress(audio)
    flags = 0b0011 if last else 0b0001
    s = -seq if last else seq
    return _header(0b0010, flags) + struct.pack(">i", s) + struct.pack(">I", len(payload)) + payload


def _parse(msg: bytes):
    msg_type = msg[1] >> 4
    flags = msg[1] & 0x0f
    comp = msg[2] & 0x0f
    p = msg[4:]
    if flags & 0x01:
        p = p[4:]  # sequence
    last = bool(flags & 0x02)
    if msg_type == 0b1111:  # error
        p = p[4:]  # error code
    if len(p) < 4:
        return msg_type, last, None
    size = struct.unpack(">I", p[:4])[0]
    p = p[4:4 + size]
    if comp == 0b0001:
        try:
            p = gzip.decompress(p)
        except Exception:
            pass
    try:
        return msg_type, last, json.loads(p.decode("utf-8"))
    except Exception:
        return msg_type, last, None


def _extract_text(body) -> str:
    if not isinstance(body, dict):
        return ""
    r = body.get("result")
    if isinstance(r, dict):
        return r.get("text") or ""
    if isinstance(r, list) and r and isinstance(r[0], dict):
        return r[0].get("text") or ""
    return body.get("text") or ""


# 单包最大音频字节数（过大时分片发送，避免单帧过大）
_CHUNK = 200 * 1024


async def transcribe_wav(wav_bytes: bytes, timeout: float = 30.0) -> str:
    """把 16k 单声道 16bit 的 WAV 字节送火山识别，返回文本。"""
    import websockets

    s = get_settings()
    key = s.volcengine_api_key
    if not key:
        raise RuntimeError("缺少 VOLCENGINE_API_KEY")
    rid = str(uuid.uuid4())
    headers = {
        "X-Api-Key": key,
        "X-Api-Resource-Id": s.volc_asr_resource_id,
        "X-Api-Request-Id": rid,
        "X-Api-Connect-Id": rid,
        "X-Api-Sequence": "-1",
    }
    text = ""
    async with websockets.connect(s.volc_asr_url, additional_headers=headers, max_size=None) as ws:
        await ws.send(_full_client_request(1))
        # 分片发送音频，最后一片标记 last
        seq = 2
        n = len(wav_bytes)
        if n <= _CHUNK:
            await ws.send(_audio_request(wav_bytes, seq, last=True))
        else:
            off = 0
            while off < n:
                chunk = wav_bytes[off:off + _CHUNK]
                off += _CHUNK
                last = off >= n
                await ws.send(_audio_request(chunk, seq, last=last))
                seq += 1
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg_type, last, body = _parse(msg)
            if msg_type == 0b1111:
                raise RuntimeError(f"火山ASR错误: {body}")
            t = _extract_text(body)
            if t:
                text = t
            if last:
                break
    return text.strip()
