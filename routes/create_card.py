import asyncio
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import nats.errors

from config.tasiq import broker, get_kv
from schemas.data_schema import DataSchema
from tasks.index_card import create_a_simple_cards
from utils.templates import (
    get_templates_list,
    render_template_badge,
    save_custom_template,
    delete_custom_template,
    CUSTOM_DIR,
)

router = APIRouter()

MAX_BATCH_SIZE = 500


class CustomTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Уникальное название шаблона")
    description: str = Field(default="", max_length=150, description="Краткое описание")
    temp_bg_id: str | None = Field(default=None, description="ID предварительно загруженного фона")
    bg_color: str = Field(default="#FFFFFF", description="Цвет фона, если нет изображения")
    layout: Dict[str, Any] = Field(..., description="Координаты и стили элементов бейджа")


@router.get("/templates", summary="Список доступных шаблонов оформления")
async def list_templates():
    """
    Возвращает список из 4 базовых шаблонов + всех сохраненных кастомных шаблонов
    со ссылками на готовые фото-превью для фронтенда.
    """
    return get_templates_list()


@router.post("/templates/upload-background", summary="Загрузить фон для конструктора шаблона")
async def upload_background(background: UploadFile = File(...)):
    """
    Загружает фоновое изображение пользователя и выполняет автоматическое
    умное кадрирование (crop/fit к пропорциям 3:2, 450x300).
    """
    if not background.content_type or not background.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть изображением (PNG, JPG, WebP)",
        )

    temp_id = f"temp_{uuid.uuid4().hex[:10]}"
    temp_path = CUSTOM_DIR / f"{temp_id}.png"

    try:
        from PIL import Image, ImageOps
        img = Image.open(background.file).convert("RGB")
        # Умная подгонка под пропорции карточки (450x300)
        fitted = ImageOps.fit(img, (450, 300), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(temp_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось обработать изображение: {e}",
        )

    return {
        "temp_bg_id": temp_id,
        "preview_url": f"/api/templates/temp-bg/{temp_id}",
    }


@router.get("/templates/temp-bg/{temp_bg_id}", summary="Превью временного фона для конструктора")
async def get_temp_background(temp_bg_id: str):
    """Отдает загруженный временный фон для отображения на интерактивном холсте."""
    temp_path = CUSTOM_DIR / f"{temp_bg_id}.png"
    if not temp_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Временный фон не найден",
        )
    return FileResponse(temp_path, media_type="image/png")


@router.post("/templates/custom", summary="Сохранить кастомный шаблон из конструктора")
async def create_custom_template(payload: CustomTemplateCreate):
    """
    Сохраняет созданный в конструкторе шаблон с проверкой уникальности имени.
    """
    try:
        tpl_data = save_custom_template(
            name=payload.name,
            layout=payload.layout,
            temp_bg_id=payload.temp_bg_id,
            bg_color=payload.bg_color,
            description=payload.description,
        )
        return {
            "status": "SUCCESS",
            "template": tpl_data,
            "preview_url": f"/api/templates/{tpl_data['id']}/preview",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal template creation error: {e}",
        )


@router.delete("/templates/custom/{template_id}", summary="Удалить кастомный шаблон")
async def remove_custom_template(template_id: str):
    """Удаляет сохраненный кастомный шаблон."""
    if not template_id.startswith("custom_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалять базовые встроенные шаблоны",
        )
    deleted = delete_custom_template(template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кастомный шаблон не найден",
        )
    return {"status": "DELETED", "template_id": template_id}


@router.get("/templates/{template_id}/preview", summary="Получить фото-превью шаблона")
async def get_template_preview(template_id: str):
    """
    Отдает изображение бейджа в формате PNG для отображения в интерфейсе пользователя.
    """
    all_tpl_ids = [t["id"] for t in get_templates_list()]
    if template_id not in all_tpl_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Шаблон '{template_id}' не найден.",
        )

    preview_path = Path(f"./templates/previews/{template_id}.png")
    if not preview_path.exists():
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        img = render_template_badge(
            name="Александр",
            surname="Смирнов",
            item_id=101,
            template_id=template_id,
            event_date="15.11.2026",
        )
        img.save(preview_path)

    return FileResponse(
        path=preview_path,
        media_type="image/png",
        filename=f"{template_id}_preview.png",
    )


class TextEmployeesPayload(BaseModel):
    text: str = Field(..., description="Построчный список сотрудников")


@router.post("/upload-employees", summary="Загрузить список сотрудников из файла Excel (.xlsx) или CSV (.csv)")
async def upload_employees(file: UploadFile = File(...)):
    """
    Принимает файл .xlsx, .xls или .csv со списком сотрудников и возвращает
    структурированный список для генератора бейджей.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пуст.")

    from utils.importer import parse_employee_file
    employees = parse_employee_file(content, file.filename or "file.csv")
    if not employees:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось найти имена сотрудников в файле. Убедитесь, что в файле есть строки с именами.",
        )

    return {
        "status": "SUCCESS",
        "count": len(employees),
        "employees": employees,
    }


@router.post("/parse-text-employees", summary="Парсинг списка сотрудников из простого текста")
async def parse_text_employees_endpoint(payload: TextEmployeesPayload):
    """Парсит введенный построчно текст со списком сотрудников."""
    from utils.importer import parse_employee_text
    employees = parse_employee_text(payload.text)
    return {
        "status": "SUCCESS",
        "count": len(employees),
        "employees": employees,
    }


@router.post("/create_card", summary="Create cards in background", status_code=status.HTTP_202_ACCEPTED)
async def create_card(
    data: List[DataSchema],
    template: str = Query(
        default="classic_blue",
        description="ID шаблона (например: classic_blue, dark_modern, minimal_white, festival_green или ID кастомного шаблона)",
    ),
    event_date: str = Query(
        default="15.11.2026",
        description="Дата проведения мероприятия (например, '15.11.2026')",
    ),
    category_title: str | None = Query(
        default=None,
        description="Верхняя надпись/категория бейджа (например, 'EVENT PASS', 'VIP', 'СПИКЕР'). Оставьте пустым, чтобы не отображать.",
    ),
    phone: str | None = Query(
        default=None,
        description="Контактный номер телефона компании/мероприятия (опционально, если не задан в сотрудниках)",
    ),
    website: str | None = Query(
        default=None,
        description="Ссылка на сайт компании/мероприятия (опционально, если не задана в сотрудниках)",
    ),
    bg_color: str | None = Query(
        default=None,
        description="Пользовательский цвет фона карточки (HEX). Если не задан, используется цвет шаблона.",
    ),
    accent_color: str | None = Query(
        default=None,
        description="Пользовательский цвет верхней линии (HEX). Если не задан, используется цвет шаблона.",
    ),
    accent_height: int = Query(
        default=6,
        ge=1,
        le=50,
        description="Высота верхней акцентной линии в пикселях (по умолчанию 6).",
    ),
    accent_visible: bool = Query(
        default=True,
        description="Отображать ли верхнюю акцентную линию.",
    ),
    qr_fields: str | None = Query(
        default=None,
        description="Поля для включения в QR-код через запятую (например: name,id,date,phone,website).",
    ),
    is_pdf: bool = Query(
        default=False,
        description="Создать готовый к печати PDF лист А4 (по 8 бейджей на страницу) внутри ZIP архива",
    ),
):
    """
    Запускает фоновую генерацию карточек.
    - data: список участников (максимум 500).
    - template: базовый или кастомный шаблон.
    - event_date: дата мероприятия (отображается на бейдже и зашивается в QR).
    - category_title: верхняя плашка (например 'EVENT PASS'). Если пусто, надпись не выводится.
    - phone: телефон на бейдже.
    - website: сайт на бейдже.
    - bg_color: пользовательский цвет фона карточки.
    - accent_color: цвет верхней акцентной линии.
    - accent_height: высота верхней линии.
    - accent_visible: видимость верхней линии.
    - qr_fields: список полей для кодирования в QR-код.
    - is_pdf: если True, в ZIP дополнительно генерируется многостраничный PDF А4.
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
    qr_fields_list = [f.strip() for f in qr_fields.split(",") if f.strip()] if qr_fields else None

    # 1. Записываем начальный статус в KV
    kv = await get_kv()
    initial_event = {
        "status": "QUEUED",
        "current": 0,
        "total": len(data),
        "percent": 0,
        "template": template,
        "event_date": event_date,
        "category_title": category_title,
        "phone": phone,
        "website": website,
        "bg_color": bg_color,
        "accent_color": accent_color,
        "accent_height": accent_height,
        "accent_visible": accent_visible,
        "qr_fields": qr_fields_list,
        "is_pdf": is_pdf,
    }
    await kv.put(project_uuid, json.dumps(initial_event).encode("utf-8"))

    # 2. Отправляем задачу в постоянную очередь JetStream
    await create_a_simple_cards.kiq(
        data=payload,
        project_uuid=project_uuid,
        template_id=template,
        event_date=event_date,
        category_title=category_title,
        phone=phone,
        website=website,
        bg_color=bg_color,
        accent_color=accent_color,
        accent_height=accent_height,
        accent_visible=accent_visible,
        qr_fields=qr_fields_list,
        is_pdf=is_pdf,
    )

    return {
        "status": "QUEUED",
        "project_uuid": project_uuid,
        "total_items": len(data),
        "template": template,
        "event_date": event_date,
        "category_title": category_title,
        "phone": phone,
        "website": website,
        "is_pdf": is_pdf,
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
