import json
import re

from fastapi import APIRouter, HTTPException
from groq import APIError, Groq
from pydantic import ValidationError

from src.app.core.config import get_settings
from src.app.schemas.voice import (
    InstructionPayload,
    InstructionRequest,
    TaskCreate,
    TaskReplace,
    TaskUpdate,
)

router = APIRouter(tags=["instruction"])

SYSTEM_PROMPT = """
You are an API instruction router for a task management application.

Interpret the user's command in Spanish or English.

Return ONLY a valid JSON object with exactly these properties:
- endpoint: string
- method: string
- params: object

Allowed actions:

CREATE:
{"endpoint":"/tasks","method":"POST","params":{"title":"task title"}}

LIST:
{"endpoint":"/tasks","method":"GET","params":{}}

REPLACE:
{"endpoint":"/tasks/1","method":"PUT","params":{"title":"new title","done":false}}

UPDATE:
{"endpoint":"/tasks/1","method":"PATCH","params":{"done":true}}

DELETE:
{"endpoint":"/tasks/1","method":"DELETE","params":{}}

Rules:
- Use only the endpoints and HTTP methods above.
- Extract the actual task title from the user's words.
- Never use task_name, task, description or text instead of title.
- For updates and deletions, require a numeric task ID.
- Never invent a task ID.
- If a task ID is required but missing, return
  {"endpoint":"/tasks","method":"GET","params":{}}.
- Do not add explanations or markdown.
- Return only JSON.
"""


def validate_instruction(data: object) -> InstructionPayload:
    if not isinstance(data, dict):
        raise ValueError("Instruction must be a JSON object")

    if set(data) != {"endpoint", "method", "params"}:
        raise ValueError("Invalid instruction fields")

    instruction = InstructionPayload.model_validate(data)
    endpoint = instruction.endpoint
    method = instruction.method
    params = instruction.params

    if endpoint == "/tasks":
        if method == "GET" and not params:
            return instruction

        if method == "POST":
            if set(params) != {"title"}:
                raise ValueError("Invalid create parameters")
            TaskCreate.model_validate(params)
            return instruction

    match = re.fullmatch(r"/tasks/([1-9][0-9]*)", endpoint)

    if match:
        if method == "DELETE" and not params:
            return instruction

        if method == "PUT":
            if set(params) != {"title", "done"}:
                raise ValueError("Invalid replace parameters")
            TaskReplace.model_validate(params)
            return instruction

        if method == "PATCH":
            if not params or not set(params) <= {"title", "done"}:
                raise ValueError("Invalid update parameters")
            update = TaskUpdate.model_validate(params)
            if any(value is None for value in update.model_dump(exclude_unset=True).values()):
                raise ValueError("Update parameters cannot be null")
            return instruction

    raise ValueError("Unsupported task instruction")


@router.post("/instruction", response_model=InstructionPayload)
def route_instruction(
    payload: InstructionRequest,
) -> InstructionPayload:
    settings = get_settings()

    try:
        client = Groq(
            api_key=settings.groq_api_key,
            timeout=settings.request_timeout_seconds,
        )

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload.transcription},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_completion_tokens=512,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Empty model response")

        return validate_instruction(json.loads(content))

    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail="Groq service request failed",
        ) from exc

    except (ValueError, TypeError, KeyError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Invalid instruction returned by language model",
        ) from exc
