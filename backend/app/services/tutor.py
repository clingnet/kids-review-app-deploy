"""AI 老师·知识点辅导（多轮多模态会话）。

流程：start() 生成初始讲解 → say()/ask_with_image() 多轮一对一 →
check_mastery() 出题考察判定掌握 → 回写知识点掌握度。
语音(ASR/TTS)在路由层接入（三期），本服务只管文本+视觉的会话逻辑。
"""
from __future__ import annotations

import logging
from pathlib import Path

from .. import db
from ..llm import get_llm, mock, prompts

log = logging.getLogger("tutor")


def _history_text(history: list[dict]) -> str:
    role_cn = {"teacher": "老师", "child": "孩子"}
    return "\n".join(f"{role_cn.get(h['role'], h['role'])}：{h['content']}"
                     for h in history) or "（暂无）"


def start(kp: str, errors: list[str] | None = None,
          difficulties: list[str] | None = None) -> dict:
    sid = db.create_tutor_session(kp)
    result = get_llm().run(
        role="reason",
        system=prompts.TUTOR_SYSTEM,
        user=prompts.TUTOR_INIT_USER.format(
            kp=kp,
            errors="、".join(errors or []) or "（无记录）",
            difficulties="、".join(difficulties or []) or "（无记录）",
        ),
        json_mode=True,
        mock_fn=mock.tutor_turn,
    )
    history = [{"role": "teacher", "content": result.get("reply", "")}]
    if result.get("ask_back"):
        history.append({"role": "teacher", "content": result["ask_back"]})
    db.update_tutor_session(sid, history, mastered=False)
    result["session_id"] = sid
    return result


def say(session_id: int, child_text: str,
        image_path: str | None = None) -> dict:
    """孩子说一句话（语音转写文本）/ 附手写困惑照片，老师继续引导。"""
    sess = db.get_tutor_session(session_id)
    if not sess:
        raise ValueError("会话不存在")
    kp = sess["knowledge_point"]
    history = sess["history"]
    history.append({"role": "child", "content": child_text})

    images = [Path(image_path)] if image_path else None
    # 有图走视觉模型，无图走推理模型
    role = "vision" if images else "reason"
    result = get_llm().run(
        role=role,
        system=prompts.TUTOR_SYSTEM,
        user=prompts.TUTOR_TURN_USER.format(
            kp=kp, history=_history_text(history),
            child=child_text + ("（含手写照片）" if image_path else "")),
        images=images,
        json_mode=True,
        mock_fn=mock.tutor_turn,
    )
    history.append({"role": "teacher", "content": result.get("reply", "")})
    if result.get("ask_back"):
        history.append({"role": "teacher", "content": result["ask_back"]})
    mastered = bool(result.get("mastered"))
    db.update_tutor_session(session_id, history, mastered=mastered)
    result["session_id"] = session_id
    return result


def check_mastery(session_id: int, kp: str, subject: str,
                  answers: str) -> dict:
    """出题考察后，判定是否彻底掌握，并回写掌握度（进闭环）。"""
    result = get_llm().run(
        role="reason",
        system=prompts.MASTERY_CHECK_SYSTEM,
        user=prompts.MASTERY_CHECK_USER.format(kp=kp, answers=answers),
        json_mode=True,
        mock_fn=mock.mastery_check,
    )
    if "new_mastery" in result:
        db.set_mastery(kp, subject, float(result["new_mastery"]))
    sess = db.get_tutor_session(session_id)
    if sess:
        db.update_tutor_session(session_id, sess["history"],
                                mastered=bool(result.get("mastered")))
    return result
