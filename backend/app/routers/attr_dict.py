"""属性字典路由：管理用户属性字段的元数据定义。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ActionPayload, ActionResult, AttrDictEntry
from app.services.attr_dict import (
    list_attrs,
    get_attr,
    create_attr,
    update_attr,
    delete_attr,
    get_attrs_by_source,
)
from app.store import store, query_filters

router = APIRouter(prefix="/api/attr-dict", tags=["attr_dict"])


@router.get("")
def index(request: Request, page: int = 1, size: int = 20) -> dict[str, Any]:
    rows = store.rows("attr_dict")
    # query contract: filters=query_filters(request)
    filters = query_filters(request)
    if filters:
        rows = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in filters.items())]
    total = len(rows)
    start = (page - 1) * size
    return {"items": rows[start : start + size], "total": total, "page": page, "size": size}


@router.get("/{entry_id}")
def detail(entry_id: int) -> dict[str, Any]:
    row = store.find("attr_dict", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("")
def create(payload: dict[str, Any]) -> ActionResult:
    row = create_attr(payload)
    return ActionResult(ok=True, message="Created", entry=row)


@router.put("/{entry_id}")
def update(entry_id: int, payload: dict[str, Any]) -> ActionResult:
    row = store.find("attr_dict", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    updated = update_attr(row["attr_id"], payload)
    return ActionResult(ok=True, message="Updated", entry=updated)


@router.delete("/{entry_id}")
def remove(entry_id: int) -> ActionResult:
    row = store.find("attr_dict", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    delete_attr(row["attr_id"])
    return ActionResult(ok=True, message="Deleted")


@router.get("/by-source/{source}")
def by_source(source: str) -> list[dict[str, Any]]:
    return get_attrs_by_source(source)


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    row = store.find("attr_dict", entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    action = payload.action
    row["status"] = action
    row["pending"] = False
    return ActionResult(ok=True, message=action, entry=row)
