"""API 请求体模型。"""
from __future__ import annotations

from pydantic import BaseModel


class ExplainReq(BaseModel):
    knowledge_point: str
    errors: list[str] | None = None
    refresh: bool = False


class ExamReq(BaseModel):
    subject: str = "数学"
    auto_points: list[str] | None = None      # 全局自动抽选
    focus_points: list[str] | None = None      # 圈选重点（必出）
    weak_points: list[str] | None = None       # 薄弱点（必出）
    num: int = 15
    types: str = "计算/填空/应用题"
    difficulty: str = "易40%/中40%/难20%"
    total: int = 100
    refresh: bool = False             # true=强制 AI 重新出卷(否则优先题库,秒出)


class TutorStartReq(BaseModel):
    knowledge_point: str
    subject: str = "数学"
    errors: list[str] | None = None
    difficulties: list[str] | None = None


class TutorCheckReq(BaseModel):
    knowledge_point: str
    subject: str = "数学"
    answers: str


class PracticeReq(BaseModel):
    scope: str = "weak"               # subject|kp|weak|wrongbook
    value: str | None = None
    count: int = 5
    refresh: bool = False             # true=强制 AI 重出并入库


class PracticeSubmitReq(BaseModel):
    question: dict
    child_answer: str


class WrongbookAddReq(BaseModel):
    question: dict
    source: str = "practice"
