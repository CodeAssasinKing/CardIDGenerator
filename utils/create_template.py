from pathlib import Path
from PIL import Image

async def create_a_template():
    img = Image.new("RGB", (450, 300), "white")
    if not Path("./templates/").exists():
        Path("./templates/").mkdir()
    img.save(f"./templates/white.png")
    return {"message": "Template created successfully"}