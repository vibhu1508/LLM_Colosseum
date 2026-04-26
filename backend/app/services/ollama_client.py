import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List

import httpx

from app.config import settings
from app.schemas.contracts import CompareRequest, ModelSelection


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")

    def _build_system_prompt(self, output_mode: str, role_override: str | None = None) -> str:
        safety = (
            "You are a Healthcare Information Assistant for education. "
            "Never provide diagnosis, prescriptions, treatment plans, or emergency instructions. "
            "Encourage seeking licensed medical professionals for personal conditions."
        )
        role_instruction = ""
        if role_override and role_override.strip():
            role_instruction = (
                f" For this run, adopt the communication style and perspective of a {role_override.strip()} "
                "while still following all safety constraints."
            )

        if output_mode == "json":
            return (
                f"{safety}{role_instruction} Return valid JSON only. No markdown. "
                "Required keys: summary, safety_notice, key_points, limitations."
            )
        return f"{safety}{role_instruction}"

    def _build_user_content(self, request: CompareRequest) -> str:
        parts: List[str] = [f"Prompt Type: {request.prompt_type}"]
        valid_examples = [example for example in request.examples if example.input.strip() and example.output.strip()]

        if request.prompt_type == "one-shot":
            if valid_examples:
                parts.append("One-shot example:")
                parts.append(self._format_example_block(valid_examples[0].input, valid_examples[0].output, 1))
            else:
                parts.append("No one-shot example provided by user.")
        elif request.prompt_type == "few-shot":
            if valid_examples:
                parts.append("Few-shot examples:")
                for index, example in enumerate(valid_examples, start=1):
                    parts.append(self._format_example_block(example.input, example.output, index))
            else:
                parts.append("No few-shot examples provided by user.")
        elif request.prompt_type == "chain-of-thought":
            parts.append("Reason step-by-step internally, but return only a concise final answer.")

        parts.append(f"Prompt Instructions:\n{request.prompt_text}")
        parts.append(f"Input:\n{request.input_text}")
        parts.append(f"Output mode required: {request.output_mode}")
        return "\n\n".join(parts)

    def _format_example_block(self, input_text: str, output_text: str, index: int) -> str:
        return (
            f"Example {index} Input: {input_text.strip()}\n"
            "Example Output:\n"
            f"{output_text.strip()}"
        )

    async def _call_single(
        self,
        client: httpx.AsyncClient,
        model: ModelSelection,
        request: CompareRequest,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model.id,
            "messages": [
                {
                    "role": "system",
                    "content": self._build_system_prompt(request.output_mode, request.role_override),
                },
                {
                    "role": "user",
                    "content": self._build_user_content(request),
                },
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }

        if request.output_mode == "json":
            payload["format"] = "json"

        started = time.perf_counter()
        try:
            response = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=300.0)
            response.raise_for_status()
            data = response.json()
            raw = data.get("message", {}).get("content", "")
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
                "raw_response": f"Request failed: {repr(ex)}",
                "parsed_json": None,
                "is_json_valid": False,
                "latency_ms": round(latency_ms, 2),
            }

    async def _stream_single_model(
        self,
        client: httpx.AsyncClient,
        model: ModelSelection,
        request: CompareRequest,
        queue: asyncio.Queue[Dict[str, Any]],
    ) -> None:
        payload: Dict[str, Any] = {
            "model": model.id,
            "messages": [
                {
                    "role": "system",
                    "content": self._build_system_prompt(request.output_mode, request.role_override),
                },
                {
                    "role": "user",
                    "content": self._build_user_content(request),
                },
            ],
            "stream": True,
            "options": {"temperature": 0.3},
        }

        if request.output_mode == "json":
            payload["format"] = "json"

        await queue.put(
            {
                "type": "model_started",
                "model_id": model.id,
            }
        )

        started = time.perf_counter()
        chunks: List[str] = []

        try:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=300.0) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    piece = event.get("message", {}).get("content", "")
                    if piece:
                        chunks.append(piece)
                        await queue.put(
                            {
                                "type": "model_chunk",
                                "model_id": model.id,
                                "chunk": piece,
                            }
                        )

            raw = "".join(chunks)
            parsed_json = None
            is_json_valid = False
            if request.output_mode == "json":
                try:
                    parsed_json = json.loads(raw)
                    is_json_valid = isinstance(parsed_json, dict)
                except json.JSONDecodeError:
                    parsed_json = None

            await queue.put(
                {
                    "type": "model_completed",
                    "model": model,
                    "raw_response": raw,
                    "parsed_json": parsed_json,
                    "is_json_valid": is_json_valid,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        except Exception as ex:  # pylint: disable=broad-except
            await queue.put(
                {
                    "type": "model_completed",
                    "model": model,
                    "raw_response": f"Request failed: {repr(ex)}",
                    "parsed_json": None,
                    "is_json_valid": False,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )

    async def run_comparison(self, request: CompareRequest) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            tasks = [self._call_single(client, model, request) for model in request.models]
            return await asyncio.gather(*tasks)

    async def stream_comparison(self, request: CompareRequest) -> AsyncGenerator[Dict[str, Any], None]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        completed_models = 0

        async with httpx.AsyncClient() as client:
            tasks = [
                asyncio.create_task(self._stream_single_model(client, model, request, queue))
                for model in request.models
            ]

            try:
                while completed_models < len(request.models):
                    event = await queue.get()
                    if event.get("type") == "model_completed":
                        completed_models += 1
                    yield event
            finally:
                await asyncio.gather(*tasks, return_exceptions=True)
