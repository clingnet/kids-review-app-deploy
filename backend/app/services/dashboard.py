"""首页仪表盘聚合(纯 DB 计算,不调模型)。"""
from __future__ import annotations

from .. import db


def overall_mastery() -> float:
    kps = db.list_kp()
    if not kps:
        return 0.0
    return round(sum(k.get("mastery") or 0 for k in kps) / len(kps), 3)


def subjects_mastery() -> list[dict]:
    agg: dict[str, list[float]] = {}
    for k in db.list_kp():
        agg.setdefault(k.get("subject") or "其它", []).append(k.get("mastery") or 0)
    return [{"subject": s, "mastery": round(sum(v) / len(v), 3)}
            for s, v in agg.items()]


# 薄弱点口径:掌握度低于此阈值的知识点(与知识图谱红色节点一致),保证首页计数与图谱一致
WEAK_THRESHOLD = 0.6


def weak_points_list() -> list[dict]:
    """统一口径:掌握度 < 阈值的知识点;并合并 AI 总结的"why"。"""
    detail = {w["knowledge_point"]: w for w in db.list_weak_points()}
    weak = [k for k in db.list_kp() if (k.get("mastery") or 0) < WEAK_THRESHOLD]
    weak.sort(key=lambda x: x.get("mastery") or 0)
    return [{"knowledge_point": k["name"], "subject": k.get("subject"),
             "mastery": k.get("mastery"),
             "why": (detail.get(k["name"]) or {}).get("why"),
             "typical_errors": (detail.get(k["name"]) or {}).get("typical_errors", [])}
            for k in weak]


def build() -> dict:
    weak = weak_points_list()
    qs = db.all_questions()
    snaps = db.list_snapshots(7)
    materials = db.list_materials()
    recent = []
    for m in materials[:5]:
        recent.append({"type": "upload",
                       "text": f"上传素材 #{m['id']} · {m.get('subject') or ''}",
                       "time": m.get("uploaded_at")})
    return {
        "overall_mastery": overall_mastery(),
        "subjects": subjects_mastery(),
        "weak_points": weak,
        "streak_days": len(snaps),          # 简化:有掌握度快照的天数
        "trend": [{"date": s["day"], "mastery": s["overall"]} for s in snaps],
        "recent": recent,
        "counts": {"questions": len(qs), "weak": len(weak),
                   "wrong": len(db.wrong_questions())},
    }
