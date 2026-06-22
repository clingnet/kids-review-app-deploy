"""组卷/模拟卷服务。

- **提速**:组卷优先从题库选题(秒出),题库不够才调 AI 生成,并把新题入库。
- 每张卷子带**唯一编号 code**(打印在卷上)。
- grade():拍照回传做完的卷子 → 视觉识别编号+作答 → 按编号匹配卷子 → 判分 → 存结果 + 错题。
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

from .. import db
from ..llm import get_llm, mock, prompts

log = logging.getLogger("exam")

_TYPE_ORDER = ["选择", "填空", "计算", "解答", "练习", "其它"]


def _simple_type(name) -> str:
    """从可能很啰嗦的题型/章节名里提取规范题型,避免把'二、填空(共3,每710分)'当题型。"""
    s = str(name or "")
    for t in ["选择", "填空", "计算", "解答", "应用", "判断", "练习"]:
        if t in s:
            return "解答" if t == "应用" else t
    return "其它"


def _gen_code() -> str:
    """生成唯一卷子编号,如 SJ-7F3A9。"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        code = "SJ-" + "".join(random.choice(alphabet) for _ in range(5))
        if not db.exam_by_code(code):
            return code
    return "SJ-" + "".join(random.choice(alphabet) for _ in range(7))


def _norm(v) -> str:
    return str(v or "").strip().replace(" ", "").replace("　", "").lower()


def _section_name(typ: str) -> str:
    base = (typ or "其它").replace("题", "")
    cn = {"选择": "选择题", "填空": "填空题", "计算": "计算题",
          "解答": "解答题", "练习": "综合练习"}.get(base, base + "题")
    return cn


def _assemble_from_bank(subject: str, questions: list[dict], num: int,
                        total: int) -> dict:
    """把题库题按题型分组成卷子。"""
    chosen = questions[:num]
    per = max(1, round(total / max(1, len(chosen))))
    groups: dict[str, list[dict]] = {}
    for q in chosen:
        base = _simple_type(q.get("type"))     # 规范化,兼容历史脏题型
        groups.setdefault(base, []).append(q)
    sections = []
    n = 0
    for base in sorted(groups, key=lambda b: _TYPE_ORDER.index(b)
                       if b in _TYPE_ORDER else 99):
        qs = []
        for q in groups[base]:
            n += 1
            qs.append({"number": str(n), "stem": q.get("stem"),
                       "options": q.get("options", []), "score": per,
                       "answer": q.get("answer"),
                       "knowledge_points": q.get("knowledge_points", []),
                       "source": "题库"})
        sections.append({"name": _section_name(base), "questions": qs})
    return {"title": f"{subject}期末模拟卷", "total_score": per * len(chosen),
            "duration_min": 60, "sections": sections}


def generate(subject: str, auto_points, focus_points, weak_points,
             num: int = 15, types: str = "选择题、填空题、计算题、解答题",
             difficulty: str = "中", total: int = 100,
             refresh: bool = False) -> dict:
    kps = list(dict.fromkeys((focus_points or []) + (weak_points or []) +
                             (auto_points or [])))
    if not kps:
        kps = [k["name"] for k in db.list_kp()[:8]]

    # 题库候选(优先)
    pool, seen = [], set()
    for kp in kps:
        for q in db.bank_by_kp(kp, 20):
            if q.get("stem") and q["stem"] not in seen:
                seen.add(q["stem"]); pool.append(q)
    if subject and len(pool) < num:
        for q in db.bank_by_subject(subject, 60):
            if q.get("stem") and q["stem"] not in seen:
                seen.add(q["stem"]); pool.append(q)

    if not refresh and len(pool) >= num:
        random.shuffle(pool)
        paper = _assemble_from_bank(subject, pool, num, total)
        code = _gen_code()
        eid = db.save_exam(paper["title"], paper, code)
        paper.update(exam_id=eid, code=code, from_bank=True)
        log.info("组卷(题库)完成 exam=%s code=%s", eid, code)
        return paper

    # 题库不足 → AI 生成,并入库
    result = get_llm().run(
        role="reason",
        system=prompts.MOCK_EXAM_SYSTEM,
        user=prompts.MOCK_EXAM_USER.format(
            subject=subject,
            auto_points="、".join(auto_points or []) or "无",
            focus_points="、".join(focus_points or []) or "无",
            weak_points="、".join(weak_points or []) or "无",
            num=num, types=types, difficulty=difficulty, total=total),
        json_mode=True,
        mock_fn=mock.mock_exam,
    )
    # 把生成的题入库,供下次秒出
    bank_items = []
    for sec in result.get("sections", []):
        for q in sec.get("questions", []):
            bank_items.append({
                "stem": q.get("stem"), "type": _simple_type(sec.get("name")),
                "options": q.get("options", []), "answer": q.get("answer"),
                "explanation": q.get("explanation", ""),
                "knowledge_points": q.get("knowledge_points", [])})
    if bank_items:
        db.add_bank_questions(bank_items, subject=subject)

    code = _gen_code()
    eid = db.save_exam(result.get("title", f"{subject}模拟卷"), result, code)
    result.update(exam_id=eid, code=code, from_bank=False)
    log.info("组卷(AI)完成 exam=%s code=%s", eid, code)
    return result


def _flatten(payload: dict) -> list[dict]:
    out = []
    for sec in payload.get("sections", []):
        out += sec.get("questions", [])
    return out


def grade(image_path: str) -> dict:
    """拍照判分:识别编号+作答 → 匹配卷子 → 判分 → 存结果 + 错题。"""
    ext = get_llm().run(
        role="vision",
        system=prompts.GRADE_SYSTEM,
        user=prompts.GRADE_USER,
        images=[Path(image_path)],
        json_mode=True,
        mock_fn=mock.grade_paper,
    )
    code = ext.get("code")
    exam = db.exam_by_code(code) if code else None
    if not exam:
        return {"matched": False, "code": code,
                "message": "没识别到卷子编号或找不到对应卷子,请确保编号清晰可见。"}

    payload = exam["payload"]
    questions = _flatten(payload)
    ans_map = {_norm(a.get("number")): a.get("child_answer")
               for a in ext.get("answers", [])}

    details, score, total, correct, wrong = [], 0.0, 0.0, 0, 0
    for q in questions:
        num = _norm(q.get("number"))
        sc = q.get("score") or 0
        total += sc
        child = ans_map.get(num)
        ok = child is not None and _norm(child) == _norm(q.get("answer"))
        if ok:
            score += sc; correct += 1
        else:
            wrong += 1
            if child is not None:        # 只把真做错的入错题本
                db.add_wrongbook({"stem": q.get("stem"), "answer": q.get("answer"),
                                  "child_answer": child,
                                  "knowledge_points": q.get("knowledge_points", [])},
                                 source="exam")
        details.append({"number": q.get("number"), "child_answer": child,
                        "correct_answer": q.get("answer"), "is_correct": ok,
                        "score": sc})

    rid = db.save_exam_result(exam["id"], code, score, total, correct, wrong, details)
    log.info("判分完成 exam=%s code=%s %s/%s", exam["id"], code, score, total)
    return {"matched": True, "code": code, "exam_id": exam["id"],
            "title": payload.get("title"), "result_id": rid,
            "score": score, "total": total, "correct": correct, "wrong": wrong,
            "details": details}
