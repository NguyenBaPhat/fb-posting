import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from services.storage import read_json, write_json

router = APIRouter(prefix="/templates", tags=["templates"])

TEMPLATE_IMAGES_DIR = Path(__file__).parent.parent / "data" / "template_images"
TEMPLATE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/")
def list_templates():
    return read_json("templates")


@router.post("/")
async def save_template(
    name: str = Form(...),
    content: str = Form(""),
    post_type: str = Form("normal"),
    mp_title: Optional[str] = Form(None),
    mp_price: Optional[str] = Form(None),
    mp_condition: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
):
    filenames = []
    for img in images:
        if img and img.filename:
            ext = Path(img.filename).suffix
            filename = f"{uuid.uuid4()}{ext}"
            save_path = TEMPLATE_IMAGES_DIR / filename
            with open(save_path, "wb") as f:
                f.write(await img.read())
            filenames.append(filename)

    template = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "content": content,
        "post_type": post_type,
        "mp_title": mp_title or "",
        "mp_price": mp_price or "",
        "mp_condition": mp_condition or "Mới",
        "image_filenames": filenames,
        "created_at": datetime.now().isoformat(),
    }
    templates = read_json("templates")
    templates.append(template)
    write_json("templates", templates)
    return template


@router.delete("/{template_id}")
def delete_template(template_id: str):
    templates = read_json("templates")
    tmpl = next((t for t in templates if t["id"] == template_id), None)
    if not tmpl:
        raise HTTPException(404, "Template không tồn tại")
    # Xóa file ảnh
    for filename in tmpl.get("image_filenames", []):
        path = TEMPLATE_IMAGES_DIR / filename
        if path.exists():
            path.unlink()
    write_json("templates", [t for t in templates if t["id"] != template_id])
    return {"message": "Đã xóa template"}


@router.get("/image/{filename}")
def get_template_image(filename: str):
    path = TEMPLATE_IMAGES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Không tìm thấy ảnh")
    return FileResponse(str(path))
