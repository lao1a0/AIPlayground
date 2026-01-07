from openai import AsyncOpenAI
from typing import Optional
from ..core.base import BaseLLM
from ..core.exceptions import APIKeyNotFoundError, ModelNotAvailableError
from ..config.settings import KIMI_API_KEY
import asyncio

class KimiLLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        # 如果未提供api_key，使用配置中的KIMI_API_KEY
        if api_key is None:
            api_key = KIMI_API_KEY
        
        if not api_key:
            raise APIKeyNotFoundError("Kimi API key not found")
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1")
        self.max_retries = max_retries

    async def _handle_api_call(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                if "insufficient_quota" in error_msg:
                    raise ModelNotAvailableError("Kimi API quota exceeded. Please check your billing details.")
                if "rate_limit_exceeded" in error_msg.lower():
                    if attempt == self.max_retries - 1:
                        raise
                    wait_time = (2 ** attempt) + 1
                    print(f"Rate limit hit, waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                raise

    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self._handle_api_call(
            self.client.chat.completions.create,
            model=kwargs.get("model", "kimi-k2-turbo-preview"),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
        )
        if response and response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""

    async def stream(self, prompt: str, **kwargs):
        response = await self._handle_api_call(
            self.client.chat.completions.create,
            model=kwargs.get("model", "kimi-k2-turbo-preview"),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
            stream=True
        )
        if response:
            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
