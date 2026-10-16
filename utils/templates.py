import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any

from PIL import Image, ImageDraw, ImageOps
import qrcode
from utils.fonts import get_font, get_fitted_font

CUSTOM_DIR = Path("./templates/custom")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BadgeTemplate:
    id: str
    name: str
    description: str
    bg_color: str
    accent_bar_color: str
    text_primary: str
    text_secondary: str
    badge_tag_bg: str
    badge_tag_text: str
    qr_dark: str
    qr_light: str
    border_color: str
    category_title: str


TEMPLATES: Dict[str, BadgeTemplate] = {
    "classic_blue": BadgeTemplate(
        id="classic_blue",
        name="Classic Blue (Tech)",
        description="Строгий деловой стиль для IT-конференций и митапов",
        bg_color="#FFFFFF",
        accent_bar_color="#2563EB",
        text_primary="#0F172A",
        text_secondary="#64748B",
        badge_tag_bg="#F1F5F9",
        badge_tag_text="#334155",
        qr_dark="#0F172A",
        qr_light="#FFFFFF",
        border_color="#E2E8F0",
        category_title="CONFERENCE PASS",
    ),
    "dark_modern": BadgeTemplate(
        id="dark_modern",
        name="Dark Modern (VIP)",
        description="Премиальный темный стиль для закрытых клубов и VIP-гостей",
        bg_color="#0F172A",
        accent_bar_color="#F59E0B",
        text_primary="#F8FAFC",
        text_secondary="#94A3B8",
        badge_tag_bg="#1E293B",
        badge_tag_text="#F59E0B",
        qr_dark="#0F172A",
        qr_light="#FFFFFF",
        border_color="#334155",
        category_title="VIP ACCESS",
    ),
    "minimal_white": BadgeTemplate(
        id="minimal_white",
        name="Minimalist Monochrome",
        description="Сдержанный монохромный стиль для выставок, форумов и лекций",
        bg_color="#FAFAFA",
        accent_bar_color="#18181B",
        text_primary="#18181B",
        text_secondary="#71717A",
        badge_tag_bg="#E4E4E7",
        badge_tag_text="#18181B",
        qr_dark="#18181B",
        qr_light="#FAFAFA",
        border_color="#E4E4E7",
        category_title="EVENT PASS",
    ),
    "festival_green": BadgeTemplate(
        id="festival_green",
        name="Festival Emerald (Hackathon)",
        description="Свежий яркий дизайн для хакатонов, фестивалей и соревнований",
        bg_color="#FFFFFF",
        accent_bar_color="#059669",
        text_primary="#064E3B",
        text_secondary="#059669",
        badge_tag_bg="#ECFDF5",
        badge_tag_text="#065F46",
        qr_dark="#064E3B",
        qr_light="#FFFFFF",
        border_color="#A7F3D0",
        category_title="HACKATHON PARTICIPANT",
    ),
}


def check_template_name_unique(name: str, exclude_id: str | None = None) -> bool:
    """
    Проверяет, уникально ли имя шаблона (без учета регистра).
    Имя не должно совпадать ни со стандартными, ни с уже сохраненными кастомными шаблонами.
    """
    clean_name = name.strip().lower()

    # 1. Проверяем среди 4 базовых
    for t in TEMPLATES.values():
        if t.name.strip().lower() == clean_name:
            return False

    # 2. Проверяем среди кастомных шаблонов
    for json_file in CUSTOM_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if data.get("name", "").strip().lower() == clean_name:
                if exclude_id and data.get("id") == exclude_id:
                    continue
                return False
        except Exception:
            continue

    return True


def get_custom_templates() -> Dict[str, dict]:
    """Считывает все сохраненные кастомные шаблоны из ./templates/custom/*.json."""
    custom_map = {}
    if not CUSTOM_DIR.exists():
        return custom_map

    for json_file in CUSTOM_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            tpl_id = data.get("id")
            if tpl_id:
                custom_map[tpl_id] = data
        except Exception:
            continue

    return custom_map


def save_custom_template(
    name: str,
    layout: dict,
    temp_bg_id: str | None = None,
    bg_color: str = "#FFFFFF",
    description: str = "",
) -> dict:
    """
    Сохраняет новый кастомный шаблон с проверкой уникальности имени,
    перемещает фон и генерирует превью.
    """
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Название шаблона не может быть пустым.")

    if not check_template_name_unique(clean_name):
        raise ValueError(f"Шаблон с названием '{clean_name}' уже существует. Пожалуйста, укажите другое название.")

    clean_slug = re.sub(r"[^a-zA-Z0-9]", "", clean_name.lower())[:15]
    template_id = f"custom_{clean_slug}_{uuid.uuid4().hex[:8]}" if clean_slug else f"custom_{uuid.uuid4().hex[:10]}"

    bg_image_path = None
    if temp_bg_id:
        temp_file = CUSTOM_DIR / f"{temp_bg_id}.png"
        if temp_file.exists():
            final_bg = CUSTOM_DIR / f"{template_id}_bg.png"
            shutil.copy2(temp_file, final_bg)
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass
            bg_image_path = str(final_bg)

    template_data = {
        "id": template_id,
        "name": clean_name,
        "description": description.strip() or "Пользовательский дизайн из конструктора",
        "is_custom": True,
        "bg_color": bg_color,
        "bg_image": bg_image_path,
        "layout": layout,
    }

    # Сохраняем конфигурацию в JSON
    json_path = CUSTOM_DIR / f"{template_id}.json"
    json_path.write_text(json.dumps(template_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Генерируем превью
    preview_dir = Path("./templates/previews")
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_img = render_template_badge(
        name="Александр",
        surname="Смирнов",
        item_id=101,
        template_id=template_id,
        event_date="15.11.2026",
    )
    preview_img.save(preview_dir / f"{template_id}.png")

    return template_data


def delete_custom_template(template_id: str) -> bool:
    """Удаляет кастомный шаблон (json, фон и превью)."""
    json_file = CUSTOM_DIR / f"{template_id}.json"
    bg_file = CUSTOM_DIR / f"{template_id}_bg.png"
    preview_file = Path("./templates/previews") / f"{template_id}.png"

    deleted = False
    if json_file.exists():
        json_file.unlink(missing_ok=True)
        deleted = True
    if bg_file.exists():
        bg_file.unlink(missing_ok=True)
    if preview_file.exists():
        preview_file.unlink(missing_ok=True)

    return deleted


def get_templates_list() -> List[Dict[str, Any]]:
    """Возвращает метаданные 4 базовых шаблонов + всех сохраненных кастомных шаблонов."""
    # 1. Базовые шаблоны
    result = [
        {
            "id": tpl.id,
            "name": tpl.name,
            "description": tpl.description,
            "primary_color": tpl.accent_bar_color,
            "bg_color": tpl.bg_color,
            "category_title": tpl.category_title,
            "preview_url": f"/api/templates/{tpl.id}/preview",
            "is_custom": False,
        }
        for tpl in TEMPLATES.values()
    ]

    # 2. Кастомные шаблоны
    custom_map = get_custom_templates()
    for c_id, c_data in custom_map.items():
        result.append({
            "id": c_id,
            "name": c_data.get("name", "Пользовательский"),
            "description": c_data.get("description", "Кастомный дизайн"),
            "primary_color": c_data.get("layout", {}).get("name", {}).get("color", "#2563EB"),
            "bg_color": c_data.get("bg_color", "#FFFFFF"),
            "category_title": c_data.get("layout", {}).get("category_title", {}).get("text", "EVENT PASS"),
            "preview_url": f"/api/templates/{c_id}/preview",
            "is_custom": True,
            "layout": c_data.get("layout", {}),
            "bg_image": c_data.get("bg_image"),
        })

    return result


def is_dark_color(hex_color: str) -> bool:
    """Определяет, является ли цвет тёмным (по воспринимаемой яркости)."""
    if not hex_color or not isinstance(hex_color, str):
        return False
    clean = hex_color.lstrip("#")
    try:
        if len(clean) == 3:
            r = int(clean[0] * 2, 16)
            g = int(clean[1] * 2, 16)
            b = int(clean[2] * 2, 16)
        elif len(clean) == 6:
            r = int(clean[0:2], 16)
            g = int(clean[2:4], 16)
            b = int(clean[4:6], 16)
        else:
            return False
        return (0.299 * r + 0.587 * g + 0.114 * b) < 128
    except Exception:
        return False


def build_qr_payload(
    name: str = "",
    surname: str = "",
    item_id: int | str = "",
    event_date: str = "",
    phone: str | None = None,
    website: str | None = None,
    full_name: str | None = None,
    qr_fields: List[str] | None = None,
) -> str:
    """
    Формирует строку для кодирования в QR-код на основе выбранных полей.
    Поддерживаемые поля:
    - 'name' или 'fio': ФИО / Имя сотрудника
    - 'id': идентификатор бейджа
    - 'date': дата мероприятия
    - 'phone': телефон
    - 'website': ссылка на сайт
    """
    if qr_fields is None:
        qr_fields = ["name", "id", "date"]
        if phone and str(phone).strip():
            qr_fields.append("phone")
        if website and str(website).strip():
            qr_fields.append("website")

    norm_fields = [str(f).strip().lower() for f in qr_fields if str(f).strip()]

    # Если выбрана только ссылка на сайт — генерируем прямую кликабельную ссылку
    if norm_fields == ["website"] and website and str(website).strip():
        web = str(website).strip()
        if not web.startswith("http://") and not web.startswith("https://"):
            return f"https://{web}"
        return web

    lines = []

    # 1. ФИО / Имя
    if any(k in norm_fields for k in ("name", "fio", "fullname", "full_name")):
        fn = (full_name or f"{name} {surname}").strip()
        if fn:
            lines.append(f"ФИО: {fn}")
        elif name:
            lines.append(f"Имя: {name}")

    # 2. ID
    if "id" in norm_fields and item_id is not None and str(item_id).strip():
        lines.append(f"ID: #{item_id}")

    # 3. Дата
    if "date" in norm_fields and event_date and str(event_date).strip():
        lines.append(f"Дата: {event_date}")

    # 4. Телефон
    if "phone" in norm_fields and phone and str(phone).strip():
        p = str(phone).strip()
        lines.append(f"Тел: {p}")

    # 5. Сайт
    if "website" in norm_fields and website and str(website).strip():
        w = str(website).strip()
        lines.append(f"Сайт: {w}")

    if lines:
        return "\n".join(lines)

    # Если всё отключено, возвращаем хотя бы базовый ID или Имя
    return str(item_id or name or "PASS")


def render_template_badge(
    name: str,
    surname: str,
    item_id: int,
    template_id: str = "classic_blue",
    event_date: str = "15.11.2026",
    category_title: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    full_name: str | None = None,
    bg_color: str | None = None,
    accent_color: str | None = None,
    accent_height: int | None = None,
    accent_visible: bool | None = None,
    qr_fields: List[str] | None = None,
) -> Image.Image:
    """
    Отрисовывает бейдж 450x300 на основе базового или кастомного шаблона
    с поддержкой ФИО в одну строку, контактов (телефон, сайт) и QR-кода.
    """
    custom_templates = get_custom_templates()

    # --- Рендеринг кастомного шаблона из конструктора ---
    if template_id in custom_templates:
        c_data = custom_templates[template_id]
        bg_image_path = c_data.get("bg_image")
        final_bg = bg_color or c_data.get("bg_color", "#FFFFFF")

        if bg_image_path and Path(bg_image_path).exists() and not bg_color:
            base_img = Image.open(bg_image_path).convert("RGB")
            # Автоматическая умная подгонка (crop/fit к пропорциям 3:2, 450x300)
            card = ImageOps.fit(base_img, (450, 300), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            card = Image.new("RGB", (450, 300), final_bg)

        draw = ImageDraw.Draw(card)
        layout = c_data.get("layout", {})

        # 0. Верхняя декоративная акцентная полоса
        accent_conf = layout.get("accent_bar", {})
        if accent_visible is not None:
            show_accent = accent_visible
        elif "accent_bar" in layout:
            show_accent = accent_conf.get("visible", True)
        else:
            show_accent = False if (bg_image_path and not bg_color) else True

        if show_accent:
            bar_h = accent_height if accent_height is not None else accent_conf.get("height", 6)
            bar_c = accent_color or accent_conf.get("color", "#2563EB")
            draw.rectangle([(0, 0), (450, max(1, bar_h))], fill=bar_c)

        # 1. Заголовок / Категория
        cat_conf = layout.get("category_title", {})
        if cat_conf.get("visible", True):
            if category_title is None:
                header_text = cat_conf.get("text", "EVENT PASS")
            else:
                header_text = category_title.strip()

            if header_text:
                cat_font = get_font("SemiBold", size=cat_conf.get("size", 11))
                draw.text(
                    (cat_conf.get("x", 28), cat_conf.get("y", 26)),
                    header_text,
                    font=cat_font,
                    fill=cat_conf.get("color", "#64748B"),
                )

        # 2. Имя и Фамилия (или ФИО в одну строку)
        fn_conf = layout.get("full_name", {})
        if fn_conf.get("visible", False):
            # Режим ФИО в одну строку
            display_fn = (full_name or f"{name} {surname}").strip()
            if display_fn:
                max_w = fn_conf.get("max_w", 250)
                font_fn = get_fitted_font(display_fn, max_width=max_w, initial_size=fn_conf.get("size", 22), min_size=14, weight="Bold")
                draw.text(
                    (fn_conf.get("x", 28), fn_conf.get("y", 68)),
                    display_fn,
                    font=font_fn,
                    fill=fn_conf.get("color", "#0F172A"),
                )
        else:
            # Раздельные Имя и Фамилия
            name_conf = layout.get("name", {})
            if name_conf.get("visible", True) and name:
                font_name = get_fitted_font(name, max_width=230, initial_size=name_conf.get("size", 24), min_size=15, weight="Bold")
                draw.text(
                    (name_conf.get("x", 28), name_conf.get("y", 52)),
                    name,
                    font=font_name,
                    fill=name_conf.get("color", "#0F172A"),
                )

            sur_conf = layout.get("surname", {})
            if sur_conf.get("visible", True) and surname:
                font_surname = get_fitted_font(surname, max_width=230, initial_size=sur_conf.get("size", 24), min_size=15, weight="Bold")
                draw.text(
                    (sur_conf.get("x", 28), sur_conf.get("y", 84)),
                    surname,
                    font=font_surname,
                    fill=sur_conf.get("color", "#0F172A"),
                )

        # 3. Тег ID
        id_conf = layout.get("id_badge", {})
        if id_conf.get("visible", True):
            font_id = get_font("SemiBold", size=id_conf.get("size", 12))
            id_text = f"ID #{item_id}"
            id_w = int(font_id.getlength(id_text))
            x, y = id_conf.get("x", 28), id_conf.get("y", 150)
            draw.rounded_rectangle([(x, y), (x + id_w + 20, y + 30)], radius=6, fill=id_conf.get("bg", "#F1F5F9"))
            draw.text((x + 10, y + 6), id_text, font=font_id, fill=id_conf.get("color", "#334155"))

        # 4. Тег даты (без слова DATE:)
        date_conf = layout.get("date", {})
        if date_conf.get("visible", True) and event_date and str(event_date).strip():
            date_str = str(event_date).strip()
            font_date = get_font("Medium", size=date_conf.get("size", 11))
            date_w = int(font_date.getlength(date_str))
            x, y = date_conf.get("x", 115), date_conf.get("y", 150)
            draw.rounded_rectangle([(x, y), (x + date_w + 20, y + 30)], radius=6, fill=date_conf.get("bg", "#F1F5F9"))
            draw.text((x + 10, y + 6), date_str, font=font_date, fill=date_conf.get("color", "#334155"))

        # 5. Номер телефона (если включен в макете ИЛИ реально передан)
        phone_conf = layout.get("phone", {})
        # Приоритет: переданный phone > текст из макета
        final_phone = (phone or "").strip() or (phone_conf.get("text", "") or "").strip()
        phone_visible = phone_conf.get("visible", True)
        if final_phone and (phone_visible or (phone and str(phone).strip())):
            clean_p = final_phone if final_phone.lower().startswith("тел") else f"Тел: {final_phone}"
            p_font = get_font("Medium", size=phone_conf.get("size", 10))
            draw.text(
                (phone_conf.get("x", 28), phone_conf.get("y", 204)),
                clean_p,
                font=p_font,
                fill=phone_conf.get("color", "#64748B"),
            )

        # 6. Ссылка на сайт (если включена в макете ИЛИ реально передана)
        web_conf = layout.get("website", {})
        final_web = (website or "").strip() or (web_conf.get("text", "") or "").strip()
        web_visible = web_conf.get("visible", True)
        if final_web and (web_visible or (website and str(website).strip())):
            w_font = get_font("Medium", size=web_conf.get("size", 10))
            draw.text(
                (web_conf.get("x", 28), web_conf.get("y", 224)),
                final_web,
                font=w_font,
                fill=web_conf.get("color", "#2563EB"),
            )

        # 7. QR-код
        qr_conf = layout.get("qr_code", {})
        if qr_conf.get("visible", True):
            qr_size = qr_conf.get("size", 120)
            qr_x, qr_y = qr_conf.get("x", 288), qr_conf.get("y", 58)
            qr_dark = qr_conf.get("qr_dark", "#0F172A")
            qr_light = qr_conf.get("qr_light", "#FFFFFF")

            # Конфигурация полей QR
            effective_qr_fields = qr_fields if qr_fields is not None else qr_conf.get("fields")
            qr_payload = build_qr_payload(
                name=name,
                surname=surname,
                item_id=item_id,
                event_date=event_date,
                phone=final_phone,
                website=final_web,
                full_name=full_name,
                qr_fields=effective_qr_fields,
            )

            qr = qrcode.QRCode(box_size=4, border=1)
            qr.add_data(qr_payload)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color=qr_dark, back_color=qr_light).convert("RGB")
            qr_img = qr_img.resize((qr_size, qr_size))

            if qr_conf.get("border", True):
                draw.rounded_rectangle(
                    [(qr_x - 6, qr_y - 6), (qr_x + qr_size + 6, qr_y + qr_size + 6)],
                    radius=8,
                    outline=qr_conf.get("border_color", "#E2E8F0"),
                    width=1,
                    fill=qr_light,
                )
            card.paste(qr_img, (qr_x, qr_y))

        # 8. Пользовательские произвольные тексты (Custom Texts)
        custom_texts = layout.get("custom_texts", [])
        if not isinstance(custom_texts, list):
            custom_texts = []

        # Также считываем из словаря layout, если они сохранены как ключи custom_text_... или text_...
        for k, v in layout.items():
            if (k.startswith("custom_text") or k.startswith("text_")) and isinstance(v, dict):
                if not any(isinstance(ct, dict) and ct.get("id") == k for ct in custom_texts):
                    custom_texts.append(v)

        for c_txt in custom_texts:
            if not isinstance(c_txt, dict) or not c_txt.get("visible", True):
                continue
            raw_t = (c_txt.get("text") or "").strip()
            if not raw_t:
                continue

            t_size = int(c_txt.get("size", 14))
            t_color = c_txt.get("color", "#0F172A")
            t_x = int(c_txt.get("x", 28))
            t_y = int(c_txt.get("y", 180))
            t_weight = c_txt.get("weight", "Bold")
            if t_weight not in ("Bold", "SemiBold", "Medium", "Regular"):
                t_weight = "Bold"

            font_custom = get_font(t_weight, size=t_size)
            draw.text((t_x, t_y), raw_t, font=font_custom, fill=t_color)

        return card

    # --- Рендеринг базовых 4 шаблонов ---
    tpl = TEMPLATES.get(template_id, TEMPLATES["classic_blue"])

    final_bg = bg_color or tpl.bg_color
    dark_mode = is_dark_color(final_bg)

    card = Image.new("RGB", (450, 300), final_bg)
    draw = ImageDraw.Draw(card)

    text_primary = "#F8FAFC" if dark_mode else tpl.text_primary
    text_secondary = "#94A3B8" if dark_mode else tpl.text_secondary
    border_color = "#334155" if dark_mode else tpl.border_color
    badge_tag_bg = "#1E293B" if dark_mode else tpl.badge_tag_bg
    badge_tag_text = "#38BDF8" if dark_mode else tpl.badge_tag_text

    # 1. Верхняя декоративная акцентная полоса
    show_accent = accent_visible if accent_visible is not None else True
    if show_accent:
        bar_h = accent_height if accent_height is not None else 6
        bar_c = accent_color or tpl.accent_bar_color
        draw.rectangle([(0, 0), (450, max(1, bar_h))], fill=bar_c)

    if template_id == "minimal_white" and not bg_color:
        draw.rectangle([(0, 0), (449, 299)], outline=border_color, width=1)

    # 2. Левая колонка: Типографика
    if category_title is None:
        header_text = tpl.category_title
    else:
        header_text = category_title.strip()

    if header_text:
        font_cat = get_font("SemiBold", size=11)
        draw.text((28, 26), header_text, font=font_cat, fill=text_secondary)

    max_text_width = 230
    clean_fn = (full_name or "").strip()
    clean_name = str(name).strip()
    clean_surname = str(surname).strip()

    # Если задано ФИО в одну строку или фамилия отсутствует
    if clean_fn or not clean_surname:
        single_name = clean_fn or clean_name
        font_single = get_fitted_font(single_name, max_width=max_text_width, initial_size=24, min_size=15, weight="Bold")
        draw.text((28, 68), single_name, font=font_single, fill=text_primary)
    else:
        font_name = get_fitted_font(clean_name, max_width=max_text_width, initial_size=24, min_size=16, weight="Bold")
        font_surname = get_fitted_font(clean_surname, max_width=max_text_width, initial_size=24, min_size=16, weight="Bold")
        draw.text((28, 52), clean_name, font=font_name, fill=text_primary)
        draw.text((28, 84), clean_surname, font=font_surname, fill=text_primary)

    draw.line([(28, 134), (245, 134)], fill=border_color, width=1)

    # Тег ID
    draw.rounded_rectangle([(28, 150), (105, 180)], radius=6, fill=badge_tag_bg)
    font_id = get_font("SemiBold", size=12)
    draw.text((36, 156), f"ID #{item_id}", font=font_id, fill=badge_tag_text)

    # Тег даты (без слова DATE:)
    if event_date and str(event_date).strip():
        date_str = str(event_date).strip()
        font_date = get_font("Medium", size=11)
        date_w = int(font_date.getlength(date_str))
        pill_right = 115 + date_w + 24
        draw.rounded_rectangle([(115, 150), (pill_right, 180)], radius=6, fill=badge_tag_bg)
        draw.text((127, 157), date_str, font=font_date, fill=badge_tag_text)

    # Телефон и Сайт (если заданы)
    contact_y = 196
    has_contact = False
    font_contact = get_font("Medium", size=9)

    if phone and str(phone).strip():
        clean_p = str(phone).strip()
        display_phone = clean_p if clean_p.lower().startswith("тел") else f"Тел: {clean_p}"
        draw.text((28, contact_y), display_phone, font=font_contact, fill=text_secondary)
        contact_y += 16
        has_contact = True

    if website and str(website).strip():
        clean_w = str(website).strip()
        web_color = "#38BDF8" if dark_mode else tpl.accent_bar_color
        draw.text((28, contact_y), clean_w, font=font_contact, fill=web_color)
        contact_y += 16
        has_contact = True

    # Нижняя подпись
    font_foot = get_font("Regular", size=10)
    footer_text = "OFFICIAL PASS • ACCESS GRANTED"
    footer_y = 252 if has_contact else 248
    draw.text((28, footer_y), footer_text, font=font_foot, fill=text_secondary)

    # 3. Правая колонка: QR-код
    qr_payload = build_qr_payload(
        name=clean_name,
        surname=clean_surname,
        item_id=item_id,
        event_date=event_date,
        phone=phone,
        website=website,
        full_name=clean_fn,
        qr_fields=qr_fields,
    )
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=tpl.qr_dark, back_color=tpl.qr_light).convert("RGB")
    qr_img = qr_img.resize((125, 125))

    draw.rounded_rectangle([(280, 50), (420, 190)], radius=10, outline=border_color, width=1, fill=tpl.qr_light)
    card.paste(qr_img, (288, 58))

    font_scan = get_font("Medium", size=10)
    draw.text((310, 202), "SCAN FOR ACCESS", font=font_scan, fill=tpl.text_secondary)

    return card
