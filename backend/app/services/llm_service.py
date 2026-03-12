"""推理服务封装（sglang 部署安诊儿，OpenAI 兼容接口）

通过 OpenAI 兼容 API 调用 sglang 部署的安诊儿模型。
设计为可替换的抽象层，未来可切换其他模型或推理服务。
"""

import time
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMResponse:
    """模型推理响应"""
    def __init__(
        self,
        content: str,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
    ):
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms


class LLMService:
    """大模型推理服务"""

    def __init__(self):
        self.base_url = settings.VLLM_BASE_URL
        self.model_name = settings.VLLM_MODEL_NAME
        self.timeout = settings.VLLM_TIMEOUT
        self.max_tokens = settings.VLLM_MAX_TOKENS
        self.temperature = settings.VLLM_TEMPERATURE

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """调用模型进行对话推理"""
        start_time = time.time()

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            latency_ms = int((time.time() - start_time) * 1000)
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return LLMResponse(
                content=choice["message"]["content"],
                model=data.get("model", self.model_name),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency_ms,
            )
        except httpx.TimeoutException:
            logger.error(f"推理服务超时 (>{self.timeout}s)")
            raise
        except Exception as e:
            logger.error(f"推理服务失败: {e}")
            raise

    async def health_check(self) -> bool:
        """检查推理服务（sglang）是否可用"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


llm_service = LLMService()
