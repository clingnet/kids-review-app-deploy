"""AI 老师问答(通用多轮 chat,支持知识点上下文 + 拍照)。复用 tutor_sessions 存历史。"""
from __future__ import annotations

from pathlib import Path

from .. import db
from ..llm import get_llm, mock, prompts


def _history_text(history: list[dict]) -> str:
    role_cn = {"teacher": "老师", "child": "孩子"}
    return "\n".join(f"{role_cn.get(h['role'], h['role'])}：{h['content']}"
                     for h in history) or "（暂无）"


def _weak_text(topic: str | None) -> str:
    """取该知识点孩子做错过的题,喂给 AI 做针对性教学。"""
    if not topic:
        return ""
    _, wrong = db.questions_for_kp(topic)
    if not wrong:
        return ""
    lines = []
    for q in wrong[:5]:
        lines.append(
            f"- 题目：{q.get('stem','')}；孩子答：{q.get('child_answer')}；"
            f"正确答案：{q.get('correct_answer')}；错因：{q.get('error_type') or '未标注'}")
    return ("孩子在这个知识点上做错过的题（请对症分析、对症讲解，不要泛泛而谈）：\n"
            + "\n".join(lines) + "\n\n")


def chat(session_id: int | None, message: str, topic: str | None = None,
         image_path: str | None = None) -> dict:
    if not session_id:
        session_id = db.create_tutor_session(topic or "通用辅导")
    sess = db.get_tutor_session(session_id)
    if not sess:
        session_id = db.create_tutor_session(topic or "通用辅导")
        sess = db.get_tutor_session(session_id)

    history = sess["history"]
    history.append({"role": "child", "content": message})

    context = f"正在辅导知识点「{topic}」。\n" if topic else ""
    weak = _weak_text(topic)
    images = [Path(image_path)] if image_path else None
    role = "vision" if images else "reason"

    result = get_llm().run(
        role=role,
        system=prompts.CHAT_SYSTEM,
        user=prompts.CHAT_USER.format(
            context=context, weak=weak, history=_history_text(history),
            message=message, img="（含手写照片）" if image_path else ""),
        images=images,
        json_mode=True,
        mock_fn=mock.chat,
    )
    history.append({"role": "teacher", "content": result.get("reply", "")})
    if result.get("ask_back"):
        history.append({"role": "teacher", "content": result["ask_back"]})
    db.update_tutor_session(session_id, history, mastered=bool(result.get("mastered")))
    result["session_id"] = session_id
    return result


def kp_detail(name: str, subject: str | None = None) -> dict:
    """知识点详情:介绍 + 出过的题 + 做错过的题 + 掌握度。介绍**带缓存**,生成一次即存。"""
    questions, wrong = db.questions_for_kp(name)
    mastery = next((k.get("mastery") for k in db.list_kp()
                    if k["name"] == name), None)
    cached = db.get_kp_content(name)
    if cached and cached.get("intro"):
        intro = cached["intro"]                      # 命中缓存,秒回,不调 AI
    else:
        intro = get_llm().run(
            role="reason",
            system=prompts.KP_INTRO_SYSTEM,
            user=prompts.KP_INTRO_USER.format(kp=name),
            json_mode=True,
            mock_fn=mock.kp_intro,
        ).get("intro", "")
        db.upsert_kp_content(name, subject=subject, intro=intro)
    return {"name": name, "subject": subject, "mastery": mastery,
            "intro": intro, "questions": questions, "wrong_questions": wrong}
