"""真机测试：用真实 OpenRouter 模型跑通 视觉提取 + 推理分析 全链路。

运行：cd kids-review-app && PYTHONPATH=backend DATA_DIR=/tmp/kr_real python3 backend/real_test.py
（依赖根目录 .env 里的 OPENROUTER_API_KEY 与 LLM_DRY_RUN=false）
"""
import os
import sys
import time

os.environ.setdefault("DATA_DIR", "/tmp/kr_real")

from PIL import Image, ImageDraw, ImageFont

from app import db
from app.config import get_settings
from app.services import analyze, exam, extract, tutor
from app.services.images import save_and_compress

FONT = "/home/ubuntu/workspace/NotoSansSC.otf"


def make_worksheet() -> bytes:
    img = Image.new("RGB", (900, 1200), "white")
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(FONT, 34)
    mid = ImageFont.truetype(FONT, 30)
    red = (200, 30, 30)
    d.text((40, 40), "五年级数学期末练习", font=big, fill="black")
    lines = [
        ("1. 计算 3/4 + 1/6 =", "4/10", False),
        ("2. 计算 8 × 5 =", "40", True),
        ("3. 长方形 长8cm 宽5cm，周长 =", "40cm", False),
        ("4. 2.5 × 4 =", "10", True),
    ]
    y = 130
    for stem, ans, ok in lines:
        d.text((50, y), stem, font=mid, fill="black")
        d.text((620, y), ans, font=mid, fill=(20, 90, 200))   # 蓝色"手写"作答
        if not ok:
            d.text((760, y), "✗", font=mid, fill=red)          # 老师批改
        else:
            d.text((760, y), "✓", font=mid, fill=(20, 150, 60))
        y += 110
    import io
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def main():
    s = get_settings()
    print(f"dry_run={s.llm_dry_run}  vision={s.vision_model}  reason={s.reason_model}")
    assert not s.llm_dry_run, "请确保 .env 里 LLM_DRY_RUN=false"
    db.init_db()

    print("\n== 1. 视觉提取（Qwen3-VL 读图）==")
    t = time.time()
    fname, path = save_and_compress(make_worksheet(), "ws.jpg")
    mid = db.add_material("未知", "未知", fname, path)
    res = extract.extract_material(mid, path)
    print(f"  科目={res.get('subject')} 用时={time.time()-t:.1f}s 题数={len(res.get('questions',[]))}")
    for q in res.get("questions", []):
        print(f"   [{q.get('number')}] {q.get('stem')!r} 作答={q.get('child_answer')!r} "
              f"对错={q.get('is_correct')} 知识点={q.get('knowledge_points')}")

    print("\n== 2. 全局分析（DeepSeek 推理）==")
    t = time.time()
    g = analyze.run_global_analysis()
    print(f"  用时={time.time()-t:.1f}s 知识点={len(g.get('knowledge_points',[]))}")
    print(f"  概述：{g.get('summary','')[:80]}")

    print("\n== 3. 薄弱点 ==")
    w = analyze.run_weak_points()
    for x in w.get("weak_points", []):
        print(f"   - {x.get('knowledge_point')} 掌握={x.get('mastery')}")

    print("\n== 4. 讲解+练习 ==")
    kp = (w.get("weak_points") or [{}])[0].get("knowledge_point", "通分")
    ex = analyze.explain_weak_point(kp, [])
    print(f"   讲解({kp})：{ex.get('explanation','')[:70]}… 练习={len(ex.get('practice',[]))}道")

    print("\n== 5. 模拟卷（三来源）==")
    paper = exam.generate_exam("数学", auto_points=None, focus_points=[kp], weak_points=[])
    nq = sum(len(sec.get("questions", [])) for sec in paper.get("sections", []))
    print(f"   {paper.get('title')} 大题={len(paper.get('sections',[]))} 题数={nq}")

    print("\n== 6. AI 老师辅导（多轮）==")
    t0 = tutor.start(kp, errors=["3/4+1/6=4/10"])
    print(f"   初始讲解：{t0.get('reply','')[:60]}…")
    t1 = tutor.say(t0["session_id"], "我不知道4和6的最小公倍数是多少")
    print(f"   多轮回应：{t1.get('reply','')[:60]}…")

    print("\n🎉 OpenRouter 真机全链路通过")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ 失败：", repr(e))
        sys.exit(1)
