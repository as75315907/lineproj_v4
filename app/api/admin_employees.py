from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_employee_service
from app.core.security import require_admin_auth
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/admin/api/employees", tags=["admin-employees"], dependencies=[Depends(require_admin_auth)])


class RolePayload(BaseModel):
    role: str


class StatusPayload(BaseModel):
    status: str


class NamePayload(BaseModel):
    name: str


class NotePayload(BaseModel):
    note: str


@router.get("")
async def list_employees(
    employee_service: EmployeeService = Depends(get_employee_service),
) -> dict:
    return {"employees": employee_service.list_employees()}


@router.post("/{uid}/role")
async def update_employee_role(
    uid: str,
    payload: RolePayload,
    employee_service: EmployeeService = Depends(get_employee_service),
) -> dict:
    if payload.role not in {"staff", "supervisor", "leader", "admin"}:
        raise HTTPException(status_code=400, detail="invalid role")
    employee_service.update_role(uid, payload.role)
    return {"ok": True, "message": "角色已更新"}


@router.post("/{uid}/name")
async def update_employee_name(
    uid: str,
    payload: NamePayload,
    employee_service: EmployeeService = Depends(get_employee_service),
) -> dict:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    employee_service.update_name(uid, payload.name)
    return {"ok": True, "message": "姓名已更新"}


@router.post("/{uid}/status")
async def update_employee_status(
    uid: str,
    payload: StatusPayload,
    employee_service: EmployeeService = Depends(get_employee_service),
) -> dict:
    if payload.status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="invalid status")
    employee_service.update_status(uid, payload.status)
    return {"ok": True, "message": "員工狀態已更新"}


@router.post("/{uid}/note")
async def update_employee_note(
    uid: str,
    payload: NotePayload,
    employee_service: EmployeeService = Depends(get_employee_service),
) -> dict:
    employee_service.update_note(uid, payload.note)
    return {"ok": True, "message": "備註已更新"}
