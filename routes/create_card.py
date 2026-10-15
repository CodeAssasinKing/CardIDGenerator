import asyncio
import json
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
import nats.errors

from config.tasiq import broker, get_kv
from schemas.data_schema import DataSchema
from tasks.index_card import create_a_simple_cards

router = APIRouter()

MAX_BATCH_SIZE = 500


@router.post("/create_card", summary="Create cards in background", status_code=status.HTTP_202_ACCEPTED)
async def create_card(data: List[DataSchema]):
    """
    Запускает фоновую генерацию карточек.
    Ограничение пачки: от 1 до 500 элементов.
    """
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Список данных пуст.",
        )

    if len(data) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Превышен лимит пачки: максимум {MAX_BATCH_SIZE} карточек за один запрос.",
        )

    project_uuid = str(uuid.uuid4())
    payload = [item.model_dump() for item in data]

    # 1. Сразу записываем начальный статус в KV, чтобы стрим не был пустым при подключении
    kv = await get_kv()
    initial_event = {
        "status": "QUEUED",
        "current": 0,
        "total": len(data),
        "percent": 0,
    }
    await kv.put(project_uuid, json.dumps(initial_event).encode("utf-8"))

    # 2. Отправляем задачу в постоянную очередь JetStream
    await create_a_simple_cards.kiq(data=payload, project_uuid=project_uuid)

    return {
        "status": "QUEUED",
        "project_uuid": project_uuid,
        "total_items": len(data),
        "stream_url": f"/api/stream/{project_uuid}",
        "download_url": f"/api/download/{project_uuid}",
    }


@router.get("/stream/{project_uuid}", summary="Stream progress via Server-Sent Events (SSE)")
async def stream_progress(project_uuid: str):
    """
    Стримит прогресс генерации в реальном времени через NATS KeyValue Watcher.
    """
    archive_path = Path(f"./templates/{project_uuid}/cards.zip")

    # Если задача уже завершена к моменту запроса
    if archive_path.exists():
        async def instant_done():
            yield f'data: {{"status": "COMPLETED", "percent": 100, "download_url": "/api/download/{project_uuid}"}}\n\n'
        return StreamingResponse(instant_done(), media_type="text/event-stream")

    kv = await get_kv()

    async def event_generator():
        watcher = await kv.watch(project_uuid)
        try:
            while True:
                try:
                    entry = await watcher.updates(timeout=60.0)
                except (asyncio.TimeoutError, nats.errors.TimeoutError):
                    yield 'data: {"status": "TIMEOUT", "error": "Воркер не ответил вовремя"}\n\n'
                    break

                if entry is None or entry.value is None:
                    continue

                raw_data = entry.value.decode("utf-8")
                yield f"data: {raw_data}\n\n"

                parsed = json.loads(raw_data)
                # Если задача завершена или упала с ошибкой — выходим из стрима
                if parsed.get("status") in ("COMPLETED", "FAILED"):
                    break
        finally:
            await watcher.stop()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/download/{project_uuid}", summary="Download ready zip archive")
async def download_cards(project_uuid: str):
    """Скачивание готового zip-архива."""
    archive_path = Path(f"./templates/{project_uuid}/cards.zip")
    if not archive_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Архив еще генерируется воркером или не найден. Проверьте статус в /api/stream/{project_uuid}",
        )

    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=f"cards_{project_uuid}.zip",
    )
