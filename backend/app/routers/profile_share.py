"""画像共享路由：字段授权、画像投影与共享快照的受控访问。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas import ActionResult, GrantFieldsPayload, ProjectionPayload, SharePayload
from app.services.profile_share import (
    create_projection,
    create_shared_snapshot,
    get_access_scope,
    get_share,
    grant_fields,
    list_accounts,
    list_grants,
    list_projections,
    list_shares,
    open_shared_snapshot,
    revoke_fields,
)

router = APIRouter(prefix="/api/profile-share", tags=["profile_share"])


@router.get("")
def index(page: int = 1, size: int = 20) -> dict[str, Any]:
    rows = list_shares()
    total = len(rows)
    start = (page - 1) * size
    return {"items": rows[start : start + size], "total": total, "page": page, "size": size}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    rows = list_shares()
    return {"items": rows, "total": len(rows)}


@router.get("/accounts")
def accounts() -> dict[str, Any]:
    return {"items": list_accounts(), "total": len(list_accounts())}


@router.get("/grants")
def grants() -> dict[str, Any]:
    rows = list_grants()
    return {"items": rows, "total": len(rows)}


@router.post("/grants/{grant_id}/grant")
def grant(grant_id: str, payload: GrantFieldsPayload) -> ActionResult:
    try:
        row = grant_fields(grant_id, payload.fields, payload.remark)
        return ActionResult(ok=True, message="已授权", entry=row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/grants/{grant_id}/revoke")
def revoke(grant_id: str, payload: GrantFieldsPayload) -> ActionResult:
    try:
        row = revoke_fields(grant_id, payload.fields, payload.remark)
        return ActionResult(ok=True, message="已撤回", entry=row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/scope")
def scope(card_id: str, partner_id: str) -> dict[str, Any]:
    try:
        return {"card_id": card_id, "partner_id": partner_id, "scope_tags": get_access_scope(card_id, partner_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projections")
def create_projection_entry(payload: ProjectionPayload) -> ActionResult:
    try:
        row = create_projection(payload.card_id, payload.partner_id)
        return ActionResult(ok=True, message="Projection created", entry=row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/projections")
def projections(card_id: str | None = None, partner_id: str | None = None) -> dict[str, Any]:
    rows = list_projections(card_id=card_id, partner_id=partner_id)
    return {"items": rows, "total": len(rows)}


@router.post("/shares")
def create_share(payload: SharePayload) -> ActionResult:
    try:
        row = create_shared_snapshot(
            payload.snapshot_id, payload.card_id, payload.partner_id, payload.projection_version
        )
        entry = dict(row)
        entry["share_link"] = f"/api/profile-share/shares/{row['share_id']}/open"
        return ActionResult(ok=True, message="Shared", entry=entry)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/shares")
def shares(snapshot_id: str | None = None, partner_id: str | None = None) -> dict[str, Any]:
    rows = list_shares(snapshot_id=snapshot_id, partner_id=partner_id)
    return {"items": rows, "total": len(rows)}


@router.get("/shares/{share_id}")
def share_detail(share_id: str) -> dict[str, Any]:
    row = get_share(share_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.get("/shares/{share_id}/open")
def open_share(share_id: str, account_id: str) -> dict[str, Any]:
    try:
        return open_shared_snapshot(share_id, account_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
