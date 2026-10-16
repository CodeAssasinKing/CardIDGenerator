from pathlib import Path
from PIL import Image
from utils.templates import TEMPLATES, render_template_badge


async def create_a_template():
    """
    Создает базовые файлы шаблонов и визуальные превью 4 стилей бейджей при старте приложения,
    если они еще не созданы.
    """
    templates_dir = Path("./templates")
    templates_dir.mkdir(parents=True, exist_ok=True)

    # 1. Базовый белый шаблон
    white_png = templates_dir / "white.png"
    if not white_png.exists():
        img = Image.new("RGB", (450, 300), "white")
        img.save(white_png)

    # 2. Папка с превью для каждого из 4 шаблонов
    preview_dir = templates_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    for tpl_id in TEMPLATES:
        preview_file = preview_dir / f"{tpl_id}.png"
        if not preview_file.exists():
            preview_img = render_template_badge(
                name="Александр",
                surname="Смирнов",
                item_id=101,
                template_id=tpl_id,
                event_date="15.11.2026",
            )
            preview_img.save(preview_file)

    return {"message": "Templates and previews initialized successfully"}