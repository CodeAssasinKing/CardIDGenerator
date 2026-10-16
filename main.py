import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from routes.route import app as main_routes
from utils.create_template import create_a_template
from config.tasiq import broker
from tasks.index_card import cleanup_old_batches_task


async def periodic_cleanup():
    """Фоновая очистка старых архивов старше 2 часов (каждые 30 минут)."""
    while True:
        try:
            await asyncio.sleep(1800)
            await cleanup_old_batches_task.kiq(max_age_seconds=7200)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_a_template()

    cleanup_bg_task = None
    if not broker.is_worker_process:
        await broker.startup()
        # Запускаем фоновую периодическую очистку и чистим при старте
        cleanup_bg_task = asyncio.create_task(periodic_cleanup())
        await cleanup_old_batches_task.kiq(max_age_seconds=7200)

    yield

    if cleanup_bg_task:
        cleanup_bg_task.cancel()

    if not broker.is_worker_process:
        await broker.shutdown()


app = FastAPI(
    title="Qr code maker",
    description="Card generation with Taskiq background workers and real-time SSE progress",
    lifespan=lifespan,
)


from fastapi.responses import FileResponse


@app.get("/", summary="Главная страница (веб-интерфейс)")
async def root():
    return FileResponse("static/index.html")


app.include_router(router=main_routes)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)