"""DRY_RUN 模拟数据：让无 Key 也能跑通完整链路、看到真实形状的数据。

每个函数对应一类任务的返回，形状与真实模型被要求输出的 JSON 完全一致，
这样真机接 Key 后业务代码无需改动。
"""
from __future__ import annotations


def extract_from_image() -> dict:
    """一张试卷图 → 结构化题目 + 孩子作答 + 对错 + 知识点。"""
    return {
        "subject": "数学",
        "source": "期末模拟卷",
        "questions": [
            {
                "number": "1",
                "type": "计算",
                "stem": "计算 3/4 + 1/6 = ?",
                "child_answer": "4/10",
                "correct_answer": "11/12",
                "is_correct": False,
                "knowledge_points": ["分数加减法", "通分"],
                "error_type": "通分错误：分母未取最小公倍数",
            },
            {
                "number": "2",
                "type": "应用题",
                "stem": "一辆车每小时行 60 千米，3.5 小时行多少千米？",
                "child_answer": "210 千米",
                "correct_answer": "210 千米",
                "is_correct": True,
                "knowledge_points": ["小数乘法", "行程问题"],
                "error_type": None,
            },
            {
                "number": "3",
                "type": "几何",
                "stem": "一个长方形长 8cm 宽 5cm，求周长。",
                "child_answer": "40cm",
                "correct_answer": "26cm",
                "is_correct": False,
                "knowledge_points": ["长方形周长", "周长与面积辨析"],
                "error_type": "概念混淆：把周长算成了面积",
            },
        ],
    }


def global_analysis() -> dict:
    """汇总多张图后的全局知识点概览。"""
    return {
        "summary": "本次复习覆盖数学 12 个知识点，分数运算与几何周长面积辨析是高频失分区。",
        "knowledge_points": [
            {"name": "分数加减法", "subject": "数学", "frequency": 5,
             "difficulty": "中", "beyond_syllabus": False, "mastery": 0.35},
            {"name": "通分", "subject": "数学", "frequency": 4,
             "difficulty": "中", "beyond_syllabus": False, "mastery": 0.40},
            {"name": "长方形周长", "subject": "数学", "frequency": 3,
             "difficulty": "易", "beyond_syllabus": False, "mastery": 0.50},
            {"name": "周长与面积辨析", "subject": "数学", "frequency": 3,
             "difficulty": "中", "beyond_syllabus": False, "mastery": 0.30},
            {"name": "小数乘法", "subject": "数学", "frequency": 4,
             "difficulty": "易", "beyond_syllabus": False, "mastery": 0.85},
        ],
        "relations": [
            {"from": "分数加减法", "to": "通分", "type": "前置"},
            {"from": "周长与面积辨析", "to": "长方形周长", "type": "相关"},
        ],
    }


def weak_points() -> dict:
    """自动总结的薄弱点列表。"""
    return {
        "weak_points": [
            {
                "knowledge_point": "通分",
                "subject": "数学",
                "mastery": 0.40,
                "why": "分数加减时分母不取最小公倍数，直接相加分子分母。",
                "typical_errors": ["3/4 + 1/6 写成 4/10"],
            },
            {
                "knowledge_point": "周长与面积辨析",
                "subject": "数学",
                "mastery": 0.30,
                "why": "周长与面积公式混用，求周长时套了面积算法。",
                "typical_errors": ["长8宽5的长方形周长算成40"],
            },
        ]
    }


def explain_and_practice() -> dict:
    """针对一个薄弱点：讲解文案 + 配套练习题。"""
    return {
        "knowledge_point": "通分",
        "explanation": (
            "通分就是把几个分母不同的分数，变成分母相同的分数，方便加减。\n"
            "关键三步：① 找出各分母的最小公倍数(LCM) 作为公共分母；"
            "② 每个分数的分子分母同乘相同的数；③ 再相加减。\n"
            "例：3/4 + 1/6，分母 4 和 6 的最小公倍数是 12。"
            "3/4 = 9/12，1/6 = 2/12，所以 9/12 + 2/12 = 11/12。"
        ),
        "worked_example": "1/2 + 1/3：LCM(2,3)=6 → 3/6 + 2/6 = 5/6。",
        "practice": [
            {"stem": "2/3 + 1/4 = ?", "answer": "11/12",
             "explanation": "LCM(3,4)=12 → 8/12 + 3/12 = 11/12"},
            {"stem": "5/6 - 1/4 = ?", "answer": "7/12",
             "explanation": "LCM(6,4)=12 → 10/12 - 3/12 = 7/12"},
            {"stem": "1/2 + 2/5 = ?", "answer": "9/10",
             "explanation": "LCM(2,5)=10 → 5/10 + 4/10 = 9/10"},
        ],
    }


def mock_exam() -> dict:
    """一键模拟卷（三来源组卷的结果）。"""
    return {
        "title": "数学期末模拟卷（自动组卷）",
        "total_score": 100,
        "duration_min": 60,
        "sections": [
            {
                "name": "一、计算题",
                "questions": [
                    {"number": "1", "stem": "3/4 + 1/6 =", "score": 5,
                     "answer": "11/12", "knowledge_points": ["通分"], "source": "薄弱点"},
                    {"number": "2", "stem": "5/6 - 1/3 =", "score": 5,
                     "answer": "1/2", "knowledge_points": ["分数加减法"], "source": "重点"},
                ],
            },
            {
                "name": "二、应用题",
                "questions": [
                    {"number": "3",
                     "stem": "长方形长 8cm 宽 5cm，求周长和面积。", "score": 10,
                     "answer": "周长26cm，面积40cm²",
                     "knowledge_points": ["周长与面积辨析"], "source": "薄弱点"},
                ],
            },
        ],
    }


def tutor_turn() -> dict:
    """AI 老师辅导的一轮回复。"""
    return {
        "reply": "我看到你把 3/4+1/6 算成了 4/10，是把分子和分母分别相加了对吗？"
                 "其实分数不能这样直接加哦。我们先看分母 4 和 6，要找一个它们公共的倍数……",
        "ask_back": "你能告诉我，4 和 6 最小的公共倍数是多少吗？",
        "mastered": False,
    }


def mastery_check() -> dict:
    return {"mastered": True, "comment": "孩子能独立完成通分并算对，判定已掌握。", "new_mastery": 0.8}


def practice() -> dict:
    return {
        "questions": [
            {"type": "选择", "stem": "计算 3/4 + 1/6 = ?",
             "options": ["A. 4/10", "B. 11/12", "C. 1", "D. 9/12"],
             "answer": "B", "explanation": "通分:LCM(4,6)=12 → 9/12+2/12=11/12",
             "knowledge_points": ["通分", "分数加法"]},
            {"type": "填空", "stem": "长方形长 8cm 宽 5cm，周长 = ___ cm",
             "options": [], "answer": "26",
             "explanation": "周长=(长+宽)×2=(8+5)×2=26",
             "knowledge_points": ["长方形周长"]},
            {"type": "选择", "stem": "2.5 × 4 = ?",
             "options": ["A. 10", "B. 1.0", "C. 100", "D. 0.1"],
             "answer": "A", "explanation": "2.5×4=10",
             "knowledge_points": ["小数乘法"]},
        ]
    }


def chat() -> dict:
    return {"reply": "好问题!我们一步步来。你能先告诉我这道题里你卡在哪一步了吗?",
            "ask_back": "是不知道怎么通分，还是算到一半不确定?", "mastered": False}


def asr() -> dict:
    return {"text": "老师，这道题我不会做，能讲讲吗？"}


def grade_paper() -> dict:
    return {"code": None, "answers": [
        {"number": "1", "child_answer": "B"},
        {"number": "2", "child_answer": "26cm"},
        {"number": "3", "child_answer": "10"},
    ]}


def kp_intro() -> dict:
    return {"intro": "通分就是把分母不同的分数变成分母相同的分数，方便加减。"
                     "关键是找各分母的最小公倍数作为公共分母。"}
