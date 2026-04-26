import json
from pathlib import Path
from typing import List

from app.schemas.contracts import ModelSelection


DEFAULT_MODELS = [
    ModelSelection(id="openai/gpt-4o-mini", name="GPT-4o Mini", symbol="O", provider="OpenAI"),
    ModelSelection(id="meta-llama/llama-3.1-8b-instruct", name="Llama 3.1 8B", symbol="M", provider="Meta"),
    ModelSelection(id="google/gemini-flash-1.5", name="Gemini Flash 1.5", symbol="G", provider="Google"),
    ModelSelection(id="mistralai/mistral-7b-instruct", name="Mistral 7B", symbol="Mi", provider="Mistral"),
    ModelSelection(id="qwen/qwen-2.5-7b-instruct", name="Qwen 2.5 7B", symbol="Q", provider="Qwen"),
]

MODEL_CATALOG_PATH = Path(__file__).resolve().parents[2] / "model_catalog.json"


def get_available_models() -> List[ModelSelection]:
    if MODEL_CATALOG_PATH.exists():
        try:
            with MODEL_CATALOG_PATH.open("r", encoding="utf-8") as file:
                raw_models = json.load(file)
            return [ModelSelection(**model) for model in raw_models]
        except Exception:  # pylint: disable=broad-except
            return DEFAULT_MODELS
    return DEFAULT_MODELS
