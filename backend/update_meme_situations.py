#!/usr/bin/env python3
"""meam/memes_classified.json(GPT 상황 분류 결과)을 memes 테이블에 얹는다.

    cd backend && .venv/Scripts/python.exe update_meme_situations.py

import_memes.py가 만든 행(id는 원본 소스의 id/post_id)에 situation/situation_score/
ad_safe 세 컬럼만 채워 넣는다. unique_id가 우리 memes.id와 그대로 대응한다.
memes 테이블에 없는 unique_id(아직 import_memes.py를 안 돌렸거나 소스가 빠진 경우)는
건너뛰고 몇 건인지 알려준다 — 조용히 무시하면 나중에 분류 데이터가 안 들어간 걸 못 찾는다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import models
from app.core.database import SessionLocal, init_db

CLASSIFIED_PATH = Path(__file__).resolve().parents[1] / "meam" / "memes_classified.json"


def main() -> None:
    init_db()
    items = json.loads(CLASSIFIED_PATH.read_text(encoding="utf-8"))

    db = SessionLocal()
    updated = 0
    missing = []
    try:
        for item in items:
            meme_id = item["unique_id"]
            row = db.get(models.Meme, meme_id)
            if row is None:
                missing.append(meme_id)
                continue
            row.situation = item.get("situation") or ""
            row.situation_score = item.get("situation_score")
            row.ad_safe = item.get("ad_safe")
            updated += 1
        db.commit()
    finally:
        db.close()

    print(f"완료 — {updated}건 갱신")
    if missing:
        print(f"memes 테이블에 없어서 건너뜀 ({len(missing)}건): {', '.join(missing)}")
        print("import_memes.py를 먼저 돌렸는지 확인해주세요.")


if __name__ == "__main__":
    main()
