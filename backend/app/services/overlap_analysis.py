"""交集分析服务：计算两个人群的交集、并集或差集。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.crowd_select import get_crowd_result


def analyze_overlap(task_id: str) -> dict[str, Any]:
    """执行交集分析，消费圈选结果。"""
    task = store.find_by_field("overlap_analysis", "task_id", task_id)
    if task is None:
        raise ValueError(f"Overlap task not found: {task_id}")

    crowd_a_id = task["crowd_a"]
    crowd_b_id = task["crowd_b"]
    intersect_mode = task["intersect_mode"]
    analysis_dims = task.get("analysis_dims", [])

    # 获取两个人群的圈选结果
    crowd_a = get_crowd_result(crowd_a_id)
    crowd_b = get_crowd_result(crowd_b_id)

    if crowd_a is None or crowd_b is None:
        raise ValueError("Crowd result not found")

    users_a = set(crowd_a.get("matched_users", []))
    users_b = set(crowd_b.get("matched_users", []))

    # 计算交集模式
    if intersect_mode == "intersect":
        result_users = users_a & users_b
    elif intersect_mode == "union":
        result_users = users_a | users_b
    elif intersect_mode == "diff":
        result_users = users_a - users_b
    elif intersect_mode == "a_only":
        result_users = users_a - users_b
    elif intersect_mode == "b_only":
        result_users = users_b - users_a
    else:
        result_users = users_a & users_b

    # 维度分析
    dim_stats: dict[str, dict[str, int]] = {}
    for dim in analysis_dims:
        dim_stats[dim] = {}
        # 模拟维度分布
        for user in result_users:
            val = f"{dim}_val_{hash(user) % 5}"
            dim_stats[dim][val] = dim_stats[dim].get(val, 0) + 1

    result = {
        "task_id": task_id,
        "crowd_a": crowd_a_id,
        "crowd_b": crowd_b_id,
        "intersect_mode": intersect_mode,
        "users_a_count": len(users_a),
        "users_b_count": len(users_b),
        "result_count": len(result_users),
        "intersection_rate": len(users_a & users_b) / len(users_a) if users_a else 0.0,
        "dim_stats": dim_stats,
        "result_table": task.get("result_table", ""),
    }

    # 存储产物
    store.set_artifact("overlap_analysis", task_id, result)

    # 更新状态
    store.update("overlap_analysis", task["id"], {
        "status": "已完成",
        "pending": False,
    })

    return result


def get_overlap_result(task_id: str) -> dict[str, Any] | None:
    """获取交集分析结果。"""
    artifact = store.get_artifact("overlap_analysis", task_id)
    if artifact:
        return artifact
    try:
        return analyze_overlap(task_id)
    except ValueError:
        return None
