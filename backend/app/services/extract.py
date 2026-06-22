"""提取服务：试卷图 → 结构化题目（题干/作答/对错/知识点），并入库。"""
from __future__ import annotations

import logging
from pathlib import Path

from .. import db
from ..llm import get_llm
from ..llm import mock, prompts

log = logging.getLogger("extract")


def extract_material(material_id: int, image_path: str) -> dict:
    """对单张已上传图片做提取，写入 questions 表，更新 material 状态。"""
    llm = get_llm()
    try:
        result = llm.run(
            role="vision",
            system=prompts.EXTRACT_SYSTEM,
            user=prompts.EXTRACT_USER,
            images=[Path(image_path)],
            json_mode=True,
            mock_fn=mock.extract_from_image,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("提取失败 material=%s", material_id)
        db.set_material_status(material_id, "failed")
        raise

    questions = result.get("questions", [])
    for q in questions:
        db.add_question(material_id, q)
    db.set_material_status(
        material_id, "extracted",
        subject=result.get("subject"), source=result.get("source"),
    )
    log.info("提取完成 material=%s 共 %d 题", material_id, len(questions))
    return result
