"""LLM 统一适配层。

- Provider 可插拔：所有调用走 OpenAI 兼容接口，换模型只改 .env。
- 角色 → 模型映射：vision / reason / vision_fallback 等。
- DRY_RUN：无 Key 也能跑，返回内置模拟数据（见 mock.py）。
- 视觉：图片以 base64 data-url 作为 content part 传入。
- JSON 模式：强制结构化输出，失败重试 + 兜底解析。
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable

from ..config import Settings, get_settings
from . import mock

log = logging.getLogger("llm")


def _img_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def _extract_json(text: str) -> Any:
    """从模型回复里抠出 JSON（容忍 ```json 包裹 / 前后噪声）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    # 找第一个 { 或 [ 到最后一个 } 或 ]
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i : j + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(text)  # 让它抛错


class LLM:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self._clients: dict[str, Any] = {}

    # ---- provider 客户端缓存 ----
    def _client(self, provider: str):
        if provider not in self._clients:
            from openai import OpenAI

            key, base = self.s.provider_creds(provider)
            self._clients[provider] = OpenAI(api_key=key or "dry-run", base_url=base)
        return self._clients[provider]

    def _resolve(self, role: str) -> tuple[str, str]:
        spec = {
            "vision": self.s.vision_model,
            "reason": self.s.reason_model,
            "vision_fallback": self.s.vision_fallback_model,
            "asr": self.s.asr_model,
        }.get(role, role)
        provider, _, model = spec.partition(":")
        return provider, model

    # ---- 核心调用 ----
    def run(
        self,
        role: str,
        system: str,
        user: str,
        images: list[Path] | None = None,
        audio: tuple[Path, str] | None = None,    # (路径, 格式如 webm/mp4/wav/mp3)
        json_mode: bool = True,
        mock_fn: Callable[[], Any] | None = None,
        max_retries: int = 2,
    ) -> Any:
        """返回 json_mode=True 时为 dict/list，否则为 str。"""
        if self.s.llm_dry_run:
            log.info("[DRY_RUN] role=%s 返回模拟数据", role)
            if mock_fn is not None:
                return mock_fn()
            return {"_dry_run": True, "role": role} if json_mode else "（模拟模式）"

        provider, model = self._resolve(role)
        client = self._client(provider)

        content: Any = user
        if images or audio:
            content = [{"type": "text", "text": user}]
            for p in (images or []):
                content.append(
                    {"type": "image_url", "image_url": {"url": _img_data_url(p)}}
                )
            if audio:
                apath, afmt = audio
                b64 = base64.b64encode(Path(apath).read_bytes()).decode()
                content.append(
                    {"type": "input_audio", "input_audio": {"data": b64, "format": afmt}}
                )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if json_mode and self.s.use_json_response_format:
            kwargs["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = client.chat.completions.create(**kwargs)
                text = resp.choices[0].message.content or ""
                return _extract_json(text) if json_mode else text
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("LLM 调用失败 attempt=%d role=%s: %s", attempt, role, e)
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"LLM 调用最终失败 role={role}: {last_err}")


_singleton: LLM | None = None


def get_llm() -> LLM:
    global _singleton
    if _singleton is None:
        _singleton = LLM()
    return _singleton
