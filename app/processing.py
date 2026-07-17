import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import Prompt

logger = logging.getLogger(__name__)


async def process_pending(limit: int | None = None) -> tuple[int, int]:
    settings = get_settings()
    limit = limit or settings.scheduler_batch_size
    processed = failed = 0
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        rows = (await session.execute(
            select(Prompt)
            .where(Prompt.processed.is_(False))
            .where(Prompt.processing_attempts < settings.scheduler_max_retries)
            .where((Prompt.next_attempt_at.is_(None)) | (Prompt.next_attempt_at <= now))
            .order_by(Prompt.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )).scalars().all()
        for prompt in rows:
            started = asyncio.get_running_loop().time()
            try:
                # Processing is deliberately metadata-only for now. This is the
                # extension point for future stages such as embeddings.
                prompt.processed = True
                prompt.processed_at = datetime.now(timezone.utc)
                prompt.last_error = None
                prompt.next_attempt_at = None
                processed += 1
                logger.info("prompt_processed", extra={"prompt_id": prompt.id})
            except Exception as exc:  # pragma: no cover - defensive transaction path
                failed += 1
                prompt.processing_attempts += 1
                prompt.last_error = str(exc)[:2_000]
                prompt.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=min(300, 2 ** prompt.processing_attempts)
                )
                logger.exception("prompt_processing_failed", extra={"prompt_id": prompt.id})
            finally:
                logger.info("prompt_processing_duration", extra={
                    "prompt_id": prompt.id,
                    "duration_ms": round((asyncio.get_running_loop().time() - started) * 1000, 2),
                })
        await session.commit()
    return processed, failed


async def scheduler_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    while not stop.is_set():
        try:
            logger.info("scheduler_run")
            await process_pending()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduler_run_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_interval_seconds)
        except asyncio.TimeoutError:
            pass
