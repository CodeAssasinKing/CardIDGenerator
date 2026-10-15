import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import List, Union

import qrcode

from config.tasiq import broker, get_kv
from schemas.data_schema import DataSchema
from utils.fonts import render_styled_card


@broker.task
async def create_a_simple_cards(data: List[Union[DataSchema, dict]], project_uuid: str) -> str:
    """Генерирует карточки и QR-коды со шрифтом Montserrat, сохраняет статус в NATS KV и собирает zip."""
    project_dir = Path(f"./templates/{project_uuid}")
    project_dir.mkdir(parents=True, exist_ok=True)

    kv = await get_kv()
    total = len(data)

    # 1. Записываем начальный статус в KV
    initial_event = {
        "status": "PROCESSING",
        "current": 0,
        "total": total,
        "percent": 0,
    }
    await kv.put(project_uuid, json.dumps(initial_event).encode("utf-8"))

    try:
        # 2. Генерация карточек с типографикой Montserrat
        for i, item in enumerate(data, start=1):
            name = item.name if hasattr(item, "name") else item["name"]
            surname = item.surname if hasattr(item, "surname") else item["surname"]
            item_id = item.id if hasattr(item, "id") else item["id"]

            user_dir = project_dir / str(item_id)
            user_dir.mkdir(parents=True, exist_ok=True)

            # Отрисовываем бейдж с профессиональной типографикой Montserrat и встроенным QR
            card = render_styled_card(name=str(name), surname=str(surname), item_id=int(item_id))

            # Безопасное имя файла
            safe_name = "".join(c for c in str(name) if c.isalnum() or c in (" ", "_", "-")).strip() or f"card_{item_id}"
            card.save(user_dir / f"{safe_name}.png")

            # Сохраняем также отдельный QR-код на случай, если он нужен отдельно
            qr_code_img = qrcode.make(f"{name}:{surname}:{item_id}")
            qr_code_img.save(user_dir / "qrcode.png")

            # Обновляем статус прогресса в NATS KV
            percent = int((i / total) * 100)
            progress_event = {
                "status": "PROCESSING",
                "current": i,
                "total": total,
                "percent": percent,
            }
            await kv.put(project_uuid, json.dumps(progress_event).encode("utf-8"))

        # 3. Упаковываем ВСЮ папку этого UUID в zip на диске
        archive_path = project_dir / "cards.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in project_dir.rglob("*"):
                if file_path.is_file() and file_path.name != "cards.zip":
                    archive_name = file_path.relative_to(project_dir).as_posix()
                    zip_file.write(file_path, arcname=archive_name)

        # 4. Немедленная очистка: удаляем сотни временных PNG файлов, оставляя только готовый zip
        for item_path in project_dir.iterdir():
            if item_path.is_dir():
                shutil.rmtree(item_path, ignore_errors=True)

        # 5. Записываем статус завершения в KV
        done_event = {
            "status": "COMPLETED",
            "current": total,
            "total": total,
            "percent": 100,
            "download_url": f"/api/download/{project_uuid}",
        }
        await kv.put(project_uuid, json.dumps(done_event).encode("utf-8"))

        return str(archive_path)

    except Exception as exc:
        error_event = {
            "status": "FAILED",
            "error": str(exc),
            "project_uuid": project_uuid,
        }
        await kv.put(project_uuid, json.dumps(error_event).encode("utf-8"))
        raise exc


@broker.task
def cleanup_old_batches_task(max_age_seconds: int = 7200) -> int:
    """Удаляет папки проектов в ./templates старше max_age_seconds (по умолчанию 2 часа)."""
    now = time.time()
    base_dir = Path("./templates")
    deleted_count = 0

    if not base_dir.exists():
        return 0

    for item in base_dir.iterdir():
        if item.is_dir():
            try:
                if now - item.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
                    deleted_count += 1
            except Exception:
                pass

    return deleted_count