from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from services.storage import read_json, write_json

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str
    email: str
    password: str
    headless: Optional[bool] = False


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    headless: Optional[bool] = None


@router.get("/")
def list_accounts():
    accounts = read_json("accounts")
    # Mask password in response
    return [
        {**acc, "password": "••••••••"} for acc in accounts
    ]


@router.post("/")
def create_account(body: AccountCreate):
    accounts = read_json("accounts")
    # Check duplicate email
    if any(a["email"] == body.email for a in accounts):
        raise HTTPException(400, "Email đã tồn tại")
    new_account = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "email": body.email,
        "password": body.password,
        "headless": body.headless,
        "active": True,
    }
    accounts.append(new_account)
    write_json("accounts", accounts)
    return {**new_account, "password": "••••••••"}


@router.put("/{account_id}")
def update_account(account_id: str, body: AccountUpdate):
    accounts = read_json("accounts")
    for acc in accounts:
        if acc["id"] == account_id:
            if body.name is not None:
                acc["name"] = body.name
            if body.email is not None:
                acc["email"] = body.email
            if body.password is not None:
                acc["password"] = body.password
            if body.headless is not None:
                acc["headless"] = body.headless
            write_json("accounts", accounts)
            return {**acc, "password": "••••••••"}
    raise HTTPException(404, "Tài khoản không tồn tại")


@router.delete("/{account_id}")
def delete_account(account_id: str):
    accounts = read_json("accounts")
    new_list = [a for a in accounts if a["id"] != account_id]
    if len(new_list) == len(accounts):
        raise HTTPException(404, "Tài khoản không tồn tại")
    write_json("accounts", new_list)
    return {"message": "Đã xóa tài khoản"}
