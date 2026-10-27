# Voice Command API — Implementation Report

## Project

4Geeks Academy — Voice Command API

Development branch: `feature/voice-command-api`

## Implemented functionality

- In-memory task storage with incremental IDs.
- CRUD endpoints: GET, POST, PUT, PATCH, DELETE.
- Natural-language instruction routing using Groq.
- Strict validation of generated API instructions.
- Audio transcription using Groq Whisper.
- Task execution through POST /transcribe.
- Manual text input supported.
- Original frontend preserved without modification.

## AI models

The implementation was tested with:

- Chat: openai/gpt-oss-20b
- Transcription: whisper-large-v3-turbo

Models and API credentials are configured through the local .env file.

API credentials must never be committed.

## Architecture

Browser
  -> POST /transcribe
  -> Groq Whisper (audio only)
  -> Groq instruction routing
  -> Instruction validation
  -> In-memory task CRUD
  -> Structured API response

POST /instruction returns routing information without executing tasks.

POST /transcribe executes validated task instructions.

## Local execution

Backend:

    uv sync --python 3.12 --locked
    uv run uvicorn src.main:app --reload

Frontend:

    cd frontend
    npm ci
    npm run dev

API documentation:

http://127.0.0.1:8000/docs

## Verified behavior

- Create tasks.
- List tasks.
- Replace tasks using PUT.
- Update task completion using PATCH.
- Delete tasks.
- Reject invalid task payloads.
- Reject unsupported instruction routes.
- Interpret Spanish instructions through Groq.
- Transcribe real voice commands through the browser.
- Return transcription, instruction, and execution result.

Task data is stored in memory and resets when the backend process restarts.

## Implementation commits

- 111d831 — In-memory task CRUD.
- 6693cd0 — Groq instruction routing.
- 42f7de7 — Voice transcription and task execution.

## Delivery

The feature branch is intended for review through a Pull Request.

No automatic merge into main is required.
