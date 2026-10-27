import asyncio
import io

from fastapi import APIRouter, HTTPException, Request, status
from groq import APIError, Groq
from pydantic import ValidationError

from src.app.api.routes import tasks
from src.app.api.routes.instruction import route_instruction, validate_instruction
from src.app.core.config import get_settings
from src.app.schemas.voice import (
    InstructionPayload,
    InstructionRequest,
    TaskCreate,
    TaskReplace,
    TaskUpdate,
    TranscribeFlowResponse,
)
from src.app.utils.language import normalize_transcription_language

router = APIRouter(tags=["transcribe"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.get("/")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def execute_instruction(instruction: InstructionPayload):
    instruction = validate_instruction(instruction.model_dump())
    endpoint = instruction.endpoint
    method = instruction.method
    params = instruction.params

    if endpoint == "/tasks":
        if method == "GET":
            return [task.model_dump() for task in tasks.get_tasks()]

        if method == "POST":
            payload = TaskCreate.model_validate(params)
            return tasks.create_task(payload).model_dump()

    task_id = int(endpoint.rsplit("/", 1)[-1])

    if method == "PUT":
        payload = TaskReplace.model_validate(params)
        return tasks.replace_task(task_id, payload).model_dump()

    if method == "PATCH":
        payload = TaskUpdate.model_validate(params)
        return tasks.update_task(task_id, payload).model_dump()

    if method == "DELETE":
        return tasks.delete_task(task_id)

    raise HTTPException(
        status_code=400,
        detail="Unsupported task operation",
    )


def transcribe_audio(
    audio: bytes,
    filename: str,
    language: str | None,
) -> str:
    settings = get_settings()

    try:
        client = Groq(
            api_key=settings.groq_api_key,
            timeout=settings.request_timeout_seconds,
        )

        result = client.audio.transcriptions.create(
            file=(filename, io.BytesIO(audio)),
            model=settings.groq_transcription_model,
            language=language,
            response_format="json",
        )

        transcription = result.text.strip()

        if not transcription:
            raise HTTPException(
                status_code=422,
                detail="Audio transcription is empty",
            )

        return transcription

    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail="Audio transcription service failed",
        ) from exc


@router.post(
    "/transcribe",
    response_model=TranscribeFlowResponse,
)
async def transcribe_and_run_flow(
    request: Request,
) -> TranscribeFlowResponse:

    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        try:
            payload = InstructionRequest.model_validate(
                await request.json()
            )
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid transcription payload",
            ) from exc

        transcription = payload.transcription.strip()

    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")

        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=422,
                detail="Audio file is required",
            )

        language = normalize_transcription_language(
            form.get("language")
        )

        audio = await upload.read(MAX_AUDIO_BYTES + 1)

        if not audio:
            raise HTTPException(
                status_code=422,
                detail="Audio file is empty",
            )

        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Audio file is too large",
            )

        filename = getattr(upload, "filename", None) or "command.webm"

        transcription = await asyncio.to_thread(
            transcribe_audio,
            audio,
            filename,
            language,
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use JSON or multipart/form-data",
        )

    if not transcription:
        raise HTTPException(
            status_code=422,
            detail="Transcription cannot be empty",
        )

    instruction = await asyncio.to_thread(
        route_instruction,
        InstructionRequest(transcription=transcription),
    )

    try:
        result = execute_instruction(instruction)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid task parameters",
        ) from exc

    return TranscribeFlowResponse(
        transcription=transcription,
        instruction=instruction,
        result=result,
    )
