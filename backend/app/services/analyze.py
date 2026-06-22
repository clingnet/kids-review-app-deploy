"""分析服务：全局知识点分析 + 薄弱点自动总结，并落库（驱动知识树/薄弱点中心）。"""
from __future__ import annotations

import json
import logging

from .. import db
from ..llm import get_llm, mock, prompts

log = logging.getLogger("analyze")


def run_global_analysis() -> dict:
    """基于已提取的所有题目，做全局知识点分析，落 knowledge_points + relations。"""
    questions = db.all_questions()
    if not questions:
        return {"summary": "还没有题目数据，请先上传并分析试卷。",
                "knowledge_points": [], "relations": []}

    payload = json.dumps(
        [{"stem": q["stem"], "is_correct": q["is_correct"],
          "knowledge_points": q["knowledge_points"], "error_type": q["error_type"]}
         for q in questions], ensure_ascii=False)

    result = get_llm().run(
        role="reason",
        system=prompts.GLOBAL_ANALYSIS_SYSTEM,
        user=prompts.GLOBAL_ANALYSIS_USER.format(data=payload),
        json_mode=True,
        mock_fn=mock.global_analysis,
    )

    for kp in result.get("knowledge_points", []):
        db.upsert_kp(kp)
    for rel in result.get("relations", []):
        db.upsert_relation(rel.get("from"), rel.get("to"), rel.get("type"))
    log.info("全局分析完成，知识点 %d 个", len(result.get("knowledge_points", [])))
    return result


def run_weak_points() -> dict:
    """基于错题 + 掌握度，自动总结薄弱点，落 weak_points 表。"""
    wrong = db.wrong_questions()
    kps = db.list_kp()
    payload = json.dumps(
        {"wrong_questions": [
            {"stem": q["stem"], "child_answer": q["child_answer"],
             "knowledge_points": q["knowledge_points"], "error_type": q["error_type"]}
            for q in wrong],
         "knowledge_points": kps}, ensure_ascii=False)

    result = get_llm().run(
        role="reason",
        system=prompts.WEAK_POINTS_SYSTEM,
        user=prompts.WEAK_POINTS_USER.format(data=payload),
        json_mode=True,
        mock_fn=mock.weak_points,
    )
    db.replace_weak_points(result.get("weak_points", []))
    log.info("薄弱点总结完成，共 %d 个", len(result.get("weak_points", [])))
    return result


def explain_weak_point(kp: str, errors: list[str] | None = None,
                       refresh: bool = False) -> dict:
    """针对一个薄弱点的讲解 + 练习题。**带缓存**:
    - 默认优先返回缓存讲解 + 题库练习(秒回,不调 AI);
    - refresh=True 才重新调 AI 生成,并存入缓存/题库。"""
    cached = db.get_kp_content(kp)
    if not refresh and cached and cached.get("explanation"):
        bank = db.bank_by_kp(kp, limit=3)
        practice = [{"stem": b["stem"], "answer": b["answer"],
                     "explanation": b["explanation"]} for b in bank[:3]]
        return {"knowledge_point": kp, "explanation": cached["explanation"],
                "worked_example": cached.get("worked_example", ""),
                "practice": practice, "cached": True}

    errs = "、".join(errors or []) or "（无具体记录）"
    res = get_llm().run(
        role="reason",
        system=prompts.EXPLAIN_SYSTEM,
        user=prompts.EXPLAIN_USER.format(kp=kp, errors=errs),
        json_mode=True,
        mock_fn=mock.explain_and_practice,
    )
    # 讲解存缓存,练习入题库
    db.upsert_kp_content(kp, explanation=res.get("explanation"),
                         worked_example=res.get("worked_example"))
    db.add_bank_questions([{
        "stem": p.get("stem"), "answer": p.get("answer"),
        "explanation": p.get("explanation"), "type": "练习",
        "options": [], "knowledge_points": [kp]}
        for p in res.get("practice", [])])
    res["cached"] = False
    return res
