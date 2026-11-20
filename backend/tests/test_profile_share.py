"""画像共享链路测试：访问范围裁剪、投影版本、共享快照与撤权约束。

场景还原：原卡片（PC-003）有会员等级（TAG-005）和消费档位（TAG-006），
来源分群 SEG-001 授权合作方 PTN-001 两个字段；共享投影后收回等级授权，
消费档位仍可分享。合作方持原链接打开时核对版本来源、链接可用性与
重新交付范围；维护方回查原快照时原始版本与共享记录仍可追溯。
"""
from __future__ import annotations

import unittest

# 设置路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.store import store
from app.services.tag_compute import compute_tag
from app.services.user_segment import compute_segment
from app.services.profile_card import build_profile_card
from app.services.tag_snapshot import get_snapshot
from app.services.profile_share import (
    create_projection,
    create_shared_snapshot,
    get_access_scope,
    get_latest_projection,
    get_projection,
    grant_fields,
    list_projections,
    list_shares,
    open_shared_snapshot,
    revoke_fields,
)

CARD_ID = "PC-003"
PARTNER = "PTN-001"
PARTNER_ACCOUNT = "ACC-PTN-001"
OTHER_PARTNER_ACCOUNT = "ACC-PTN-002"
MAINTAINER_ACCOUNT = "ACC-OPS-001"
SNAPSHOT_ID = "SN-003"
GRANT_ID = "FG-001"
TAG_LEVEL = "TAG-005"  # 会员等级
TAG_TIER = "TAG-006"  # 消费档位


class TestProfileShare(unittest.TestCase):
    """画像共享：投影裁剪、共享快照与撤权约束。"""

    def setUp(self) -> None:
        """重置共享相关状态，并准备卡片计算产物。"""
        store._artifacts.clear()
        store._compute_cache.clear()
        store._snapshots.clear()
        store._tables["profile_projection"].clear()
        store._tables["shared_snapshot"].clear()
        store._next_ids["profile_projection"] = 1
        store._next_ids["shared_snapshot"] = 1
        # 还原来源分群授权：等级 + 消费档位
        store.update("field_grant", 1, {
            "allowed_tags": [TAG_LEVEL, TAG_TIER],
            "revoked_tags": [],
            "version": 1,
            "history": [],
            "status": "生效中",
        })
        # 准备画像卡片数据
        compute_tag("TC-005")
        compute_tag("TC-006")
        compute_segment("SEG-001")
        build_profile_card(CARD_ID)

    # ---------- 基础能力 ----------
    def test_access_scope_intersects_card_tags_and_grant(self) -> None:
        """访问范围 = 卡片展示标签 ∩ 来源分群授权字段。"""
        scope = get_access_scope(CARD_ID, PARTNER)
        self.assertEqual(scope, [TAG_LEVEL, TAG_TIER])
        # 合作方B只获准消费档位
        scope_b = get_access_scope(CARD_ID, "PTN-002")
        self.assertEqual(scope_b, [TAG_TIER])

    def test_projection_crops_by_access_scope_and_versions(self) -> None:
        """按访问范围裁剪并写入画像投影，每次写入产生新版本。"""
        proj = create_projection(CARD_ID, PARTNER)
        self.assertEqual(proj["version"], 1)
        self.assertEqual(proj["scope_tags"], [TAG_LEVEL, TAG_TIER])
        tag_ids = [t["tag_id"] for t in proj["tag_values"]]
        self.assertEqual(tag_ids, [TAG_LEVEL, TAG_TIER])
        # 分群分布同样被裁剪到访问范围内
        tier_keys = set((proj.get("segment_info") or {}).get("tier_distribution", {}))
        self.assertTrue(tier_keys <= {TAG_LEVEL, TAG_TIER})

        proj2 = create_projection(CARD_ID, PARTNER)
        self.assertEqual(proj2["version"], 2)
        # 历史版本保留可追溯
        self.assertIsNotNone(get_projection(CARD_ID, PARTNER, 1))
        self.assertEqual(get_latest_projection(CARD_ID, PARTNER)["version"], 2)
        self.assertEqual(len(list_projections(card_id=CARD_ID, partner_id=PARTNER)), 2)

    def test_projection_blocked_when_scope_empty(self) -> None:
        """访问范围为空时无法生成画像投影。"""
        revoke_fields(GRANT_ID, [TAG_LEVEL, TAG_TIER])
        with self.assertRaises(ValueError):
            create_projection(CARD_ID, PARTNER)

    def test_share_snapshot_records_projection_version_and_partner(self) -> None:
        """标签快照保存画像投影数据的版本和共享对象。"""
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        self.assertEqual(share["projection_version"], 1)
        self.assertEqual(share["partner_id"], PARTNER)
        self.assertEqual(share["snapshot_id"], SNAPSHOT_ID)
        # 快照结果中可追溯共享记录
        snapshot = get_snapshot(SNAPSHOT_ID)
        self.assertIsNotNone(snapshot)
        shares = snapshot["shares"]
        self.assertEqual(len(shares), 1)
        self.assertEqual(shares[0]["projection_version"], 1)
        self.assertEqual(shares[0]["partner_id"], PARTNER)

    # ---------- 核心场景：部分撤权 ----------
    def test_partial_revocation_partner_opens_old_link(self) -> None:
        """收回等级授权后，合作方开旧链接：档位取自共享版本，链接部分可用。"""
        proj = create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)

        # 撤权前：合作方可看到等级 + 消费档位
        before = open_shared_snapshot(share["share_id"], PARTNER_ACCOUNT)
        self.assertEqual(before["link_status"], "active")
        self.assertEqual([t["tag_id"] for t in before["tags"]], [TAG_LEVEL, TAG_TIER])

        # 来源分群收回等级授权，消费档位仍可分享
        grant = revoke_fields(GRANT_ID, [TAG_LEVEL])
        self.assertEqual(grant["allowed_tags"], [TAG_TIER])

        # 合作方账号打开旧链接
        view = open_shared_snapshot(share["share_id"], PARTNER_ACCOUNT)
        # 档位从共享版本 v1 取得
        self.assertEqual(view["projection_version"], proj["version"])
        self.assertEqual(view["projection_id"], proj["projection_id"])
        # 只返回仍获准的消费档位，等级不出现在结果中（权限与投影一致）
        self.assertEqual([t["tag_id"] for t in view["tags"]], [TAG_TIER])
        self.assertNotIn(TAG_LEVEL, [t["tag_id"] for t in view["tags"]])
        # 档位值与共享版本内保存的一致
        proj_tier = next(t for t in proj["tag_values"] if t["tag_id"] == TAG_TIER)
        view_tier = view["tags"][0]
        self.assertEqual(view_tier, proj_tier)
        # 链接可继续使用（部分字段被撤）
        self.assertEqual(view["link_status"], "partial")
        # 需要重新交付的范围：被撤回的等级
        redeliver_ids = [r["tag_id"] for r in view["redelivery_scope"]]
        self.assertEqual(redeliver_ids, [TAG_LEVEL])
        self.assertEqual(view["revoked_fields"][0]["tag_id"], TAG_LEVEL)

    def test_maintainer_traces_original_snapshot(self) -> None:
        """维护方回查原快照：原始版本画像稿与共享记录仍可追溯。"""
        proj = create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        revoke_fields(GRANT_ID, [TAG_LEVEL])

        view = open_shared_snapshot(share["share_id"], MAINTAINER_ACCOUNT)
        self.assertEqual(view["viewer_role"], "maintainer")
        # 原始投影版本仍是共享时点的画像稿（等级 + 消费档位）
        original = view["original_projection"]
        self.assertEqual(original["scope_tags"], [TAG_LEVEL, TAG_TIER])
        self.assertEqual(
            [t["tag_id"] for t in original["tag_values"]],
            [t["tag_id"] for t in proj["tag_values"]],
        )
        # 共享记录可追溯
        self.assertEqual(view["share_record"]["share_id"], share["share_id"])
        self.assertEqual(view["share_record"]["projection_version"], 1)
        self.assertEqual(len(view["snapshot_shares"]), 1)
        # 当前授权与变更历史可对照
        self.assertEqual(view["current_allowed_tags"], [TAG_TIER])
        self.assertEqual(view["grant_history"][-1]["action"], "revoke")
        self.assertEqual(view["grant_history"][-1]["fields"], [TAG_LEVEL])

    def test_full_revocation_disables_link(self) -> None:
        """全部字段撤权后，历史链接不可用且不再返回任何标签值。"""
        create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        revoke_fields(GRANT_ID, [TAG_LEVEL, TAG_TIER])

        view = open_shared_snapshot(share["share_id"], PARTNER_ACCOUNT)
        self.assertEqual(view["link_status"], "disabled")
        self.assertEqual(view["tags"], [])
        self.assertEqual(len(view["redelivery_scope"]), 2)

    def test_regrant_and_reprojection_redelivers(self) -> None:
        """重新授权后生成新投影交付，旧链接仍受原版本约束。"""
        create_projection(CARD_ID, PARTNER)
        share_v1 = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        revoke_fields(GRANT_ID, [TAG_LEVEL])

        # 撤权期间生成的投影只含消费档位
        proj_v2 = create_projection(CARD_ID, PARTNER)
        self.assertEqual(proj_v2["version"], 2)
        self.assertEqual([t["tag_id"] for t in proj_v2["tag_values"]], [TAG_TIER])

        # 重新授权等级并生成 v3 重新交付
        grant_fields(GRANT_ID, [TAG_LEVEL])
        proj_v3 = create_projection(CARD_ID, PARTNER)
        self.assertEqual(proj_v3["version"], 3)
        self.assertEqual([t["tag_id"] for t in proj_v3["tag_values"]], [TAG_LEVEL, TAG_TIER])
        share_v3 = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        self.assertEqual(share_v3["projection_version"], 3)

        # 旧链接仍指向 v1，按当前权限返回（等级已恢复，v1 内含等级）
        old_view = open_shared_snapshot(share_v1["share_id"], PARTNER_ACCOUNT)
        self.assertEqual(old_view["projection_version"], 1)
        self.assertEqual(old_view["link_status"], "active")
        # 新链接返回 v3 全量字段
        new_view = open_shared_snapshot(share_v3["share_id"], PARTNER_ACCOUNT)
        self.assertEqual(new_view["projection_version"], 3)
        self.assertEqual([t["tag_id"] for t in new_view["tags"]], [TAG_LEVEL, TAG_TIER])

    # ---------- 访问控制 ----------
    def test_partner_cannot_open_other_partners_link(self) -> None:
        """合作方账号只能打开发给自己的共享链接。"""
        create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        with self.assertRaises(PermissionError):
            open_shared_snapshot(share["share_id"], OTHER_PARTNER_ACCOUNT)

    def test_unknown_account_rejected(self) -> None:
        create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        with self.assertRaises(ValueError):
            open_shared_snapshot(share["share_id"], "ACC-NOBODY")

    def test_open_records_trace(self) -> None:
        """每次打开都留痕，维护方可在共享记录中看到。"""
        create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        open_shared_snapshot(share["share_id"], PARTNER_ACCOUNT)
        open_shared_snapshot(share["share_id"], PARTNER_ACCOUNT)
        view = open_shared_snapshot(share["share_id"], MAINTAINER_ACCOUNT)
        self.assertEqual(view["share_record"]["opened_count"], 2)
        self.assertTrue(view["share_record"]["last_opened_at"])

    def test_pending_scope_listed_for_redelivery(self) -> None:
        """共享版本未覆盖的新授权字段列入重新交付范围。"""
        create_projection(CARD_ID, PARTNER)
        share = create_shared_snapshot(SNAPSHOT_ID, CARD_ID, PARTNER)
        # 共享后又新授权了标签（投影 v1 未覆盖）
        # 先把 TAG-001 授权给该合作方
        grant_fields(GRANT_ID, ["TAG-001"])
        view = open_shared_snapshot(share["share_id"], PARTNER_ACCOUNT)
        pending = [r["tag_id"] for r in view["redelivery_scope"]]
        self.assertIn("TAG-001", pending)
        # 但新授权字段不会出现在旧版本返回的标签值里
        self.assertNotIn("TAG-001", [t["tag_id"] for t in view["tags"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
