import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import ExperimentRun, ModelOutput, OutputEvaluation
from app.schemas.contracts import (
    CompareRequest,
    CompareResponse,
    EvaluationRequest,
    EvaluationResponse,
    GlobalRunItem,
    ModelOutputResponse,
    ModelsResponse,
)
from app.services.model_registry import get_available_models
from app.services.ollama_client import OllamaClient


router = APIRouter()
ollama = OllamaClient()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.get("/models", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    return ModelsResponse(models=get_available_models())


@router.post("/compare", response_model=CompareResponse)
async def compare_models(request: CompareRequest, db: Session = Depends(get_db)) -> CompareResponse:
    run = ExperimentRun(
        prompt_type=request.prompt_type,
        prompt_text=request.prompt_text,
        input_text=request.input_text,
        output_mode=request.output_mode,
    )
    db.add(run)
    db.flush()

    results = await ollama.run_comparison(request)

    outputs_response: List[ModelOutputResponse] = []
    for result in results:
        model = result["model"]
        parsed_json_str = json.dumps(result["parsed_json"]) if result["parsed_json"] is not None else None

        output = ModelOutput(
            run_id=run.id,
            model_name=model.name,
            model_symbol=model.symbol,
            provider_name=model.provider,
            raw_response=result["raw_response"],
            parsed_json=parsed_json_str,
            is_json_valid=result["is_json_valid"],
            latency_ms=result["latency_ms"],
        )
        db.add(output)
        db.flush()

        outputs_response.append(
            ModelOutputResponse(
                output_id=output.id,
                model_name=output.model_name,
                model_symbol=output.model_symbol,
                provider_name=output.provider_name,
                raw_response=output.raw_response,
                parsed_json=result["parsed_json"],
                is_json_valid=output.is_json_valid,
                latency_ms=output.latency_ms,
            )
        )

    db.commit()
    db.refresh(run)

    return CompareResponse(run_id=run.id, created_at=run.created_at, outputs=outputs_response)


@router.post("/compare/stream")
async def compare_models_stream(request: CompareRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    run = ExperimentRun(
        prompt_type=request.prompt_type,
        prompt_text=request.prompt_text,
        input_text=request.input_text,
        output_mode=request.output_mode,
    )
    db.add(run)
    db.flush()

    async def event_generator():
        yield _sse({"type": "run_started", "run_id": run.id, "created_at": run.created_at.isoformat()})

        async for event in ollama.stream_comparison(request):
            event_type = event.get("type")

            if event_type == "model_started":
                yield _sse(event)
                continue

            if event_type == "model_chunk":
                yield _sse(event)
                continue

            if event_type == "model_completed":
                model = event["model"]
                parsed_json_str = json.dumps(event["parsed_json"]) if event["parsed_json"] is not None else None

                output = ModelOutput(
                    run_id=run.id,
                    model_name=model.name,
                    model_symbol=model.symbol,
                    provider_name=model.provider,
                    raw_response=event["raw_response"],
                    parsed_json=parsed_json_str,
                    is_json_valid=event["is_json_valid"],
                    latency_ms=event["latency_ms"],
                )
                db.add(output)
                db.commit()
                db.refresh(output)

                yield _sse(
                    {
                        "type": "model_completed",
                        "model_id": model.id,
                        "output": {
                            "output_id": output.id,
                            "model_name": output.model_name,
                            "model_symbol": output.model_symbol,
                            "provider_name": output.provider_name,
                            "raw_response": output.raw_response,
                            "parsed_json": event["parsed_json"],
                            "is_json_valid": output.is_json_valid,
                            "latency_ms": output.latency_ms,
                        },
                    }
                )
                continue

            yield _sse({"type": "error", "message": "Unexpected stream event"})

        yield _sse({"type": "done", "run_id": run.id})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/runs", response_model=List[GlobalRunItem])
def list_runs(
    saved_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> List[GlobalRunItem]:
    query = (
        db.query(ExperimentRun, ModelOutput, OutputEvaluation)
        .join(ModelOutput, ModelOutput.run_id == ExperimentRun.id)
        .outerjoin(OutputEvaluation, OutputEvaluation.output_id == ModelOutput.id)
        .order_by(ExperimentRun.created_at.desc(), ModelOutput.id.desc())
    )

    if saved_only:
        query = query.filter(OutputEvaluation.id.isnot(None))

    rows = query.limit(500).all()

    return [
        GlobalRunItem(
            run_id=run.id,
            created_at=run.created_at,
            prompt_type=run.prompt_type,
            output_mode=run.output_mode,
            model_name=output.model_name,
            model_symbol=output.model_symbol,
            provider_name=output.provider_name,
            input_text=run.input_text,
            prompt_text=run.prompt_text,
            raw_response=output.raw_response,
            is_json_valid=output.is_json_valid,
            accuracy=evaluation.accuracy if evaluation else None,
            clarity=evaluation.clarity if evaluation else None,
            relevance=evaluation.relevance if evaluation else None,
            failure_tags=evaluation.failure_tags.split(",") if evaluation and evaluation.failure_tags else [],
            notes=evaluation.notes if evaluation else None,
            is_saved=evaluation is not None,
        )
        for run, output, evaluation in rows
    ]


@router.post("/evaluate", response_model=EvaluationResponse)
def submit_evaluation(request: EvaluationRequest, db: Session = Depends(get_db)) -> EvaluationResponse:
    output = db.query(ModelOutput).filter(ModelOutput.id == request.output_id).first()
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    existing = db.query(OutputEvaluation).filter(OutputEvaluation.output_id == request.output_id).first()
    tags = ",".join(request.failure_tags) if request.failure_tags else ""

    if existing:
        existing.accuracy = request.accuracy
        existing.clarity = request.clarity
        existing.relevance = request.relevance
        existing.failure_tags = tags
        existing.notes = request.notes
    else:
        evaluation = OutputEvaluation(
            output_id=request.output_id,
            accuracy=request.accuracy,
            clarity=request.clarity,
            relevance=request.relevance,
            failure_tags=tags,
            notes=request.notes,
        )
        db.add(evaluation)

    db.commit()
    return EvaluationResponse(message="Evaluation saved")
