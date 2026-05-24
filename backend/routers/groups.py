from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from services.storage import read_json, write_json

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


@router.get("/")
def list_groups():
    return read_json("groups")


@router.post("/")
def create_group(body: GroupCreate):
    groups = read_json("groups")
    if any(g["url"] == body.url for g in groups):
        raise HTTPException(400, "URL group đã tồn tại")
    new_group = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "url": body.url,
        "description": body.description,
        "active": True,
    }
    groups.append(new_group)
    write_json("groups", groups)
    return new_group


@router.put("/{group_id}")
def update_group(group_id: str, body: GroupUpdate):
    groups = read_json("groups")
    for g in groups:
        if g["id"] == group_id:
            if body.name is not None:
                g["name"] = body.name
            if body.url is not None:
                g["url"] = body.url
            if body.description is not None:
                g["description"] = body.description
            write_json("groups", groups)
            return g
    raise HTTPException(404, "Group không tồn tại")


@router.delete("/{group_id}")
def delete_group(group_id: str):
    groups = read_json("groups")
    new_list = [g for g in groups if g["id"] != group_id]
    if len(new_list) == len(groups):
        raise HTTPException(404, "Group không tồn tại")
    write_json("groups", new_list)
    return {"message": "Đã xóa group"}
