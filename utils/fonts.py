from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode

# Базовый путь к шрифтам Montserrat
FONTS_DIR = Path("./fonts/Montserrat/static")


@lru_cache(maxsize=64)
def get_font(weight: str = "Regular", size: int = 24) -> ImageFont.FreeTypeFont:
    """
    Возвращает шрифт Montserrat нужной насыщенности и размера с LRU-кэшированием.
    Доступные насыщенности: Bold, SemiBold, Medium, Regular, ExtraBold, Light.
    """
    font_file = FONTS_DIR / f"Montserrat-{weight}.ttf"

    if font_file.exists():
        return ImageFont.truetype(str(font_file), size=size)

    # Fallback 1: базовый Regular
    fallback_regular = FONTS_DIR / "Montserrat-Regular.ttf"
    if fallback_regular.exists():
        return ImageFont.truetype(str(fallback_regular), size=size)

    # Fallback 2: дефолтный шрифт Pillow
    return ImageFont.load_default(size=size)


def get_fitted_font(
    text: str,
    max_width: int,
    initial_size: int = 24,
    min_size: int = 12,
    weight: str = "Bold",
) -> ImageFont.FreeTypeFont:
    """
    Динамически подбирает максимальный размер шрифта, при котором строка помещается в max_width.
    Предотвращает наползание длинных фамилий на QR-код.
    """
    for sz in range(initial_size, min_size - 1, -2):
        font = get_font(weight=weight, size=sz)
        if font.getlength(text) <= max_width:
            return font

    return get_font(weight=weight, size=min_size)


def render_styled_card(name: str, surname: str, item_id: int) -> Image.Image:
    """
    Отрисовывает карточку-бейдж 450x300 с профессиональной типографикой Montserrat и встроенным QR-кодом.
    """
    card = Image.new("RGB", (450, 300), "#FFFFFF")
    draw = ImageDraw.Draw(card)

    # 1. Верхняя декоративная акцентная полоса (синий индиго)
    draw.rectangle([(0, 0), (450, 6)], fill="#2563EB")

    # 2. Левая колонка: Типографика
    # Категория / Бейдж типа
    font_sub = get_font("SemiBold", size=11)
    draw.text((28, 28), "OFFICIAL PASS / БЕЙДЖ", font=font_sub, fill="#64748B")

    # Имя и Фамилия с автоматическим подбором размера под ширину
    max_text_width = 230
    font_name = get_fitted_font(name, max_width=max_text_width, initial_size=24, min_size=16, weight="Bold")
    font_surname = get_fitted_font(surname, max_width=max_text_width, initial_size=24, min_size=16, weight="Bold")

    draw.text((28, 56), name, font=font_name, fill="#0F172A")
    draw.text((28, 88), surname, font=font_surname, fill="#0F172A")

    # Тонкая разделительная черта
    draw.line([(28, 140), (240, 140)], fill="#E2E8F0", width=1)

    # Статусный тег (ID Badge Pill)
    draw.rounded_rectangle([(28, 160), (128, 192)], radius=6, fill="#F1F5F9")
    font_id = get_font("SemiBold", size=13)
    draw.text((42, 168), f"ID #{item_id}", font=font_id, fill="#334155")

    # Нижняя подпись
    font_footer = get_font("Regular", size=11)
    draw.text((28, 245), "VALID FOR CONFERENCE 2026", font=font_footer, fill="#94A3B8")

    # 3. Правая колонка: Встроенный QR-код
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(f"{name}:{surname}:{item_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF").convert("RGB")
    qr_img = qr_img.resize((125, 125))

    # Рамка вокруг QR-кода
    draw.rounded_rectangle([(280, 50), (420, 190)], radius=10, outline="#E2E8F0", width=1)
    card.paste(qr_img, (288, 58))

    # Подпись под QR-кодом
    font_scan = get_font("Medium", size=10)
    draw.text((310, 202), "SCAN FOR ACCESS", font=font_scan, fill="#94A3B8")

    return card
