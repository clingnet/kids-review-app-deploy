"""所有 HTTP API 路由。"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db
from ..config import get_settings
from ..models import (ExamReq, ExplainReq, PracticeReq, PracticeSubmitReq,
                      TutorCheckReq, TutorStartReq, WrongbookAddReq)
from ..services import (analyze, asr, chat, dashboard, exam, extract, jobs,
                        practice, tutor)
from ..services.images import save_and_compress

router = APIRouter(prefix="/api")


@router.get("/status")
def status() -> dict:
    s = get_settings()
    return {
        "dry_run": s.llm_dry_run,
        "materials": len(db.list_materials()),
        "questions": len(db.all_questions()),
        "weak_points": len(db.list_weak_points()),
        "exams": len(db.list_exams()),
    }


@router.get("/analysis/status")
def analysis_status():
    return jobs.status()


@router.get("/dashboard")
def get_dashboard():
    return dashboard.build()


# ---------- 上传(异步分析) ----------
@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    import hashlib
    ids = []
    results = []
    for f in files:
        raw = await f.read()
        h = hashlib.sha256(raw).hexdigest()
        dup = db.material_by_hash(h)        # 去重:相同图片不重复入库/分析
        if dup:
            results.append({"material_id": dup["id"], "filename": dup["filename"],
                            "duplicate": True})
            continue
        fname, path = save_and_compress(raw, f.filename or "img.jpg")
        mid = db.add_material("未知", "未知", fname, path, hash_=h)
        ids.append(mid)
        results.append({"material_id": mid, "filename": fname})
    if ids:
        jobs.enqueue(ids)                   # 后台异步:提取 + 全局分析 + 薄弱点
    return {"uploaded": results, "queued": bool(ids),
            "duplicates": sum(1 for r in results if r.get("duplicate"))}


@router.post("/materials/{mid}/extract")
def extract_one(mid: int):
    mats = {m["id"]: m for m in db.list_materials()}
    if mid not in mats:
        raise HTTPException(404, "素材不存在")
    return extract.extract_material(mid, mats[mid]["path"])


@router.get("/materials")
def materials():
    return db.list_materials()


@router.get("/questions")
def questions():
    return db.all_questions()


# ---------- 全局分析 / 知识图谱 ----------
@router.post("/analyze/global")
def analyze_global():
    return analyze.run_global_analysis()


@router.get("/knowledge")
def knowledge():
    """知识图谱数据：节点 + 关系。"""
    return {"knowledge_points": db.list_kp(), "relations": db.list_relations()}


@router.get("/knowledge/detail")
def knowledge_detail(name: str, subject: str | None = None):
    """知识点详情:介绍 / 出过的题 / 做错过的题 / 掌握度。"""
    return chat.kp_detail(name, subject)


@router.get("/report")
def report():
    """全局分析报告(若无则现算)。"""
    return analyze.run_global_analysis()


# ---------- 薄弱点 ----------
@router.post("/analyze/weak")
def analyze_weak():
    return analyze.run_weak_points()


@router.get("/weak")
def weak():
    return db.list_weak_points()


@router.post("/weak/explain")
def weak_explain(req: ExplainReq):
    return analyze.explain_weak_point(req.knowledge_point, req.errors, req.refresh)


# ---------- 模拟卷 ----------
@router.post("/exam/generate")
def exam_generate(req: ExamReq):
    return exam.generate(
        subject=req.subject, auto_points=req.auto_points,
        focus_points=req.focus_points, weak_points=req.weak_points,
        num=req.num, types=req.types, difficulty=req.difficulty,
        total=req.total, refresh=req.refresh)


@router.get("/exams")
def exams():
    return db.list_exams()


@router.get("/exams/{eid}")
def exam_detail(eid: int):
    e = db.get_exam(eid)
    if not e:
        raise HTTPException(404, "卷子不存在")
    return e


@router.post("/exam/grade")
async def exam_grade(image: UploadFile = File(...)):
    """拍照回传做完的试卷 → 识别编号+作答 → 判分 → 存结果+错题。"""
    raw = await image.read()
    _, path = save_and_compress(raw, image.filename or "paper.jpg")
    return exam.grade(path)


@router.get("/exam/results")
def exam_results():
    return db.list_exam_results()


# ---------- AI 老师辅导 ----------
@router.post("/tutor/start")
def tutor_start(req: TutorStartReq):
    return tutor.start(req.knowledge_point, req.errors, req.difficulties)


@router.post("/tutor/{sid}/say")
async def tutor_say(sid: int, text: str = Form(...),
                    image: UploadFile | None = File(None)):
    image_path = None
    if image is not None:
        raw = await image.read()
        _, image_path = save_and_compress(raw, image.filename or "q.jpg")
    return tutor.say(sid, text, image_path)


@router.post("/tutor/{sid}/check")
def tutor_check(sid: int, req: TutorCheckReq):
    return tutor.check_mastery(sid, req.knowledge_point, req.subject, req.answers)


# ---------- 语音转文字(+通顺化) ----------
@router.post("/asr")
async def asr_route(audio: UploadFile = File(...)):
    raw = await audio.read()
    return await asr.transcribe(raw, audio.content_type, audio.filename)


# ---------- AI 老师·通用问答 chat ----------
@router.get("/chat/history")
def chat_history(session_id: int):
    """刷新后恢复对话:返回该会话的历史消息。"""
    sess = db.get_tutor_session(session_id)
    if not sess:
        return {"session_id": session_id, "topic": None, "history": []}
    return {"session_id": session_id,
            "topic": sess.get("knowledge_point"),
            "history": sess.get("history", []),
            "mastered": sess.get("mastered", False)}


@router.post("/chat")
async def chat_route(
    message: str = Form(...),
    session_id: int | None = Form(None),
    topic: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    image_path = None
    if image is not None:
        raw = await image.read()
        _, image_path = save_and_compress(raw, image.filename or "q.jpg")
    return chat.chat(session_id, message, topic, image_path)


# ---------- 自我练习 ----------
@router.post("/practice/generate")
def practice_generate(req: PracticeReq):
    return practice.generate(req.scope, req.value, req.count, req.refresh)


@router.post("/practice/submit")
def practice_submit(req: PracticeSubmitReq):
    return practice.submit(req.question, req.child_answer)


# ---------- 错题本 ----------
@router.get("/wrongbook")
def wrongbook():
    return db.list_wrongbook()


@router.post("/wrongbook/add")
def wrongbook_add(req: WrongbookAddReq):
    return {"id": db.add_wrongbook(req.question, req.source)}
