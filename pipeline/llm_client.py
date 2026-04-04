# Async LLM client using Groq via OpenAI-compatible SDK.
import json
import logging
from openai import AsyncOpenAI
from pipeline.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = settings.LLM_MODEL

    async def complete(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        # Send a prompt, get raw text back.
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise

    async def complete_json(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_schema: dict = None,
    ) -> dict:
        # Parse response as JSON
        request_params = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }

        if json_schema:
            # constrained decoding with schema
            request_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": False,
                    "schema": json_schema,
                }
            }
        else:
            # JSON object mode (valid JSON, no schema)
            request_params["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.chat.completions.create(**request_params)
            raw = response.choices[0].message.content
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nRaw: {raw[:500]}")
            raise ValueError(f"LLM did not return valid JSON: {e}")
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise