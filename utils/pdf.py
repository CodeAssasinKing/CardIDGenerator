from pathlib import Path
from typing import List
from PIL import Image, ImageDraw


def create_a4_print_sheets(cards: List[Image.Image]) -> List[Image.Image]:
    """
    Размещает карточки 450x300 на листах А4 (150 DPI: 1240 x 1754 px)
    в виде сетки 2 колонки x 4 строки (по 8 бейджей на страницу) с тонкими метками для резки.
    """
    a4_w, a4_h = 1240, 1754
    cols, rows = 2, 4
    per_page = cols * rows

    card_w, card_h = 450, 300
    gap_x = (a4_w - cols * card_w) // (cols + 1)
    gap_y = (a4_h - rows * card_h) // (rows + 1)

    pages: List[Image.Image] = []

    for i in range(0, len(cards), per_page):
        batch = cards[i : i + per_page]
        page = Image.new("RGB", (a4_w, a4_h), "#FFFFFF")
        draw = ImageDraw.Draw(page)

        for idx, card in enumerate(batch):
            col = idx % cols
            row = idx // cols
            x = gap_x + col * (card_w + gap_x)
            y = gap_y + row * (card_h + gap_y)

            # Вставляем карточку
            page.paste(card, (x, y))

            # Рисуем тонкий светло-серый контур для нарезки
            draw.rectangle(
                [(x - 1, y - 1), (x + card_w, y + card_h)],
                outline="#CBD5E1",
                width=1,
            )

        pages.append(page)

    return pages


def save_cards_to_pdf(
    cards: List[Image.Image],
    a4_output_path: Path,
    single_output_path: Path | None = None,
) -> None:
    """
    Сохраняет список карточек в:
    1. Многостраничный печатный лист А4 (по 8 бейджей на страницу).
    2. Постраничный PDF (1 бейдж на страницу).
    """
    if not cards:
        return

    # 1. Печатный лист А4
    a4_pages = create_a4_print_sheets(cards)
    if a4_pages:
        a4_pages[0].save(
            str(a4_output_path),
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=a4_pages[1:],
        )

    # 2. Постраничный PDF (одна карточка на лист)
    if single_output_path and cards:
        cards[0].save(
            str(single_output_path),
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=cards[1:],
        )
