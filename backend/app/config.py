"""集中配置，全部来自环境变量 / .env。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 运行模式
    llm_dry_run: bool = True

    # 访问保护（公网暴露时用 HTTP Basic Auth；密码为空则不拦截，本地开发用）
    basic_auth_user: str = "review"
    basic_auth_pass: str = ""

    # Providers（OpenAI 兼容）
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    bailian_api_key: str = ""
    bailian_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 是否给请求带 response_format=json_object（OpenRouter 多模型兼容性不一，默认关，靠 _extract_json 兜底）
    use_json_response_format: bool = False

    # 模型角色映射 provider:model_id  （注意 OpenRouter 的 model_id 里含 "/"）
    # 读图/提取需视觉模型（DeepSeek 在 OpenRouter 不收图片）
    vision_model: str = "openrouter:qwen/qwen3-vl-235b-a22b-instruct"
    # 推理/分析/出题/讲解（DeepSeek 便宜且强）
    reason_model: str = "openrouter:deepseek/deepseek-v4-flash"
    # 手写识别兜底（不同家视觉模型）
    vision_fallback_model: str = "openrouter:google/gemini-2.5-flash"
    # 语音转文字(音频→通顺文字),用 OpenRouter 上支持音频输入的 Gemini Flash-Lite
    asr_model: str = "openrouter:google/gemini-2.5-flash-lite-preview-09-2025"
    tts_model: str = "bailian:cosyvoice-v1"

    # App
    data_dir: str = "./data"
    max_image_edge: int = 1600
    jpeg_quality: int = 82

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = self.data_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.data_path / "app.sqlite3"

    def provider_creds(self, provider: str) -> tuple[str, str]:
        """返回 (api_key, base_url)。"""
        if provider == "openrouter":
            return self.openrouter_api_key, self.openrouter_base_url
        if provider == "deepseek":
            return self.deepseek_api_key, self.deepseek_base_url
        if provider == "bailian":
            return self.bailian_api_key, self.bailian_base_url
        raise ValueError(f"未知 provider: {provider}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
