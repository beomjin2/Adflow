#!/usr/bin/env python3
"""memes.origin_brief를 채운다.

    cd backend && .venv/Scripts/python.exe backfill_origin_brief.py

meme_recommend.py의 "situation 하나의 후보가 너무 많을 때 먼저 추리는 호출"
(_narrow_lines)이 지금까지 유래(origin) 원문을 60자로 기계적으로 잘라 대신 써 왔는데,
그 대신 GPT로 미리 만들어 둔 짧은 요약을 쓰게 하려고 이 값을 채운다(2026-09-28 사용자
결정). 매 추천 요청마다 요약하면 호출이 늘어나므로, 크롤링 뒤 한 번만 돌려 DB에
저장해 두는 방식을 택했다.

origin_brief가 이미 채워진 밈은 건드리지 않는다 — 새로 크롤링된 밈만 대상이 된다.
한 건 실패해도 전체를 중단하지 않고 다음 밈으로 넘어간다(실패한 건 다음에 이 스크립트를
다시 돌리면 그때 채워진다 — origin_brief가 빈 채로 남아 있으니).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 한글 출력 시 깨지는 것 방지

from openai import AsyncOpenAI

from app import models
from app.core.config import settings
from app.core.database import SessionLocal, init_db

_PROMPT = (
    "밈의 유래 설명을 준다. 이 밈이 뭔지 핵심만 담아 한국어 한 문장, 30자 안팎으로 "
    "요약한다. 원문에 없는 내용은 지어내지 않는다. 요약 문장만 출력한다 — 따옴표나 "
    "다른 설명 없이."
)


def _client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 요약을 만들 수 없어요")
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)


async def _brief(client: AsyncOpenAI, origin: str) -> str:
    resp = await client.chat.completions.create(
        model=settings.openai_meme_model,
        # gpt-5-mini는 temperature 커스텀 값을 못 받는다(기본값 1만 허용) — 뺀다
        # (meme_recommend.py와 같은 이유).
        reasoning_effort="minimal",
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": origin},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def main() -> None:
    init_db()  # origin_brief 컬럼이 아직 없는 구버전 DB면 여기서 ALTER TABLE로 붙는다.
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Meme)
            .filter(models.Meme.origin != "", models.Meme.origin_brief == "")
            .all()
        )
        if not rows:
            print("채울 밈이 없어요 — 전부 이미 채워져 있거나 유래가 빈 밈뿐이에요.")
            return

        print(f"{len(rows)}건 요약 시작…")
        client = _client()
        done = failed = 0
        for row in rows:
            try:
                brief = await _brief(client, row.origin)
                if brief:
                    row.origin_brief = brief
                    done += 1
                else:
                    failed += 1
                    print(f"  빈 응답: {row.id} ({row.meme_name})")
            except Exception as e:
                failed += 1
                print(f"  실패: {row.id} ({row.meme_name}) — {e}")
        db.commit()
        print(f"완료 — {done}건 채움, {failed}건 실패(다음에 다시 돌리면 그 밈만 재시도됨)")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
