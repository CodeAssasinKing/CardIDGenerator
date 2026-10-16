import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import List, Union

import qrcode

from config.tasiq import broker, get_kv
from schemas.data_schema import DataSchema
from utils.templates import render_template_badge, build_qr_payload
from utils.pdf import save_cards_to_pdf


@broker.task
async def create_a_simple_cards(
    data: List[Union[DataSchema, dict]],
    project_uuid: str,
    template_id: str = "classic_blue",
    event_date: str = "15.11.2026",
    category_title: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    bg_color: str | None = None,
    accent_color: str | None = None,
    accent_height: int = 6,
    accent_visible: bool = True,
    qr_fields: List[str] | None = None,
    is_pdf: bool = False,
) -> str:
    """
    Генерирует карточки и QR-коды со шрифтом Montserrat по выбранному шаблону и с указанной датой, заголовком, телефоном, сайтом, цветом фона, верхней полосой и полями QR.
    Если is_pdf=True, дополнительно генерирует PDF формата А4 для печати и упаковывает в ZIP.
    """
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
        "template": template_id,
        "event_date": event_date,
        "category_title": category_title,
        "phone": phone,
        "website": website,
        "bg_color": bg_color,
        "accent_color": accent_color,
        "accent_height": accent_height,
        "accent_visible": accent_visible,
        "qr_fields": qr_fields,
        "is_pdf": is_pdf,
    }
    await kv.put(project_uuid, json.dumps(initial_event).encode("utf-8"))

    rendered_cards = []

    try:
        # 2. Генерация карточек по шаблону
        for i, item in enumerate(data, start=1):
            name = item.name if hasattr(item, "name") else item.get("name", "")
            surname = item.surname if hasattr(item, "surname") else item.get("surname", "")
            item_id = item.id if hasattr(item, "id") else item.get("id", i)
            item_phone = item.phone if hasattr(item, "phone") else item.get("phone")
            item_web = item.website if hasattr(item, "website") else item.get("website")
            item_fn = item.full_name if hasattr(item, "full_name") else item.get("full_name")

            final_phone = (item_phone or phone or "").strip() or None
            final_web = (item_web or website or "").strip() or None

            # Отрисовываем бейдж по выбранному шаблону, дате, заголовку и контактам
            card = render_template_badge(
                name=str(name),
                surname=str(surname),
                item_id=int(item_id),
                template_id=template_id,
                event_date=event_date,
                category_title=category_title,
                phone=final_phone,
                website=final_web,
                full_name=item_fn,
                bg_color=bg_color,
                accent_color=accent_color,
                accent_height=accent_height,
                accent_visible=accent_visible,
                qr_fields=qr_fields,
            )
            rendered_cards.append(card)

            user_dir = project_dir / f"user_{item_id}"
            user_dir.mkdir(parents=True, exist_ok=True)

            # Безопасное имя файла
            display_title = item_fn or name or f"card_{item_id}"
            safe_name = "".join(c for c in str(display_title) if c.isalnum() or c in (" ", "_", "-")).strip() or f"card_{item_id}"
            card.save(user_dir / f"{safe_name}.png")

            # Отдельный QR-код с настраиваемыми полями
            qr_payload = build_qr_payload(
                name=str(name),
                surname=str(surname),
                item_id=item_id,
                event_date=event_date,
                phone=final_phone,
                website=final_web,
                full_name=item_fn,
                qr_fields=qr_fields,
            )
            qr_code_img = qrcode.make(qr_payload)
            qr_code_img.save(user_dir / "qrcode.png")

            # Обновляем статус прогресса в NATS KV
            percent = int((i / total) * 100)
            progress_event = {
                "status": "PROCESSING",
                "current": i,
                "total": total,
                "percent": percent,
                "template": template_id,
                "event_date": event_date,
                "category_title": category_title,
                "is_pdf": is_pdf,
            }
            await kv.put(project_uuid, json.dumps(progress_event).encode("utf-8"))

        # 3. Если запрошен PDF — генерируем печатные листы А4 и постраничный PDF
        if is_pdf and rendered_cards:
            save_cards_to_pdf(
                cards=rendered_cards,
                a4_output_path=project_dir / "badges_print_a4.pdf",
                single_output_path=project_dir / "badges_single.pdf",
            )

        # 4. Упаковываем ВСЕ файлы (включая PDF при наличии) в zip на диске
        archive_path = project_dir / "cards.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in project_dir.rglob("*"):
                if file_path.is_file() and file_path.name != "cards.zip":
                    archive_name = file_path.relative_to(project_dir).as_posix()
                    z_info = zipfile.ZipInfo.from_file(file_path, arcname=archive_name)
                    # Флаг 0x800 включает корректную UTF-8 кодировку для кириллицы в Windows Explorer / 7-Zip
                    z_info.flag_bits |= 0x800
                    with open(file_path, "rb") as f:
                        zip_file.writestr(z_info, f.read())

        # 5. Очистка: удаляем временные папки и PDF на диске, оставляя только готовый cards.zip
        for item_path in project_dir.iterdir():
            if item_path.name != "cards.zip":
                if item_path.is_dir():
                    shutil.rmtree(item_path, ignore_errors=True)
                else:
                    item_path.unlink(missing_ok=True)

        # 6. Записываем статус завершения в KV
        done_event = {
            "status": "COMPLETED",
            "current": total,
            "total": total,
            "percent": 100,
            "template": template_id,
            "event_date": event_date,
            "category_title": category_title,
            "is_pdf": is_pdf,
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
def cleanup_old_batches_task(max_age_seconds: int = 3600) -> int:
    """
    Почасовая фоновая очистка:
    - Удаляет папки проектов, если они уже были скачаны пользователем (.downloaded)
    - Удаляет невостребованные проекты старше max_age_seconds (по умолчанию 1 час / 3600 сек)
    - Полностью защищает системные папки ('custom', 'previews') и статические файлы.
    """
    now = time.time()
    base_dir = Path("./templates")
    deleted_count = 0

    if not base_dir.exists():
        return 0

    PROTECTED_DIRS = {"custom", "previews"}

    for item in base_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name in PROTECTED_DIRS:
            continue

        try:
            downloaded_marker = item / ".downloaded"
            is_downloaded = downloaded_marker.exists()
            is_expired = (now - item.stat().st_mtime) > max_age_seconds

            if is_downloaded or is_expired:
                shutil.rmtree(item, ignore_errors=True)
                deleted_count += 1
        except Exception:
            pass

    return deleted_count