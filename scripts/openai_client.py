"""
OpenAI client factory (configurable).

通过环境变量控制网络鲁棒性（都不是密钥，可公开写进 .env.example）：
- OPENAI_TIMEOUT: 总超时秒数（默认 60）
- OPENAI_CONNECT_TIMEOUT: 连接超时秒数（默认 10）
- OPENAI_FORCE_IPV4: 1/0，是否强制走 IPv4（默认 0）
- OPENAI_PROXY: 可选代理，例如 http://127.0.0.1:7890（默认空=不用）
"""

import os
import httpx
from openai import OpenAI, DefaultHttpxClient


def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def make_openai_client(api_key: str) -> OpenAI:
    if not api_key:
        raise RuntimeError("API key is empty")

    # 读取配置（都有默认值）
    timeout_total = float(os.getenv("OPENAI_TIMEOUT", "60"))
    connect_timeout = float(os.getenv("OPENAI_CONNECT_TIMEOUT", "10"))
    force_ipv4 = _truthy(os.getenv("OPENAI_FORCE_IPV4", "0"))
    proxy = os.getenv("OPENAI_PROXY") or None

    # httpx 超时配置：总超时 + connect 超时
    timeout = httpx.Timeout(timeout_total, connect=connect_timeout)

    # 强制 IPv4：local_address="0.0.0.0"
    transport = httpx.HTTPTransport(local_address="0.0.0.0") if force_ipv4 else httpx.HTTPTransport()

    http_client = DefaultHttpxClient(
        proxy=proxy,
        transport=transport,
    )

    return OpenAI(api_key=api_key, http_client=http_client, timeout=timeout)
