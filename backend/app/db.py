"""SQLite 数据层。

一期用 sqlite3（零运维、单文件、迁移最省事）。所有 JSON 字段用 TEXT 存。
将来升 Postgres 时，只需替换本模块的连接与少量 SQL 方言；上层服务不动。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from .config import get_settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT,
    source TEXT,
    filename TEXT,
    path TEXT,
    hash TEXT,                         -- 图片内容 sha256,用于去重
    status TEXT DEFAULT 'uploaded',   -- uploaded|extracted|failed
    uploaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER,
    number TEXT,
    type TEXT,
    stem TEXT,
    child_answer TEXT,
    correct_answer TEXT,
    is_correct INTEGER,               -- 0/1
    knowledge_points TEXT,            -- JSON array
    error_type TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(material_id) REFERENCES materials(id)
);

CREATE TABLE IF NOT EXISTS knowledge_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    subject TEXT,
    frequency INTEGER DEFAULT 0,
    difficulty TEXT,
    beyond_syllabus INTEGER DEFAULT 0,
    mastery REAL DEFAULT 0.5,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(name, subject)
);

CREATE TABLE IF NOT EXISTS kp_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_kp TEXT,
    to_kp TEXT,
    type TEXT,
    UNIQUE(from_kp, to_kp, type)
);

CREATE TABLE IF NOT EXISTS weak_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_point TEXT,
    subject TEXT,
    mastery REAL,
    why TEXT,
    typical_errors TEXT,              -- JSON array
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(knowledge_point, subject)
);

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,                        -- 唯一卷子编号(打印在卷上,拍照回传时对应)
    title TEXT,
    payload TEXT,                     -- JSON（整张卷子）
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exam_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER,
    code TEXT,
    score REAL,
    total REAL,
    correct_count INTEGER,
    wrong_count INTEGER,
    details TEXT,                     -- JSON 逐题 {number,child_answer,correct_answer,is_correct}
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tutor_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_point TEXT,
    history TEXT DEFAULT '[]',        -- JSON array of {role,content}
    mastered INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wrongbook (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT,                    -- JSON {stem,answer,child_answer,knowledge_points,...}
    source TEXT,                      -- practice|exam|upload
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mastery_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT,                         -- YYYY-MM-DD
    overall REAL,
    UNIQUE(day)
);

-- 知识点讲解缓存(详解/讲解/例题):生成一次存下,之后直接读,刷新按钮才重算
CREATE TABLE IF NOT EXISTS kp_content (
    name TEXT PRIMARY KEY,
    subject TEXT,
    intro TEXT,
    explanation TEXT,
    worked_example TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 题库:AI 生成的练习题存这里,出题优先从题库选,不够再调 AI
CREATE TABLE IF NOT EXISTS question_bank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT,
    knowledge_points TEXT,            -- JSON array
    type TEXT,
    stem TEXT,
    options TEXT,                     -- JSON array
    answer TEXT,
    explanation TEXT,
    source TEXT DEFAULT 'ai',
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        c = sqlite3.connect(str(get_settings().db_path), check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=8000")   # 并发提取时避免 database is locked
        _local.conn = c
    return _local.conn


def _txt(v) -> str | None:
    """把模型偶尔返回的 list/dict 转成字符串,避免 sqlite 绑定报错。"""
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def init_db() -> None:
    _conn().executescript(SCHEMA)
    # 兼容旧库:补 hash 列
    for tbl, col, typ in [("materials", "hash", "TEXT"), ("exams", "code", "TEXT")]:
        try:
            _conn().execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    _conn().commit()


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    c = _conn()
    cur = c.cursor()
    try:
        yield cur
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        cur.close()


def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


def _rows(rs) -> list[dict]:
    return [dict(r) for r in rs]


# ---------- materials ----------
def add_material(subject: str, source: str, filename: str, path: str,
                 hash_: str | None = None) -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO materials(subject,source,filename,path,hash) VALUES(?,?,?,?,?)",
            (subject, source, filename, path, hash_),
        )
        return cur.lastrowid


def material_by_hash(hash_: str) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM materials WHERE hash=? LIMIT 1", (hash_,))
        return _row(cur.fetchone())


def set_material_status(mid: int, status: str, subject: str | None = None,
                        source: str | None = None) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE materials SET status=?, subject=COALESCE(?,subject),"
            " source=COALESCE(?,source) WHERE id=?",
            (status, subject, source, mid),
        )


def list_materials() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM materials ORDER BY id DESC")
        return _rows(cur.fetchall())


# ---------- questions ----------
def add_question(material_id: int, q: dict) -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO questions(material_id,number,type,stem,child_answer,"
            "correct_answer,is_correct,knowledge_points,error_type)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (
                material_id, _txt(q.get("number")), _txt(q.get("type")),
                _txt(q.get("stem")), _txt(q.get("child_answer")),
                _txt(q.get("correct_answer")),
                1 if q.get("is_correct") else 0,
                json.dumps(q.get("knowledge_points", []), ensure_ascii=False),
                _txt(q.get("error_type")),
            ),
        )
        return cur.lastrowid


def all_questions() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM questions ORDER BY id DESC")
        out = _rows(cur.fetchall())
    for r in out:
        r["knowledge_points"] = json.loads(r.get("knowledge_points") or "[]")
        r["is_correct"] = bool(r["is_correct"])
    return out


def wrong_questions() -> list[dict]:
    return [q for q in all_questions() if not q["is_correct"]]


# ---------- knowledge points ----------
def upsert_kp(kp: dict) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_points(name,subject,frequency,difficulty,"
            "beyond_syllabus,mastery) VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(name,subject) DO UPDATE SET"
            " frequency=excluded.frequency, difficulty=excluded.difficulty,"
            " beyond_syllabus=excluded.beyond_syllabus, mastery=excluded.mastery,"
            " updated_at=datetime('now')",
            (kp["name"], kp.get("subject"), kp.get("frequency", 0),
             kp.get("difficulty"), 1 if kp.get("beyond_syllabus") else 0,
             kp.get("mastery", 0.5)),
        )


def set_mastery(name: str, subject: str, mastery: float) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE knowledge_points SET mastery=?, updated_at=datetime('now')"
            " WHERE name=? AND subject=?", (mastery, name, subject))


def list_kp() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM knowledge_points ORDER BY frequency DESC, mastery ASC")
        out = _rows(cur.fetchall())
    for r in out:
        r["beyond_syllabus"] = bool(r["beyond_syllabus"])
    return out


def upsert_relation(frm: str, to: str, typ: str) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT OR IGNORE INTO kp_relations(from_kp,to_kp,type) VALUES(?,?,?)",
            (frm, to, typ))


def list_relations() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT from_kp,to_kp,type FROM kp_relations")
        return _rows(cur.fetchall())


# ---------- weak points ----------
def replace_weak_points(items: list[dict]) -> None:
    with cursor() as cur:
        cur.execute("DELETE FROM weak_points")
        for w in items:
            cur.execute(
                "INSERT INTO weak_points(knowledge_point,subject,mastery,why,"
                "typical_errors) VALUES(?,?,?,?,?)",
                (w["knowledge_point"], w.get("subject"), w.get("mastery"),
                 w.get("why"),
                 json.dumps(w.get("typical_errors", []), ensure_ascii=False)),
            )


def list_weak_points() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM weak_points ORDER BY mastery ASC")
        out = _rows(cur.fetchall())
    for r in out:
        r["typical_errors"] = json.loads(r.get("typical_errors") or "[]")
    return out


# ---------- exams ----------
def save_exam(title: str, payload: dict, code: str | None = None) -> int:
    with cursor() as cur:
        cur.execute("INSERT INTO exams(code,title,payload) VALUES(?,?,?)",
                    (code, title, json.dumps(payload, ensure_ascii=False)))
        return cur.lastrowid


def list_exams() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT id,code,title,created_at FROM exams ORDER BY id DESC")
        return _rows(cur.fetchall())


def get_exam(eid: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM exams WHERE id=?", (eid,))
        r = _row(cur.fetchone())
    if r:
        r["payload"] = json.loads(r["payload"])
    return r


def exam_by_code(code: str) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM exams WHERE code=? ORDER BY id DESC LIMIT 1", (code,))
        r = _row(cur.fetchone())
    if r:
        r["payload"] = json.loads(r["payload"])
    return r


def save_exam_result(exam_id: int, code: str, score: float, total: float,
                     correct: int, wrong: int, details: list[dict]) -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO exam_results(exam_id,code,score,total,correct_count,"
            "wrong_count,details) VALUES(?,?,?,?,?,?,?)",
            (exam_id, code, score, total, correct, wrong,
             json.dumps(details, ensure_ascii=False)))
        return cur.lastrowid


def list_exam_results() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM exam_results ORDER BY id DESC")
        out = _rows(cur.fetchall())
    for r in out:
        r["details"] = json.loads(r.get("details") or "[]")
    return out


# ---------- tutor sessions ----------
def create_tutor_session(kp: str) -> int:
    with cursor() as cur:
        cur.execute("INSERT INTO tutor_sessions(knowledge_point) VALUES(?)", (kp,))
        return cur.lastrowid


def get_tutor_session(sid: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM tutor_sessions WHERE id=?", (sid,))
        r = _row(cur.fetchone())
    if r:
        r["history"] = json.loads(r["history"])
        r["mastered"] = bool(r["mastered"])
    return r


def update_tutor_session(sid: int, history: list[dict], mastered: bool) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE tutor_sessions SET history=?, mastered=?, updated_at=datetime('now')"
            " WHERE id=?",
            (json.dumps(history, ensure_ascii=False), 1 if mastered else 0, sid))


# ---------- 知识点详情 ----------
def questions_for_kp(name: str) -> tuple[list[dict], list[dict]]:
    """返回 (该知识点出过的题, 其中做错的题)。"""
    out = [q for q in all_questions() if name in (q.get("knowledge_points") or [])]
    wrong = [q for q in out if not q["is_correct"]]
    return out, wrong


# ---------- 错题本 ----------
def add_wrongbook(question: dict, source: str = "practice") -> int:
    with cursor() as cur:
        cur.execute("INSERT INTO wrongbook(question,source) VALUES(?,?)",
                    (json.dumps(question, ensure_ascii=False), source))
        return cur.lastrowid


def list_wrongbook() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM wrongbook ORDER BY id DESC")
        out = _rows(cur.fetchall())
    for r in out:
        r["question"] = json.loads(r["question"])
    return out


# ---------- 掌握度快照(趋势) ----------
def snapshot_overall(overall: float) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO mastery_snapshots(day,overall) VALUES(date('now'),?)"
            " ON CONFLICT(day) DO UPDATE SET overall=excluded.overall", (overall,))


def list_snapshots(limit: int = 7) -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT day,overall FROM mastery_snapshots ORDER BY day DESC LIMIT ?",
                    (limit,))
        return list(reversed(_rows(cur.fetchall())))


# ---------- 知识点讲解缓存 ----------
def get_kp_content(name: str) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM kp_content WHERE name=?", (name,))
        return _row(cur.fetchone())


def upsert_kp_content(name: str, subject: str | None = None, intro: str | None = None,
                      explanation: str | None = None,
                      worked_example: str | None = None) -> None:
    """只更新非 None 字段(intro 与 explanation 可分别缓存)。"""
    with cursor() as cur:
        cur.execute(
            "INSERT INTO kp_content(name,subject,intro,explanation,worked_example)"
            " VALUES(?,?,?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET"
            " subject=COALESCE(?,subject), intro=COALESCE(?,intro),"
            " explanation=COALESCE(?,explanation),"
            " worked_example=COALESCE(?,worked_example), updated_at=datetime('now')",
            (name, subject, intro, explanation, worked_example,
             subject, intro, explanation, worked_example))


# ---------- 题库 ----------
def add_bank_questions(items: list[dict], subject: str | None = None) -> None:
    with cursor() as cur:
        for q in items:
            cur.execute(
                "INSERT INTO question_bank(subject,knowledge_points,type,stem,options,"
                "answer,explanation,source) VALUES(?,?,?,?,?,?,?,?)",
                (subject or q.get("subject"),
                 json.dumps(q.get("knowledge_points", []), ensure_ascii=False),
                 q.get("type"), q.get("stem"),
                 json.dumps(q.get("options", []), ensure_ascii=False),
                 _txt(q.get("answer")), q.get("explanation"), q.get("source", "ai")))


def _bank_row(r: dict) -> dict:
    r["knowledge_points"] = json.loads(r.get("knowledge_points") or "[]")
    r["options"] = json.loads(r.get("options") or "[]")
    return r


def bank_by_kp(name: str, limit: int = 20) -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM question_bank WHERE knowledge_points LIKE ?"
                    " ORDER BY id DESC LIMIT ?", (f'%"{name}"%', limit))
        return [_bank_row(dict(r)) for r in cur.fetchall()]


def bank_by_subject(subject: str, limit: int = 50) -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM question_bank WHERE subject=? ORDER BY id DESC LIMIT ?",
                    (subject, limit))
        return [_bank_row(dict(r)) for r in cur.fetchall()]


def bank_all(limit: int = 100) -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM question_bank ORDER BY id DESC LIMIT ?", (limit,))
        return [_bank_row(dict(r)) for r in cur.fetchall()]
