"""DRY_RUN 链路冒烟测试：不依赖真实模型，验证服务+DB+流程跑通。

运行：cd backend && DATA_DIR=/tmp/kr_smoke LLM_DRY_RUN=true python smoke_test.py
"""
import io
import os
import sys

os.environ.setdefault("LLM_DRY_RUN", "true")
os.environ.setdefault("DATA_DIR", "/tmp/kr_smoke")

from PIL import Image

from app import db
from app.services import analyze, exam, extract, tutor
from app.services.images import save_and_compress

db.init_db()


def fake_image_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1200, 1600), (240, 240, 240)).save(buf, "JPEG")
    return buf.getvalue()


def check(name, cond):
    print(("✅" if cond else "❌"), name)
    if not cond:
        sys.exit(1)


print("== 1. 上传+压缩 ==")
fname, path = save_and_compress(fake_image_bytes(), "test.jpg")
mid = db.add_material("未知", "未知", fname, path)
check("素材入库", mid > 0 and os.path.exists(path))

print("== 2. 提取 ==")
res = extract.extract_material(mid, path)
check("提取出题目", len(res["questions"]) > 0)
check("题目入库", len(db.all_questions()) > 0)
check("有错题", len(db.wrong_questions()) > 0)

print("== 3. 全局分析 ==")
g = analyze.run_global_analysis()
check("生成知识点", len(g["knowledge_points"]) > 0)
check("知识点落库", len(db.list_kp()) > 0)
check("关系落库", len(db.list_relations()) > 0)

print("== 4. 薄弱点 ==")
w = analyze.run_weak_points()
check("薄弱点生成", len(w["weak_points"]) > 0)
check("薄弱点落库", len(db.list_weak_points()) > 0)

print("== 5. 讲解+练习 ==")
ex = analyze.explain_weak_point("通分", ["3/4+1/6=4/10"])
check("有讲解", bool(ex["explanation"]))
check("有练习", len(ex["practice"]) == 3)

print("== 6. 模拟卷(三来源) ==")
paper = exam.generate_exam("数学", auto_points=["小数乘法"],
                           focus_points=["通分"], weak_points=["周长与面积辨析"])
check("生成卷子", len(paper["sections"]) > 0)
check("卷子落库", paper.get("exam_id", 0) > 0 and db.get_exam(paper["exam_id"]) is not None)

print("== 7. AI老师辅导 ==")
t0 = tutor.start("通分", errors=["3/4+1/6=4/10"])
sid = t0["session_id"]
check("初始讲解", bool(t0["reply"]))
t1 = tutor.say(sid, "我不知道4和6的最小公倍数")
check("多轮回应", bool(t1["reply"]))
m = tutor.check_mastery(sid, "通分", "数学", "3/4+1/6=11/12，做对了")
check("掌握判定", "mastered" in m)
kp = [k for k in db.list_kp() if k["name"] == "通分"]
check("掌握度回写", kp and kp[0]["mastery"] == m.get("new_mastery"))

print("\n🎉 全链路 DRY_RUN 冒烟测试通过")
