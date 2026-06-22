"""自我练习:按范围出题 + 提交判分 + 错题入本。"""
from __future__ import annotations

from .. import db
from ..llm import get_llm, mock, prompts


def _scope_desc(scope: str, value: str | None) -> str:
    if scope == "kp" and value:
        return f"知识点「{value}」"
    if scope == "weak":
        names = [w["knowledge_point"] for w in db.list_weak_points()][:5]
        return "孩子的薄弱点:" + ("、".join(names) or "(暂无,任选基础知识点)")
    if scope == "wrongbook":
        kps = []
        for w in db.list_wrongbook():
            kps += w["question"].get("knowledge_points", [])
        return "孩子错题涉及的知识点:" + ("、".join(sorted(set(kps))[:6]) or "(暂无)")
    if scope == "subject" and value:
        return f"{value}学科的常见知识点"
    return "五年级常见知识点"


def _bank_for_scope(scope: str, value: str | None) -> list[dict]:
    if scope == "kp" and value:
        return db.bank_by_kp(value, 30)
    if scope == "subject" and value:
        return db.bank_by_subject(value, 50)
    if scope == "weak":
        out = []
        for w in db.list_weak_points():
            out += db.bank_by_kp(w["knowledge_point"], 10)
        return out
    if scope == "wrongbook":
        kps = set()
        for w in db.list_wrongbook():
            kps.update(w["question"].get("knowledge_points", []))
        out = []
        for k in kps:
            out += db.bank_by_kp(k, 10)
        return out
    return db.bank_all(100)


def _bank_to_q(rows: list[dict]) -> list[dict]:
    return [{"type": r.get("type"), "stem": r.get("stem"),
             "options": r.get("options", []), "answer": r.get("answer"),
             "explanation": r.get("explanation"),
             "knowledge_points": r.get("knowledge_points", [])} for r in rows]


def generate(scope: str, value: str | None = None, count: int = 5,
             refresh: bool = False) -> dict:
    """出题:**优先从题库选**(快);不够或 refresh 时才调 AI 生成,并把新题存入题库。"""
    from_bank = []
    if not refresh:
        import random
        bank = _bank_for_scope(scope, value)
        # 去重(按题干)
        seen, uniq = set(), []
        for r in bank:
            if r.get("stem") and r["stem"] not in seen:
                seen.add(r["stem"]); uniq.append(r)
        if len(uniq) >= count:
            picked = random.sample(uniq, count)
            qs = _bank_to_q(picked)
            for i, q in enumerate(qs):
                q["id"] = i + 1
            return {"questions": qs, "from_bank": True}
        from_bank = uniq

    need = max(1, count - len(from_bank))
    desc = _scope_desc(scope, value)
    res = get_llm().run(
        role="reason",
        system=prompts.PRACTICE_SYSTEM,
        user=prompts.PRACTICE_USER.format(desc=desc, count=need),
        json_mode=True,
        mock_fn=mock.practice,
    )
    new_qs = res.get("questions", [])
    # 新题打知识点标签 + 入库
    kp_tag = [value] if (scope == "kp" and value) else []
    for q in new_qs:
        if not q.get("knowledge_points"):
            q["knowledge_points"] = kp_tag
    db.add_bank_questions(new_qs,
                          subject=value if scope == "subject" else None)

    combined = _bank_to_q(from_bank) + new_qs
    for i, q in enumerate(combined[:count]):
        q["id"] = i + 1
    return {"questions": combined[:count], "from_bank": False}


def _norm(s) -> str:
    return str(s or "").strip().replace(" ", "").replace("　", "").lower()


def submit(question: dict, child_answer: str) -> dict:
    """客观题直接比对;记录错题。"""
    correct = _norm(child_answer) == _norm(question.get("answer"))
    if not correct:
        q = dict(question)
        q["child_answer"] = child_answer
        db.add_wrongbook(q, source="practice")
    return {
        "correct": correct,
        "correct_answer": question.get("answer"),
        "explanation": question.get("explanation", ""),
    }
