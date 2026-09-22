"""네컷을 실제로 안 그리고, media/ 에 이미 있는 이미지를 돌려써서 comic_cuts를
done 상태로 채운다 — Result(완성된 광고) 화면 레이아웃·캡션만 눈으로 확인하고
싶을 때 쓴다. 실제 그림 생성(ComfyUI)은 안 돈다.

돌리는 법 (backend/ 에서): .venv/Scripts/python.exe dev_fake_comic.py
(먼저 스토리보드 대화로 plan을 4컷 확정해 둬야 한다 — plan이 비어 있으면 그냥 끝난다.)
"""

from app.core.database import SessionLocal
from app import models

IMAGES = [
    "22ed210f386146d090e703e439e8c069.png",
    "23db86706f5543cbb515c533b7d2ea53.png",
    "a044731976b943619ff3e4a86e14f09d.png",
]

db = SessionLocal()
sb = db.get(models.Storyboard, 1)
plan = list(sb.plan or [])
if not plan:
    raise SystemExit("plan이 비어 있음 — 먼저 대화로 컷 구성을 만들어야 함")

cuts = []
for i, c in enumerate(plan):
    cuts.append({
        "n": c["n"], "short": c.get("short", ""), "line": c.get("line", ""),
        "action": c.get("action", ""), "camera": c.get("camera", ""),
        "label": f"{c['n']}컷",
        "image": f"/api/media/{IMAGES[i % len(IMAGES)]}",
        "status": "done",
    })

sb.comic_cuts = cuts
db.commit()
print("comic_cuts 채움:", len(cuts), "컷")
db.close()
