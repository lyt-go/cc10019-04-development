"""画像共享服务：按访问范围裁剪画像投影，管理共享快照与来源分群字段授权。

核心规则：
- 访问范围 = 画像卡片配置的展示标签 ∩ 来源分群当前授权给共享对象的标签字段；
- 画像投影按访问范围裁剪后写入，每次写入产生新版本，历史版本保留可追溯；
- 共享快照保存画像投影数据的版本和共享对象；
- 打开共享快照时按该对象的当前访问范围返回版本内允许的标签值，
  每次打开都重新核对权限与投影，历史链接同样受当前撤权约束。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.store import store
from app.services.profile_card import get_profile_result
from app.services.tag_snapshot import get_snapshot


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tag_name(tag_id: str) -> str:
    tag = store.find_by_field("tag_define", "tag_id", tag_id)
    return tag["tag_name"] if tag else tag_id


def _get_card(card_id: str) -> dict[str, Any]:
    card = store.find_by_field("profile_card", "card_id", card_id)
    if card is None:
        raise ValueError(f"Profile card not found: {card_id}")
    return card


def _get_partner(partner_id: str) -> dict[str, Any]:
    partner = store.find_by_field("partner", "partner_id", partner_id)
    if partner is None:
        raise ValueError(f"Partner not found: {partner_id}")
    return partner


# ========== 账号 ==========
def get_account(account_id: str) -> dict[str, Any] | None:
    """按账号编号查找共享访问账号。"""
    return store.find_by_field("share_account", "account_id", account_id)


def list_accounts() -> list[dict[str, Any]]:
    return store.rows("share_account")


# ========== 来源分群字段授权 ==========
def get_grant(segment_id: str, partner_id: str) -> dict[str, Any] | None:
    """查找来源分群对共享对象的字段授权。"""
    for row in store.rows("field_grant"):
        if row.get("segment_id") == segment_id and row.get("partner_id") == partner_id:
            return row
    return None


def list_grants() -> list[dict[str, Any]]:
    return store.rows("field_grant")


def _change_grant(grant_id: str, fields: list[str], action: str, remark: str | None) -> dict[str, Any]:
    grant = store.find_by_field("field_grant", "grant_id", grant_id)
    if grant is None:
        raise ValueError(f"Grant not found: {grant_id}")
    if not fields:
        raise ValueError("字段列表不能为空")

    allowed = list(grant.get("allowed_tags", []))
    revoked = list(grant.get("revoked_tags", []))
    if action == "grant":
        for f in fields:
            if f not in allowed:
                allowed.append(f)
            if f in revoked:
                revoked.remove(f)
    elif action == "revoke":
        for f in fields:
            if f in allowed:
                allowed.remove(f)
            if f not in revoked:
                revoked.append(f)
    else:
        raise ValueError(f"Unknown grant action: {action}")

    version = int(grant.get("version", 1)) + 1
    history = list(grant.get("history", []))
    history.append({
        "action": action,
        "fields": list(fields),
        "version": version,
        "at": _now(),
        "remark": remark or "",
    })
    store.update("field_grant", grant["id"], {
        "allowed_tags": allowed,
        "revoked_tags": revoked,
        "version": version,
        "history": history,
        "status": "生效中" if allowed else "已撤回",
        "updated_at": _now(),
    })
    return store.find_by_field("field_grant", "grant_id", grant_id)  # type: ignore[return-value]


def grant_fields(grant_id: str, fields: list[str], remark: str | None = None) -> dict[str, Any]:
    """来源分群授予共享对象一批标签字段。"""
    return _change_grant(grant_id, fields, "grant", remark)


def revoke_fields(grant_id: str, fields: list[str], remark: str | None = None) -> dict[str, Any]:
    """来源分群收回共享对象的一批标签字段授权。"""
    return _change_grant(grant_id, fields, "revoke", remark)


# ========== 访问范围 ==========
def get_access_scope(card_id: str, partner_id: str) -> list[str]:
    """访问范围：卡片展示标签 ∩ 来源分群当前授权字段，按卡片配置顺序返回。"""
    card = _get_card(card_id)
    grant = get_grant(card.get("segment_id", ""), partner_id)
    allowed = set(grant.get("allowed_tags", [])) if grant else set()
    return [t for t in card.get("display_tags", []) if t in allowed]


# ========== 画像投影 ==========
def _next_projection_version(card_id: str, partner_id: str) -> int:
    versions = [
        int(row.get("version", 0))
        for row in store.rows("profile_projection")
        if row.get("card_id") == card_id and row.get("partner_id") == partner_id
    ]
    return max(versions, default=0) + 1


def get_projection(card_id: str, partner_id: str, version: int) -> dict[str, Any] | None:
    """获取指定版本的画像投影。"""
    for row in store.rows("profile_projection"):
        if (
            row.get("card_id") == card_id
            and row.get("partner_id") == partner_id
            and int(row.get("version", 0)) == version
        ):
            return row
    return None


def get_latest_projection(card_id: str, partner_id: str) -> dict[str, Any] | None:
    """获取最新版本的画像投影。"""
    candidates = [
        row for row in store.rows("profile_projection")
        if row.get("card_id") == card_id and row.get("partner_id") == partner_id
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: int(r.get("version", 0)))


def list_projections(card_id: str | None = None, partner_id: str | None = None) -> list[dict[str, Any]]:
    rows = store.rows("profile_projection")
    if card_id:
        rows = [r for r in rows if r.get("card_id") == card_id]
    if partner_id:
        rows = [r for r in rows if r.get("partner_id") == partner_id]
    return rows


def create_projection(card_id: str, partner_id: str) -> dict[str, Any]:
    """按访问范围裁剪画像卡片数据并写入画像投影，每次写入产生新版本。"""
    card = _get_card(card_id)
    _get_partner(partner_id)

    scope = get_access_scope(card_id, partner_id)
    if not scope:
        raise ValueError(f"访问范围为空，无法生成画像投影: card={card_id}, partner={partner_id}")

    profile = get_profile_result(card_id)
    if profile is None:
        raise ValueError(f"Profile card result not found: {card_id}")

    # 只保留访问范围内的标签值
    tag_values = [dict(t) for t in profile.get("display_tags", []) if t.get("tag_id") in scope]

    # 分群分布同样按访问范围裁剪，防止越权字段随分布泄漏
    segment_info = profile.get("segment_info")
    if segment_info:
        segment_info = {
            **segment_info,
            "tier_distribution": {
                k: v for k, v in segment_info.get("tier_distribution", {}).items() if k in scope
            },
        }

    grant = get_grant(card.get("segment_id", ""), partner_id)
    version = _next_projection_version(card_id, partner_id)

    row = store.insert("profile_projection", {
        "card_id": card_id,
        "card_name": card.get("card_name", ""),
        "partner_id": partner_id,
        "version": version,
        "scope_tags": scope,
        "tag_values": tag_values,
        "segment_info": segment_info,
        "source_card_version": card.get("version", ""),
        "grant_version": int(grant.get("version", 0)) if grant else 0,
        "status": "已写入",
        "created_at": _now(),
    })
    projection_id = f"PP-{int(row['id']):03d}"
    store.update("profile_projection", int(row["id"]), {"projection_id": projection_id})
    row["projection_id"] = projection_id

    # 同步为数据产物，供跨模块消费
    store.set_artifact("profile_projection", projection_id, dict(row))
    return row


# ========== 共享快照 ==========
def get_share(share_id: str) -> dict[str, Any] | None:
    return store.find_by_field("shared_snapshot", "share_id", share_id)


def list_shares(snapshot_id: str | None = None, partner_id: str | None = None) -> list[dict[str, Any]]:
    rows = store.rows("shared_snapshot")
    if snapshot_id:
        rows = [r for r in rows if r.get("snapshot_id") == snapshot_id]
    if partner_id:
        rows = [r for r in rows if r.get("partner_id") == partner_id]
    return rows


def create_shared_snapshot(
    snapshot_id: str,
    card_id: str,
    partner_id: str,
    projection_version: int | None = None,
) -> dict[str, Any]:
    """创建共享快照：标签快照保存画像投影数据的版本和共享对象。"""
    snapshot = get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot not found: {snapshot_id}")
    _get_card(card_id)
    _get_partner(partner_id)

    if projection_version is None:
        projection = get_latest_projection(card_id, partner_id)
        if projection is None:
            # 共享时按当前访问范围裁剪并写入画像投影
            projection = create_projection(card_id, partner_id)
    else:
        projection = get_projection(card_id, partner_id, projection_version)
        if projection is None:
            raise ValueError(
                f"Projection not found: card={card_id}, partner={partner_id}, version={projection_version}"
            )

    row = store.insert("shared_snapshot", {
        "snapshot_id": snapshot_id,
        "card_id": card_id,
        "partner_id": partner_id,
        "projection_id": projection["projection_id"],
        "projection_version": projection["version"],
        "share_token": f"shk-{uuid.uuid4().hex[:12]}",
        "status": "已共享",
        "opened_count": 0,
        "created_at": _now(),
        "last_opened_at": "",
    })
    share_id = f"SH-{int(row['id']):03d}"
    store.update("shared_snapshot", int(row["id"]), {"share_id": share_id})
    row["share_id"] = share_id
    return row


# ========== 打开共享快照 ==========
def open_shared_snapshot(share_id: str, account_id: str) -> dict[str, Any]:
    """打开共享快照。

    合作方账号：按当前访问范围返回共享版本内允许的标签值，并给出链接状态与
    需要重新交付的范围；维护方账号：回查原始投影版本与共享记录。
    """
    account = get_account(account_id)
    if account is None:
        raise ValueError(f"账号不存在: {account_id}")

    share = get_share(share_id)
    if share is None:
        raise ValueError(f"共享快照不存在: {share_id}")

    card = _get_card(share["card_id"])
    projection = get_projection(share["card_id"], share["partner_id"], int(share["projection_version"]))
    if projection is None:
        raise ValueError(
            f"画像投影版本不存在: {share['projection_id']} v{share['projection_version']}"
        )

    grant = get_grant(card.get("segment_id", ""), share["partner_id"])
    allowed_now = list(grant.get("allowed_tags", [])) if grant else []

    role = account.get("role")
    if role == "partner":
        if account.get("partner_id") != share["partner_id"]:
            raise PermissionError("该合作方账号无权打开此共享链接")
        return _open_as_partner(share, projection, card, allowed_now)
    if role == "maintainer":
        return _open_as_maintainer(share, projection, card, grant, allowed_now)
    raise PermissionError(f"账号角色无权打开共享快照: {role}")


def _open_as_partner(
    share: dict[str, Any],
    projection: dict[str, Any],
    card: dict[str, Any],
    allowed_now: list[str],
) -> dict[str, Any]:
    """合作方视图：只返回获准字段，权限与投影在打开时核对一致。"""
    scope = list(projection.get("scope_tags", []))
    version_values = list(projection.get("tag_values", []))

    # 版本内允许 ∧ 当前仍获准：历史链接同样受当前撤权约束
    visible = [dict(t) for t in version_values if t.get("tag_id") in allowed_now]
    revoked = [t for t in version_values if t.get("tag_id") not in allowed_now]
    pending = [t for t in allowed_now if t not in scope]

    if not visible:
        link_status = "disabled"
    elif revoked:
        link_status = "partial"
    else:
        link_status = "active"

    redelivery_scope: list[dict[str, Any]] = []
    for t in revoked:
        redelivery_scope.append({
            "tag_id": t.get("tag_id"),
            "tag_name": t.get("tag_name", _tag_name(str(t.get("tag_id")))),
            "reason": "字段授权已撤回",
            "action": "如需继续交付，须由来源分群重新授权并生成新投影",
        })
    for tag_id in pending:
        redelivery_scope.append({
            "tag_id": tag_id,
            "tag_name": _tag_name(tag_id),
            "reason": "当前已授权但共享版本未覆盖",
            "action": "需生成新投影版本后重新交付",
        })

    opened_at = _now()
    store.update("shared_snapshot", int(share["id"]), {
        "opened_count": int(share.get("opened_count", 0)) + 1,
        "last_opened_at": opened_at,
    })

    messages = {
        "active": "链接可继续使用，投影与当前授权一致",
        "partial": "链接可继续使用，但部分字段授权已撤回，仅返回仍获准的标签值",
        "disabled": "链接已不可用，共享版本内字段授权均已撤回",
    }
    return {
        "viewer_role": "partner",
        "share_id": share["share_id"],
        "snapshot_id": share["snapshot_id"],
        "card_id": share["card_id"],
        "card_name": card.get("card_name", ""),
        "partner_id": share["partner_id"],
        "projection_id": projection["projection_id"],
        "projection_version": projection["version"],
        "link_status": link_status,
        "tags": visible,
        "revoked_fields": [
            {"tag_id": t.get("tag_id"), "tag_name": t.get("tag_name", _tag_name(str(t.get("tag_id"))))}
            for t in revoked
        ],
        "redelivery_scope": redelivery_scope,
        "opened_at": opened_at,
        "message": messages[link_status],
    }


def _open_as_maintainer(
    share: dict[str, Any],
    projection: dict[str, Any],
    card: dict[str, Any],
    grant: dict[str, Any] | None,
    allowed_now: list[str],
) -> dict[str, Any]:
    """维护方视图：复查发给合作方的画像稿，原始版本与共享记录可追溯。"""
    partner = store.find_by_field("partner", "partner_id", share["partner_id"])
    return {
        "viewer_role": "maintainer",
        "share_id": share["share_id"],
        "snapshot_id": share["snapshot_id"],
        "card_id": share["card_id"],
        "card_name": card.get("card_name", ""),
        "partner_id": share["partner_id"],
        "partner_name": partner.get("partner_name", "") if partner else "",
        "projection_id": projection["projection_id"],
        "projection_version": projection["version"],
        # 原始投影版本：共享时点发给对方的画像稿，不受后续撤权影响
        "original_projection": {
            "scope_tags": list(projection.get("scope_tags", [])),
            "tag_values": [dict(t) for t in projection.get("tag_values", [])],
            "segment_info": projection.get("segment_info"),
            "source_card_version": projection.get("source_card_version", ""),
            "grant_version": projection.get("grant_version", 0),
            "created_at": projection.get("created_at", ""),
        },
        # 共享记录与当前授权对照
        "share_record": dict(share),
        "current_allowed_tags": allowed_now,
        "grant_history": list(grant.get("history", [])) if grant else [],
        "snapshot_shares": [dict(s) for s in list_shares(snapshot_id=share["snapshot_id"])],
    }
