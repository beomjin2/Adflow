#!/usr/bin/env python3
"""memes 테이블의 image를 외부 URL 대신 로컬 사본(app/static/memes/*.jpg)으로 바꾼다.

    cd backend && .venv/Scripts/python.exe localize_meme_images.py

로컬 사본은 지연님이 fix_for_yeonjin 디자인 목업을 만들 때 25개 밈만 골라 내려받아
둔 것(원래 fix_for_yeonjin/images/ → 지금은 crawling/images/)이라, 31건 중 25장뿐이다.
그 25장에 대응하는 밈은 image를 "/api/meme-images/meme-NN.jpg"로 바꾸고, 대응이 없는
나머지는 **행 자체를 지운다** — 사장님이 시킨 대로다: 이미지를 못 구하는 밈은 화면에서
아예 빼고, 외부 URL로도 대신 채우지 않는다.

이름 대조는 공백만 지우고 비교한다(같은 밈인데 사이트마다 "일하기 전 제 모습이고요" /
"일하기전제모습이고요"처럼 띄어쓰기만 다른 경우가 있어서) — 문장 자체가 다른 건 다른
밈으로 본다. "면접을 진행하겠습니다..", "00삐", "죄송합니다 OO 포기하겠습니다"는 같은
유행의 다른 표현이지만 문장이 달라 자동으로 같다고 단정하지 않았다 — 지웠다.

매핑은 design_data.js(현재 지워짐, git 커밋 2adb82b에 남아있음)의 MEME_META를 그대로
옮긴 것이다. 새 밈을 추가하고 로컬 이미지도 새로 받으면 여기 딕셔너리에 한 줄 추가하면 된다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import models
from app.core.database import SessionLocal, init_db

IMAGE_URL_PREFIX = "/api/meme-images"

# meme_name(원본 표기) -> 로컬 파일명. design_data.js MEME_META에서 그대로 옮김.
NAME_TO_FILENAME = {
    "하겠습니다 안 하겠습니다": "meme-01.jpg",
    "고맙투우사 챌린지": "meme-02.jpg",
    "누가 돌아왔게": "meme-03.jpg",
    "거제 야호": "meme-04.jpg",
    "그린그린 레드레드": "meme-05.jpg",
    "과자 사진 꾸미기 (과자 사꾸)": "meme-06.jpg",
    "셋로그 챌린지": "meme-07.jpg",
    "냐냐냥 밈": "meme-08.jpg",
    "간바레 챌린지": "meme-09.jpg",
    "장항준적 사고": "meme-10.jpg",
    "장원영 OO": "meme-11.jpg",
    "OO 정보": "meme-12.jpg",
    "나만아는100드립": "meme-13.jpg",
    "~를 무례하지 않게 말해 주세요": "meme-14.jpg",
    "삐에로 밈": "meme-15.jpg",
    "연락없네잘살아": "meme-16.jpg",
    "측측측면샷": "meme-17.jpg",
    "일하기전제모습이고요": "meme-18.jpg",
    "모르는개산책": "meme-19.jpg",
    "장투교": "meme-20.jpg",
    "니가 좋아": "meme-21.jpg",
    "난 파라파라나 추고 있어야겠다 오이데~": "meme-22.jpg",
    "띠로리 대신 띠로리리~↘": "meme-23.jpg",
    "디오 주간": "meme-24.jpg",
    "천연 위고비": "meme-25.jpg",
}


def _norm(name: str) -> str:
    return "".join((name or "").split())


# 공백 제거 기준 조회용 — 두 키가 공백만 지우면 같아지는 경우는 없었지만, 나중에
# 늘어나도 조용히 하나를 덮어쓰지 않도록 조립 시점에 확인한다.
_NORMALIZED = {}
for _name, _file in NAME_TO_FILENAME.items():
    _key = _norm(_name)
    assert _key not in _NORMALIZED, f"공백 제거 후 이름이 겹칩니다: {_name!r}"
    _NORMALIZED[_key] = _file


def main() -> None:
    init_db()
    db = SessionLocal()
    matched = 0
    deleted = []
    try:
        for row in db.query(models.Meme).all():
            filename = _NORMALIZED.get(_norm(row.meme_name))
            if filename:
                row.image = f"{IMAGE_URL_PREFIX}/{filename}"
                matched += 1
            else:
                deleted.append(f"{row.id} ({row.meme_name})")
                db.delete(row)
        db.commit()
    finally:
        db.close()

    print(f"완료 — 로컬 이미지로 교체 {matched}건, 삭제 {len(deleted)}건")
    if deleted:
        print("삭제한 행:")
        for line in deleted:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
