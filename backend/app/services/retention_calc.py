"""留存计算引擎：计算用户留存率，支持按维度分段。"""
from __future__ import annotations

from typing import Any
from collections import defaultdict

from app.store import store
from app.schemas import RetentionResult


def _generate_retention_events(event_id: str, base_date: str, days: int) -> list[dict[str, Any]]:
    """生成留存分析所需的模拟事件数据。"""
    events = []
    import datetime
    base = datetime.datetime.strptime(base_date, "%Y-%m-%d")
    base_ts = int(base.timestamp())

    for day in range(days):
        # 每天的用户数递减模拟留存
        num_users = max(1000 - day * 80, 200)
        for user_idx in range(1, num_users + 1):
            user_id = f"U{user_idx:05d}"
            # 用户在不同维度上的分布
            attr_001 = ["app", "web", "miniapp", "h5"][user_idx % 4]
            attr_005 = ["普通", "银卡", "金卡", "钻石"][user_idx % 4]
            events.append({
                "user_id": user_id,
                "event_id": event_id,
                "timestamp": base_ts + day * 86400 + (user_idx % 3600),
                "ATTR-001": attr_001,
                "ATTR-005": attr_005,
                "date": (base + datetime.timedelta(days=day)).strftime("%Y-%m-%d"),
            })
    return events


def calculate_retention(config_id: str) -> RetentionResult:
    """执行留存计算。"""
    config = store.find_by_field("retention_calc", "config_id", config_id)
    if config is None:
        raise ValueError(f"Retention config not found: {config_id}")

    init_event = config["init_event"]
    return_event = config["return_event"]
    calc_period = config.get("calc_period", "day")
    segment_dim = config.get("segment_dim", "")
    base_date = config["base_date"]
    retention_window = config.get("retention_window", 30)

    # 生成事件数据
    events = _generate_retention_events(init_event, base_date, retention_window)

    # 按日期和用户分组
    date_users: dict[str, set[str]] = defaultdict(set)
    dim_date_users: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for e in events:
        date_users[e["date"]].add(e["user_id"])
        if segment_dim:
            dim_val = e.get(segment_dim, "unknown")
            dim_date_users[dim_val][e["date"]].add(e["user_id"])

    # 计算留存率
    cohort_sizes: dict[str, int] = {}
    retention_rates: dict[str, list[float]] = {}

    # 基准日期的用户作为初始队列
    init_date = base_date
    init_users = date_users.get(init_date, set())
    cohort_sizes[init_date] = len(init_users)
    retention_rates[init_date] = []

    for day in range(retention_window):
        target_date = _add_days(base_date, day)
        target_users = date_users.get(target_date, set())
        retained = init_users & target_users
        rate = len(retained) / len(init_users) if init_users else 0.0
        retention_rates[init_date].append(round(rate, 4))

    # 按维度分段
    if segment_dim:
        for dim_val, dim_data in dim_date_users.items():
            dim_init_users = dim_data.get(init_date, set())
            key = f"{segment_dim}:{dim_val}"
            cohort_sizes[key] = len(dim_init_users)
            retention_rates[key] = []
            for day in range(retention_window):
                target_date = _add_days(base_date, day)
                target_users = dim_data.get(target_date, set())
                retained = dim_init_users & target_users
                rate = len(retained) / len(dim_init_users) if dim_init_users else 0.0
                retention_rates[key].append(round(rate, 4))

    result = RetentionResult(
        config_id=config_id,
        init_event=init_event,
        return_event=return_event,
        base_date=base_date,
        cohort_sizes=cohort_sizes,
        retention_rates=retention_rates,
        result_table=config.get("result_table", ""),
    )

    # 存储产物
    store.set_artifact("retention_calc", config_id, result.model_dump())

    # 更新状态
    store.update("retention_calc", config["id"], {
        "status": "已完成",
        "pending": False,
    })

    return result


def _add_days(date_str: str, days: int) -> str:
    """日期加减。"""
    import datetime
    d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return (d + datetime.timedelta(days=days)).strftime("%Y-%m-%d")


def get_retention_result(config_id: str) -> dict[str, Any] | None:
    """获取留存计算结果。"""
    artifact = store.get_artifact("retention_calc", config_id)
    if artifact:
        return artifact
    try:
        result = calculate_retention(config_id)
        return result.model_dump()
    except ValueError:
        return None
