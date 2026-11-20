"""标签快照服务：消费标签计算和分群结果，生成全量快照。"""
from __future__ import annotations

from typing import Any

from app.store import store


def create_snapshot(snapshot_id: str) -> dict[str, Any]:
    """创建标签快照，消费标签计算和分群结果。"""
    snapshot = store.find_by_field("tag_snapshot", "snapshot_id", snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot not found: {snapshot_id}")

    # 获取所有标签定义
    tags = store.rows("tag_define")
    # 获取所有分群
    segments = store.rows("user_segment")
    # 获取标签计算结果
    compute_results = store.list_artifacts("tag_compute")

    # 计算用户基数（从标签计算结果汇总）
    total_users = 0
    for result in compute_results:
        total_users = max(total_users, result.get("result_count", 0))
    if total_users == 0:
        total_users = 50000  # 默认值

    # 汇总快照数据
    snapshot_data = {
        "snapshot_id": snapshot_id,
        "snapshot_date": snapshot["snapshot_date"],
        "user_count": total_users,
        "tag_count": len(tags),
        "segment_count": len(segments),
        "tags": [{"tag_id": t["tag_id"], "tag_name": t["tag_name"]} for t in tags],
        "segments": [{"segment_id": s["segment_id"], "segment_name": s["segment_name"]} for s in segments],
        "compute_results": [
            {
                "task_id": r.get("task_id"),
                "tag_id": r.get("tag_id"),
                "result_count": r.get("result_count"),
                "compute_scope": r.get("compute_scope"),
            }
            for r in compute_results
        ],
        "snapshot_path": snapshot["snapshot_path"],
        "storage_format": snapshot["storage_format"],
        "shares": _snapshot_shares(snapshot_id),
    }

    # 存储快照产物
    store.set_artifact("tag_snapshot", snapshot_id, snapshot_data)
    store.add_snapshot("tag_snapshot", snapshot_data)

    # 更新快照记录
    store.update("tag_snapshot", snapshot["id"], {
        "status": "已完成",
        "pending": False,
        "user_count": total_users,
        "tag_count": len(tags),
        "segment_count": len(segments),
    })

    return snapshot_data


def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    """获取标签快照，每次读取都挂上当前共享记录（投影版本与共享对象）。"""
    artifact = store.get_artifact("tag_snapshot", snapshot_id)
    if artifact is None:
        try:
            artifact = create_snapshot(snapshot_id)
        except ValueError:
            return None
    artifact["shares"] = _snapshot_shares(snapshot_id)
    return artifact


def _snapshot_shares(snapshot_id: str) -> list[dict[str, Any]]:
    """该快照的共享记录：画像投影数据的版本和共享对象。"""
    shares: list[dict[str, Any]] = []
    for row in store.rows("shared_snapshot"):
        if row.get("snapshot_id") == snapshot_id:
            shares.append({
                "share_id": row.get("share_id"),
                "projection_id": row.get("projection_id"),
                "projection_version": row.get("projection_version"),
                "partner_id": row.get("partner_id"),
                "card_id": row.get("card_id"),
                "status": row.get("status"),
                "created_at": row.get("created_at"),
            })
    return shares


def compare_snapshots(snapshot_id_a: str, snapshot_id_b: str) -> dict[str, Any]:
    """对比两个快照的差异。"""
    snap_a = get_snapshot(snapshot_id_a)
    snap_b = get_snapshot(snapshot_id_b)
    if snap_a is None or snap_b is None:
        raise ValueError("Snapshot not found")

    return {
        "snapshot_a": snapshot_id_a,
        "snapshot_b": snapshot_id_b,
        "user_count_diff": snap_b.get("user_count", 0) - snap_a.get("user_count", 0),
        "tag_count_diff": snap_b.get("tag_count", 0) - snap_a.get("tag_count", 0),
        "segment_count_diff": snap_b.get("segment_count", 0) - snap_a.get("segment_count", 0),
        "date_a": snap_a.get("snapshot_date"),
        "date_b": snap_b.get("snapshot_date"),
    }


def list_snapshots() -> list[dict[str, Any]]:
    """列出所有标签快照。"""
    return store.list_snapshots("tag_snapshot")
