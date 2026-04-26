import asyncio
import json
import time
from typing import Any, Dict, List

import httpx

from app.config import settings
from app.schemas.contracts import CompareRequest, ModelSelection


class OpenRouterClient:
    def __init__(self) -> None:
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.api_key = settings.openrouter_api_key

    def _build_system_prompt(self, output_mode: str) -> str:
        safety = (
            "You are a Healthcare Information Assistant for education. "
            "Never provide diagnosis, prescriptions, treatment plans, or emergency instructions. "
            "Encourage seeking licensed medical professionals for personal conditions."
        )
        if output_mode == "json":
            return (
                f"{safety} Return valid JSON only. No markdown. "
                "Required keys: summary, safety_notice, key_points, limitations."
            )
        return safety

    async def _call_single(
        self,
        client: httpx.AsyncClient,
        model: ModelSelection,
        request: CompareRequest,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model.id,
            "messages": [
                {"role": "system", "content": self._build_system_prompt(request.output_mode)},
                {
                    "role": "user",
                    "content": (
                        f"Prompt Type: {request.prompt_type}\n"
                        f"Prompt Instructions:\n{request.prompt_text}\n\n"
                        f"Input:\n{request.input_text}\n\n"
                        f"Output mode required: {request.output_mode}"
                    ),
                },
            ],
            "temperature": 0.3,
        }

        started = time.perf_counter()
        try:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=90.0)
            response.raise_for_status()
            data = response.json()
            raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            latency_ms = (time.perf_counter() - started) * 1000

            parsed_json = None
            is_json_valid = False
            if request.output_mode == "json":
                try:
                    parsed_json = json.loads(raw)
                    is_json_valid = isinstance(parsed_json, dict)
                except json.JSONDecodeError:
                    parsed_json = None

            return {
                "model": model,
                "raw_response": raw,
                "parsed_json": parsed_json,
                "is_json_valid": is_json_valid,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as ex:  # pylint: disable=broad-except
            latency_ms = (time.perf_counter() - started) * 1000
            return {
                "model": model,
                "raw_response": f"Request failed: {str(ex)}",
                "parsed_json": None,
                "is_json_valid": False,
                "latency_ms": round(latency_ms, 2),
            }

    async def run_comparison(self, request: CompareRequest) -> List[Dict[str, Any]]:
        if not self.api_key:
            return [
                {
                    "model": m,
                    "raw_response": "OpenRouter key missing. Add OPENROUTER_API_KEY in backend/.env",
                    "parsed_json": None,
                    "is_json_valid": False,
                    "latency_ms": 0,
                }
                for m in request.models
            ]

        async with httpx.AsyncClient() as client:
            tasks = [self._call_single(client, model, request) for model in request.models]
            return await asyncio.gather(*tasks)
