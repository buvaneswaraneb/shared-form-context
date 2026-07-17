import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import desc, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import engine, get_session
from .models import Base, Prompt
from .normalization import normalize_prompt, prompt_id
from .processing import process_pending, scheduler_loop
from .schemas import CronResponse, PromptResponse, SendRequest, SendResponse

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    stop = asyncio.Event()
    task = None
    settings = get_settings()
    if settings.scheduler_enabled:
        task = asyncio.create_task(scheduler_loop(stop))
    yield
    stop.set()
    if task:
        await task
    await engine.dispose()


app = FastAPI(title="Shared Prompt Context Service", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "validation_error", "details": exc.errors()})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.post("/send", response_model=SendResponse, status_code=status.HTTP_201_CREATED)
async def send(request: SendRequest, session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    normalized = normalize_prompt(request.prompt)
    if not normalized:
        raise HTTPException(422, detail={"error": "prompt_empty", "message": "Prompt cannot be empty."})
    if len(normalized) > settings.max_prompt_length:
        raise HTTPException(413, detail={"error": "prompt_too_long", "max_length": settings.max_prompt_length})
    identifier = prompt_id(normalized)
    existing = await session.get(Prompt, identifier)
    if existing:
        logger.info("duplicate_prompt_detected", extra={"prompt_id": identifier})
        return SendResponse(id=identifier, exists=True)
    try:
        await session.execute(insert(Prompt).values(
            id=identifier,
            original_prompt=request.prompt,
            normalized_prompt=normalized,
            processed=False,
            processing_attempts=0,
        ))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("duplicate_prompt_detected", extra={"prompt_id": identifier})
        return SendResponse(id=identifier, exists=True)
    logger.info("new_prompt_received", extra={"prompt_id": identifier})
    return SendResponse(id=identifier, exists=False)


def to_response(prompt: Prompt) -> PromptResponse:
    return PromptResponse(id=prompt.id, prompt=prompt.original_prompt, processed=prompt.processed, processed_at=prompt.processed_at)


@app.get("/query", response_model=list[PromptResponse])
async def query(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(select(Prompt).order_by(desc(Prompt.created_at), desc(Prompt.id)).offset(offset).limit(limit))).scalars().all()
    return [to_response(row) for row in rows]


@app.get("/today", response_model=list[PromptResponse])
async def today(session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    rows = (await session.execute(select(Prompt).where(Prompt.created_at >= start).order_by(desc(Prompt.created_at), desc(Prompt.id)))).scalars().all()
    return [to_response(row) for row in rows]


@app.api_route("/internal/process", methods=["GET", "POST"], response_model=CronResponse, include_in_schema=False)
async def process_cron(
    x_cron_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    secret = get_settings().cron_secret
    bearer = authorization.removeprefix("Bearer ") if authorization else None
    if secret and x_cron_secret != secret and bearer != secret:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
    processed, failed = await process_pending()
    return CronResponse(processed=processed, failed=failed)


@app.get("/health")
async def health():
    return {"status": "ok"}
