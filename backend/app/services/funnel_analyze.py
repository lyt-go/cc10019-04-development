"""漏斗分析引擎：计算用户转化漏斗的步骤转化率，支持分组维度。"""
from __future__ import annotations

from typing import Any
from collections import defaultdict

from app.store import store
from app.schemas import FunnelResult


def _generate_event_data(event_id: str, count: int) -> list[dict[str, Any]]:
    """生成模拟事件数据用于漏斗计算。"""
    events = []
    for i in range(1, count + 1):
        user_id = f"U{i:05d}"
        # 模拟漏斗流失：每一步只有前一步的一部分用户继续
        if event_id == "EV-001":  # 页面浏览
            events.append({
                "user_id": user_id,
                "event_id": event_id,
                "timestamp": 1700000000 + i * 100,
                "ATTR-001": ["app", "web", "miniapp", "h5"][i % 4],
                "ATTR-005": ["普通", "银卡", "金卡", "钻石"][i % 4],
            })
        elif event_id == "EV-002":  # 商品点击 - 60% 转化
            if i <= int(count * 0.6):
                events.append({
                    "user_id": user_id,
                    "event_id": event_id,
                    "timestamp": 1700000100 + i * 100,
                    "ATTR-001": ["app", "web", "miniapp", "h5"][i % 4],
                    "ATTR-005": ["普通", "银卡", "金卡", "钻石"][i % 4],
                })
        elif event_id == "EV-003":  # 下单成功 - 30% 转化
            if i <= int(count * 0.3):
                events.append({
                    "user_id": user_id,
                    "event_id": event_id,
                    "timestamp": 1700000200 + i * 100,
                    "ATTR-001": ["app", "web", "miniapp", "h5"][i % 4],
                    "ATTR-005": ["普通", "银卡", "金卡", "钻石"][i % 4],
                })
        elif event_id == "EV-004":  # 支付完成 - 25% 转化
            if i <= int(count * 0.25):
                events.append({
                    "user_id": user_id,
                    "event_id": event_id,
                    "timestamp": 1700000300 + i * 100,
                    "ATTR-001": ["app", "web", "miniapp", "h5"][i % 4],
                    "ATTR-005": ["普通", "银卡", "金卡", "钻石"][i % 4],
                })
    return events


def analyze_funnel(funnel_id: str) -> FunnelResult:
    """执行漏斗分析。"""
    funnel = store.find_by_field("funnel_analyze", "funnel_id", funnel_id)
    if funnel is None:
        raise ValueError(f"Funnel not found: {funnel_id}")

    step_events = funnel["step_events"]
    group_dim = funnel.get("group_dimension", "")
    conversion_window = funnel.get("conversion_window", 86400)
    step_window = funnel.get("step_window", 3600)

    # 获取每一步的事件数据
    all_events: list[dict[str, Any]] = []
    for event_id in step_events:
        events = _generate_event_data(event_id, 1000)
        all_events.extend(events)

    # 按用户分组并排序
    user_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in all_events:
        user_events[e["user_id"]].append(e)

    for uid in user_events:
        user_events[uid].sort(key=lambda x: x["timestamp"])

    # 计算漏斗转化
    step_counts = []
    step_rates = []
    group_results: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # 第一步：所有触发用户
    step1_users = set()
    for e in all_events:
        if e["event_id"] == step_events[0]:
            step1_users.add(e["user_id"])
    step_counts.append(len(step1_users))
    step_rates.append(1.0)

    # 后续步骤：上一步用户在窗口内触发
    prev_users = step1_users
    for i in range(1, len(step_events)):
        curr_users = set()
        for uid in prev_users:
            user_evts = user_events[uid]
            # 找到上一步的事件时间
            prev_time = None
            for ev in user_evts:
                if ev["event_id"] == step_events[i - 1]:
                    prev_time = ev["timestamp"]
                    break
            if prev_time is None:
                continue
            # 检查当前步骤是否在窗口内
            for ev in user_evts:
                if ev["event_id"] == step_events[i]:
                    if step_window > 0:
                        if prev_time < ev["timestamp"] <= prev_time + step_window:
                            curr_users.add(uid)
                            break
                    else:
                        if prev_time < ev["timestamp"] <= prev_time + conversion_window:
                            curr_users.add(uid)
                            break
        step_counts.append(len(curr_users))
        rate = len(curr_users) / len(step1_users) if step1_users else 0.0
        step_rates.append(round(rate, 4))
        prev_users = curr_users

    # 分组统计
    if group_dim:
        for event_id in step_events:
            events = _generate_event_data(event_id, 1000)
            dim_counts: dict[str, int] = defaultdict(int)
            seen = set()
            for e in events:
                key = e.get(group_dim, "unknown")
                if (e["user_id"], key) not in seen:
                    dim_counts[key] += 1
                    seen.add((e["user_id"], key))
            for dim_val, cnt in sorted(dim_counts.items()):
                group_results[group_dim].append({
                    "event_id": event_id,
                    "group_value": dim_val,
                    "count": cnt,
                })

    total_rate = step_rates[-1] if step_rates else 0.0

    result = FunnelResult(
        funnel_id=funnel_id,
        funnel_name=funnel["funnel_name"],
        step_events=step_events,
        step_counts=step_counts,
        step_rates=step_rates,
        total_conversion_rate=total_rate,
        group_results=dict(group_results),
    )

    # 存储产物
    store.set_artifact("funnel_analyze", funnel_id, result.model_dump())

    # 更新状态
    store.update("funnel_analyze", funnel["id"], {
        "status": "已完成",
        "pending": False,
    })

    return result


def get_funnel_result(funnel_id: str) -> dict[str, Any] | None:
    """获取漏斗分析结果。"""
    artifact = store.get_artifact("funnel_analyze", funnel_id)
    if artifact:
        return artifact
    try:
        result = analyze_funnel(funnel_id)
        return result.model_dump()
    except ValueError:
        return None


def compare_funnels(funnel_id_a: str, funnel_id_b: str) -> dict[str, Any]:
    """对比两个漏斗的转化情况。"""
    result_a = get_funnel_result(funnel_id_a)
    result_b = get_funnel_result(funnel_id_b)
    if result_a is None or result_b is None:
        raise ValueError("Funnel result not found")

    return {
        "funnel_a": result_a["funnel_id"],
        "funnel_b": result_b["funnel_id"],
        "step_comparison": [
            {
                "step": i,
                "count_a": result_a["step_counts"][i] if i < len(result_a["step_counts"]) else 0,
                "count_b": result_b["step_counts"][i] if i < len(result_b["step_counts"]) else 0,
                "rate_a": result_a["step_rates"][i] if i < len(result_a["step_rates"]) else 0,
                "rate_b": result_b["step_rates"][i] if i < len(result_b["step_rates"]) else 0,
            }
            for i in range(max(len(result_a["step_counts"]), len(result_b["step_counts"])))
        ],
        "total_rate_diff": result_a["total_conversion_rate"] - result_b["total_conversion_rate"],
    }
