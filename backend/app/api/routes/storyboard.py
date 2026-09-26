"""광고 구성(스토리보드) 대화.

두 가지가 빠져 있다. 의도한 것이다.
- **트렌드 조사**: 제거됐다. 어디서 가져왔는지 댈 수 없는 순위·조회수를 근거로
  사장님에게 광고를 권할 수는 없다.
- **광고 이미지 생성**: 컷 구성이 정해진 뒤 `POST /comic`으로만 만든다(MVP). 확정한
  캐릭터 그림을 참조로 넣어 컷마다 한 장씩 백그라운드에서 그린다. 대사·글자는 그림에
  넣지 않는다 — 그림 모델은 글자를 못 쓴다.

컷 구성은 **사장님이 쓴 말을 GPT가 컷으로 나눈 것**이다(`story_llm.plan_from_text`).
템플릿은 없다. 키가 없거나 호출이 실패하면 예전 경로 — 문장부호에서 자르는
`_cuts_from_text` — 로 조용히 되돌아간다. 어느 쪽이든 만든 구성을 바로 반영하지 않고
confirm 카드로 올려 사장님이 승인해야 plan이 된다. 서비스가 문장을 만드는 자리라 그렇다.

스토리 제안은 자동으로 뜨지 않는다 — 사장님이 직접 적거나(POST /chat), 대화창의
"스토리 제안받기" 버튼을 눌러야(POST /suggest) 만든다. 밈은 트렌드 화면에서 미리
골라 왔을 때만(`Storyboard.trend_meme_id`) 반영한다 — 안 골랐으면 밈 얘기 자체를
꺼내지 않는다. GPT가 크롤링된 밈 중 스스로 골라 끼워 넣게 하면 사장님이 고른 적
없는 밈이 광고에 섞일 수 있어서다. 카드를 만들거나 고르는 별도 화면도 없다.

대화 중에 밈을 새로 추천받고 싶으면 "밈 추천받기" 버튼을 눌러야(POST /recommend-meme)
한다 — 이때는 지금까지 사장님이 대화에서 쓴 문장을 근거로 trend/recommend.py와 같은
GPT 추천(meme_recommend.recommend)을 한 번 더 돌린다. 결과도 confirm 카드로 올려
승인해야 trend_meme_id가 바뀐다(kind="meme").

생산 기록은 대화에서도 남길 수 있다 — 단 **물어보고 승인해야** 남는다(`_offer_record`).
예전엔 정규식이 대화 첫 마디를 훑어 **사장님 모르게** 기록을 만들었고, 그건 PR #37에서
통째로 지웠다. 지금 것은 그 되돌리기가 아니다. 다른 점이 둘이다:
- 확인 카드를 띄우고 사장님이 눌러야 DB에 들어간다.
- **스토리와 갈라지지 않는다.** "소금빵 50개 구웠어요"는 기록이면서 동시에 스토리
  소재라, 기록 카드는 곁들임으로 붙고 스토리는 그대로 만들어진다.
"내 정보 > 생산 기록" 탭은 그대로 있다 — 자리가 하나 늘었을 뿐이다.
"""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import settings
from app.core.database import get_db
from app.services import comic_bake, director, instagram, jobs, sign_check, story_llm, trace
from app.services.chat_ai import (COMIC_GLOBAL_TAGS, COMIC_IDENTITY_FIELDS, character_part, comic_prompt,
                                  comic_prompt_slots, new_pid)
from app.services.danbooru_lookup import verify_tags
from app.services.image_gen import _save_png, generate_images
from app.services.meme_recommend import recommend as recommend_meme

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"])

MAX_CUTS = 4

# 문장 끝 또는 줄바꿈에서 자른다. 사장님이 "손님이 들어온다. 빵을 본다." 처럼 쓰면
# 그대로 두 컷이 된다.
_SPLIT_RE = re.compile(r"[\n.!?·]+|,\s*(?=그리고|그다음|그 다음|마지막)")


def _get(db: Session) -> models.Storyboard:
    sb = db.get(models.Storyboard, 1)
    if not sb:
        raise HTTPException(404, "storyboard row missing")
    return sb


def _require_character(db: Session) -> models.Character:
    """스토리를 만드는 자리(POST /chat의 스토리 단계, POST /suggest)는 전부 여기부터 거친다.

    광고 설정을 확정할 때(POST /api/ad/apply)도 캐릭터 확정을 이미 확인하지만, 그건
    스토리보드에 들어오는 시점의 검사다 — 들어온 뒤에 캐릭터를 다시 고치거나 초기화하면
    이 화면은 그대로 열려 있을 수 있다. 스토리는 마스코트 정보(이름·외형 등)를 그대로
    쓰므로, 만드는 순간에도 한 번 더 확인한다.
    """
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 스토리에 마스코트 정보가 들어가요")
    return char


def reset_storyboard(db: Session, trend_meme_id: str | None = None) -> models.Storyboard:
    """광고 설정을 확정했을 때 스토리보드를 처음 상태로 되돌린다.

    trend_meme_id — 트렌드 화면에서 미리 골라 온 밈(있으면). 이번 광고 내내 대화가
    참고한다(_meme_context 참고).

    스토리 제안은 자동으로 뜨지 않는다 — 사장님이 대화창에 직접 적거나, "스토리
    제안받기" 버튼을 눌러야(POST /api/storyboard/suggest) 만든다.
    """
    sb = _get(db)
    sb.messages = []
    sb.plan = []
    sb.comic_cuts = []
    sb.pending = {}
    sb.trend_meme_id = trend_meme_id or ""
    meme = db.get(models.Meme, trend_meme_id) if trend_meme_id else None
    sb.trend_meme_name = meme.meme_name if meme else ""
    sb.caption = ""
    db.commit()
    db.refresh(sb)
    return sb


def set_trend_meme(db: Session, trend_meme_id: str | None) -> models.Storyboard:
    """대화는 그대로 두고 참고할 밈만 바꾼다.

    `reset_storyboard`와 짝이다. 광고 설정을 다시 확정해도 **컷 수가 그대로면 대화를
    지우지 않는다**(ad.apply_ad 참고) — 그때 밈만 맞춰 넣으려고 따로 뒀다.
    """
    sb = _get(db)
    sb.trend_meme_id = trend_meme_id or ""
    meme = db.get(models.Meme, trend_meme_id) if trend_meme_id else None
    sb.trend_meme_name = meme.meme_name if meme else ""
    db.commit()
    db.refresh(sb)
    return sb


def _cuts_from_text(text: str) -> list[dict]:
    """사장님이 쓴 문장을 컷으로 쪼갠다. 한 문장이면 한 컷이다."""
    parts = [p.strip() for p in _SPLIT_RE.split(text or "")]
    parts = [p for p in parts if p][:MAX_CUTS]
    return [
        {"n": i + 1, "short": p[:14], "line": p}
        for i, p in enumerate(parts)
    ]


def _chat_note(messages: list[dict]) -> str:
    """대화창에서 사장님이 직접 쓴 문장만 모아 이어 붙인다. "스토리 제안받기"·"밈
    추천받기" 둘 다 버튼을 눌렀을 때 지금까지 나눈 얘기를 재료로 쓰려고 같이 쓴다."""
    return " ".join(
        (m.get("text") or "") for m in messages if m.get("role") == "me" and m.get("kind") == "text"
    ).strip()


def _meme_context(sb: models.Storyboard, db: Session) -> dict | None:
    """트렌드 화면에서 미리 골라 온 밈이 있을 때만 그걸 돌려준다. 안 골랐으면 None —
    GPT가 스스로 후보를 뒤져 끼워 넣게 하면 사장님이 고른 적 없는 밈이 광고에 섞일 수 있다."""
    if sb.trend_meme_id:
        m = db.get(models.Meme, sb.trend_meme_id)
        if m:
            return {"id": m.id, "name": m.meme_name, "origin": m.origin,
                    "usage_example": m.usage_example}
    return None


def _plan_context(sb: models.Storyboard, db: Session) -> dict:
    """LLM에 넘길 재료를 DB에서 한 번에 읽어 둔다.

    🔴 **읽기를 여기서 끝내는 이유가 있다.** 제안 여러 개를 동시에 만들 때
    (`_propose_options`) 스레드마다 DB를 건드리면 안 된다 — SQLAlchemy 세션은
    스레드 안전하지 않다. 그래서 스레드에는 이 dict만 넘긴다. `story_llm`은 HTTP
    호출뿐이라 스레드에서 돌아도 된다.
    """
    store = db.get(models.Store, 1)
    char = db.get(models.Character, 1)
    ad = db.get(models.AdSettings, 1)
    prods = (
        db.query(models.ProductionRecord)
        .order_by(models.ProductionRecord.id.desc()).limit(10).all()
    )
    return {
        "store": {"category": store.category, "address": store.address,
                  "hours": store.hours, "desc": store.desc} if store else {},
        "char": {"name": char.name, "look": char.look, "outfit": char.outfit,
                 "desc": char.desc} if char else {},
        "ad": {"ad_type": ad.ad_type, "ad_concept": ad.ad_concept} if ad else {},
        "prods": [{"name": p.name, "qty": p.qty, "date": p.date, "time": p.time,
                   "sold_out": p.sold_out} for p in prods],
        "current_plan": list(sb.plan or []),
        "trend_meme": _meme_context(sb, db),
    }


def _plan_with(ctx: dict, text: str) -> tuple[list[dict], dict | None] | None:
    """재료 + 사장님 문장 → (컷 구성, 반영한 밈). **DB를 안 건드린다** — 스레드에서 불러도 된다.

    GPT를 못 쓰면(키 없음·호출 실패·형식 이상) 문장부호에서 자르는 옛 규칙으로 조용히
    되돌아간다(이땐 밈은 반영 안 됨).

    **None은 "규칙으로도 되돌아가지 않는다"는 뜻이다.** GPT가 "알릴 거리가 없다"고
    본 경우에만 나온다 — 그때 규칙으로 쪼개면 "안녕하세요"가 1컷이 되어 버린다.
    """
    # 뜯어보기(trace) — 광고 하나가 만들어지는 단계를 통째로 남긴다. 그림 단계가
    # 컷의 trace_id 를 보고 이어 쓴다. trace 는 threading.local 이라 제안 여러 개를
    # 병렬로 만들 때도 스레드마다 따로 잡힌다(_propose_options).
    tr = trace.Tracer.start(kind="comic", text=text[:80])
    tr.step("입력 모으기", who="code", said=text, store=ctx.get("store"), character=ctx.get("char"),
            ad=ctx.get("ad"), production=ctx.get("prods"), trend_meme=ctx.get("trend_meme"),
            current_plan=ctx.get("current_plan"))
    with trace.use(tr):
        proposed = story_llm.plan_from_text(text, **ctx)

    if proposed is None:
        cuts = _cuts_from_text(text)
        tr.step("대사 정리", who="code", note="GPT 를 못 써 문장부호로 잘랐다", cuts=cuts)
        return [{**c, "trace_id": tr.run_id} for c in cuts], None
    if not proposed["cuts"]:
        tr.step("대사 정리", who="code", note="GPT 가 광고 내용이 아니라고 봄")
        return None
    tr.step("대사 정리", who="code", cuts=proposed["cuts"], meme_used=proposed["meme_used"],
            view=f"/api/debug/trace/{tr.run_id}/view")
    return [{**c, "trace_id": tr.run_id} for c in proposed["cuts"]], proposed["meme_used"]


def _plan_cuts(text: str, sb: models.Storyboard, db: Session) -> tuple[list[dict], dict | None] | None:
    """재료를 읽고 컷 구성을 한 번 만든다. 한 건만 만들 때 쓰는 기존 입구다."""
    return _plan_with(_plan_context(sb, db), text)


def _generate_caption(sb: models.Storyboard, db: Session) -> str | None:
    """확정된 plan으로 SNS 캡션을 새로 쓴다. POST /confirm에서 kind="plan"을 승인할
    때마다 부른다 — 컷이 바뀔 때마다 캡션도 그 내용에 맞게 다시 써야 한다."""
    store = db.get(models.Store, 1)
    char = db.get(models.Character, 1)
    ad = db.get(models.AdSettings, 1)
    prods = (
        db.query(models.ProductionRecord)
        .order_by(models.ProductionRecord.id.desc()).limit(10).all()
    )
    trend_meme = _meme_context(sb, db)
    return story_llm.generate_caption(
        store={"category": store.category, "address": store.address,
               "hours": store.hours, "desc": store.desc} if store else {},
        char={"name": char.name, "look": char.look, "outfit": char.outfit,
              "desc": char.desc} if char else {},
        ad={"ad_type": ad.ad_type, "ad_concept": ad.ad_concept} if ad else {},
        prods=[{"name": p.name, "qty": p.qty, "date": p.date, "time": p.time,
                "sold_out": p.sold_out} for p in prods],
        plan=list(sb.plan or []),
        trend_meme=trend_meme,
    )


def _propose_intro(meme_used: dict | None) -> str:
    if meme_used:
        return (
            f"'{meme_used['name']}' 밈도 참고해서 스토리를 만들었어요. "
            "마음에 들면 아래에서 이대로 바꾸기를 눌러주세요."
        )
    return "스토리를 만들었어요. 마음에 들면 아래에서 이대로 바꾸기를 눌러주세요."


def _plan_diffs(sb: models.Storyboard, cuts: list[dict]) -> list[dict]:
    """"이렇게 바뀝니다"에 쓸 before→after. 확인 카드와 제안 카드가 같이 쓴다."""
    current = list(sb.plan or [])
    diffs = []
    for cut in cuts:
        before = next((c["line"] for c in current if c.get("n") == cut["n"]), "아직 없음")
        action = cut.get("action") or ""
        diffs.append({
            "label": f"{cut['n']}컷",
            "from": before,
            "to": f"{cut['line']} — {action}" if action else cut["line"],
        })
    for old in current[len(cuts):]:
        diffs.append({"label": f"{old['n']}컷", "from": old["line"], "to": "삭제"})
    return diffs


def _propose_plan(sb: models.Storyboard, cuts: list[dict], messages: list[dict]) -> None:
    """만든 컷 구성을 확인 카드로 올린다. 승인하기 전까지 plan은 바뀌지 않는다."""
    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {
        "which": "sb", "kind": "plan", "diffs": _plan_diffs(sb, cuts),
        "payload": {"plan": cuts}, "status": "open",
    }
    sb.pending = pending
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


def _kst_now() -> datetime:
    """한국 시간. 서버는 UTC라 그냥 now()를 쓰면 **한국 시간 오전 9시 전에 날짜가 하루 밀린다**
    — 새벽에 빵을 굽는 가게가 많아서 그대로 쓰면 기록이 어제로 남는다.
    (프론트의 `today()`가 같은 이유로 toISOString()을 안 쓴다.)"""
    return datetime.now(timezone(timedelta(hours=9)))


def _offer_record(sb: models.Storyboard, rec: dict | None, messages: list[dict]) -> None:
    """사장님 말에 "무엇을 몇 개 만들었다"가 있으면 **기록으로 남길지 물어본다.**

    🔴 **스토리와 갈라지지 않는다.** "소금빵 50개 구웠어요"는 생산 기록이면서 동시에
    스토리 소재다. 여기서 분기해 기록만 만들면 #42에서 고친 것(그 문장이 스토리를
    만드는 것)이 도로 깨진다. 기록 카드는 **곁들임**이지 갈림길이 아니다 — 안 눌러도
    스토리는 그대로 나온다.

    PR #37이 지운 것과 다른 물건이다. 거기서 지운 건 정규식이 대화를 훑어 **사장님
    모르게** 기록을 만들던 코드였다. 여기는 **물어보고 승인해야** 남는다.

    rec — 호출부가 스토리 만들기와 **병렬로** 미리 뽑아 둔 것(story_llm.extract_record).
    여기서 다시 부르면 순차가 되어 사장님이 기다리는 시간이 늘어난다.
    """
    if not rec:
        return

    now = _kst_now()
    when = now - timedelta(days=1) if rec["when"] == "yesterday" else now
    date = when.strftime("%Y-%m-%d")
    qty_label = f" {rec['qty']}개" if rec["qty"] else ""

    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {
        "which": "sb", "kind": "prod_add",
        "diffs": [{
            "label": "생산 기록",
            "from": "아직 없음",
            "to": f"{rec['name']}{qty_label} · {date} {now.strftime('%H:%M')}",
        }],
        "payload": {"name": rec["name"], "qty": rec["qty"],
                    "date": date, "time": now.strftime("%H:%M"), "sold_out": ""},
        "status": "open",
    }
    sb.pending = pending
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})


def _offer_store_edit(sb: models.Storyboard, db: Session, edit: dict, messages: list[dict]) -> bool:
    """사장님 말이 가게 정보를 고치라는 말이면 before→after 카드를 띄운다. 띄웠으면 True.

    🔴 **저장 잠금(store.saved)을 여기서 존중하지 않는다.** 처음엔 잠겨 있으면
    가게 화면으로 보내려 했는데, 광고를 만들 때쯤이면 `store.saved`는 **항상 참**이다
    (저장해야 다음 단계로 넘어간다). 그대로 두면 이 기능이 영영 안 도는 셈이라
    허용하기로 했다. 잠금은 **실수로 바뀌는 것**을 막으려는 것이고, 여기는
    before→after를 보여주고 사장님이 눌러야 바뀐다 — 실수가 아니다.

    그래도 가게 정보는 **덮어쓰기**라 생산 기록보다 한 겹 더 조인다. 카드에
    `basis`로 **사장님이 한 말 그대로**를 같이 보여준다(story_llm.extract_store_edit).
    """
    store = db.get(models.Store, 1)
    if not store:
        return False

    def show(value) -> str:
        if isinstance(value, list):
            return ", ".join(value) if value else "쉬는 날 없음"
        return str(value or "").strip() or "비어 있음"

    diffs = [
        {"label": story_llm.STORE_FIELDS[f], "from": show(getattr(store, f, "")), "to": show(v)}
        for f, v in edit["fields"].items()
    ]
    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {
        "which": "sb", "kind": "store_edit", "diffs": diffs, "basis": edit["basis"],
        "payload": {"fields": edit["fields"]}, "status": "open",
    }
    sb.pending = pending
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})
    return True


# 밈 추천도 하나만 던지면 "이게 최선인가"를 확인할 길이 없다. 셋을 놓고 고르게 한다.
MEME_OPTIONS = 3


# "밈"만으로는 안 가른다 — "이 밈으로 광고 만들어줘"는 지금 쓰는 밈을 쓰라는 말이지
# 새로 추천해 달라는 말이 아니다. **고르는 동작**을 뜻하는 말이 같이 있어야 한다.
_ASKS_MEME = re.compile(r"밈.{0,12}(추천|골라|골러|바꿔|바꾸|다른|새로|말고)|(추천|골라|바꿔|다른|새로).{0,12}밈")


def _asks_for_meme(text: str) -> bool:
    """사장님이 말로 밈을 추천해 달라고 했는가.

    LLM 호출을 하나 더 늘리지 않으려고 글자로 가른다. 여기서 못 잡아도 "밈 추천받기"
    버튼이 그대로 있으니 손해가 없고, 잘못 잡으면 밈 카드가 뜰 뿐 무엇도 안 바뀐다
    (고르는 건 여전히 사장님이다). 그래서 이 자리에는 글자 판단이 맞다.
    """
    return bool(_ASKS_MEME.search(text or ""))


def _shown_meme_ids(sb: models.Storyboard) -> set[str]:
    """이 대화에서 이미 보여준 밈 id.

    "밈 추천받기"를 다시 누르면 **다른 밈이 나와야 한다.** 그런데 같은 가게 정보로
    같은 후보를 넘기면 GPT는 거의 같은 답을 낸다(temperature 0.4 로는 안 흔들린다).
    그래서 이미 보여준 것을 후보에서 빼고 부른다.

    지금 참고 중인 밈(trend_meme_id)도 뺀다 — 쓰고 있는 걸 또 권하면 추천이 아니다.
    """
    ids = {sb.trend_meme_id} if sb.trend_meme_id else set()
    for m in list(sb.messages or []):
        if m.get("kind") != "meme_options":
            continue
        for it in m.get("items") or []:
            mid = ((it or {}).get("meme") or {}).get("id")
            if mid:
                ids.add(mid)
    return ids


def _meme_card(meme: models.Meme) -> dict:
    """대화창에서 밈을 설명할 때 쓰는 한 장. 트렌드 화면이 보여주는 것과 **같은 원본**이다
    (요약해 둔 카드가 따로 없다 — models.Meme 참고).

    유래·활용예시를 자르지 않고 그대로 넘긴다. 사장님이 "이 밈이 뭔데?"를 묻는 자리라
    여기서 줄이면 결국 트렌드 화면으로 돌아가야 한다.
    """
    return {
        "id": meme.id, "name": meme.meme_name, "situation": meme.situation or "",
        "origin": meme.origin or "", "usage_example": meme.usage_example or "",
        "image": meme.image or "", "source_label": meme.source_label or "",
        "url": meme.url or "", "published": meme.published_date or "",
        "period_start": meme.period_start or "", "period_end": meme.period_end or "",
        "peak_date": meme.peak_date or "", "views": meme.views,
    }


# 제안 하나당 LLM 호출이 하나다. 늘리면 사장님이 기다리는 시간과 비용이 같이 는다.
MAX_OPTIONS = 3

_NOTHING_TO_USE = (
    "아직 광고에 쓸 게 없어요. 가게 정보나 생산 기록을 먼저 채워주시면 스토리를 만들어 드릴게요."
)


def _topic_seeds(sb: models.Storyboard, db: Session) -> list[tuple[str, str]]:
    """제안할 스토리의 씨앗 — (딱지, 사장님 말처럼 쓴 한 문장).

    🔴 **전부 DB에 실제로 있는 것에서만 뽑는다.** 비어 있는 칸은 씨앗이 안 된다 —
    여기서 없는 소재를 지어내면 사장님이 정한 적 없는 광고가 된다. 씨앗이 하나도
    없으면 제안하지 않고 정보를 채우러 보낸다(`_NOTHING_TO_USE`).

    🔴 **씨앗은 "~을 알리고 싶어" 꼴로 쓴다.** story_llm은 두 가지를 되묻는데,
    씨앗 문구가 둘 중 어느 쪽에도 안 걸리게 해야 한다:

    · 명사구 하나("오픈시간") — 말하다 만 말로 본다. 그래서 서술어를 붙인다.
    · **요청형("우리 가게를 소개하고 싶어")** — 자기한테 해 달라는 말로 읽고 거절한다.
      실측으로 3/3 거절이었다. 같은 뜻인 "우리 가게 소개를 알리고 싶어"는 3/3 통과다.
      **"무엇을" 알릴지가 목적어로 드러나야 한다.**
    """
    seeds: list[tuple[str, str]] = []

    # 사장님이 이미 쓴 말이 있으면 그게 1순위 씨앗이다.
    note = _chat_note(list(sb.messages or []))
    if note:
        seeds.append(("사장님이 쓴 내용", note))

    prod = (
        db.query(models.ProductionRecord)
        .order_by(models.ProductionRecord.id.desc()).first()
    )
    if prod and (prod.name or "").strip():
        qty = f" {prod.qty}개" if (prod.qty or "").strip() else ""
        seeds.append((prod.name.strip(), f"{prod.name.strip()}{qty} 만들었어요"))

    store = db.get(models.Store, 1)
    if store and (store.hours or "").strip():
        seeds.append(("영업시간", "우리 가게 영업시간을 알리고 싶어"))
    if store and (store.desc or "").strip():
        seeds.append(("가게 소개", "우리 가게 소개를 알리고 싶어"))

    meme = _meme_context(sb, db)
    if meme and (meme.get("name") or "").strip():
        name = meme["name"].strip()
        # "밈으로 광고를 만들고 싶어"는 0/3 거절이었다(요청형). 목적어 "우리 가게를"이
        # 들어간 이 문구가 3/3 통과다. 위 규칙 그대로다.
        seeds.append((f"{name} 밈", f"'{name}' 밈으로 우리 가게를 알리고 싶어"))

    return seeds[:MAX_OPTIONS]


def _propose_options(
    sb: models.Storyboard, db: Session, messages: list[dict], intro: str,
) -> int:
    """씨앗마다 스토리를 하나씩 만들어 **고를 수 있는 제안 카드**로 올린다. 만든 개수를 돌려준다.

    되묻기를 없애는 게 아니라 막다른 길만 없앤다 — 고르는 건 여전히 사장님이고,
    누르기 전까지 plan은 안 바뀐다.

    🔴 **반드시 병렬로 부른다.** 씨앗이 셋이면 순차는 15초고 병렬은 5초다.
    하나가 실패해도 나머지로 보여준다.
    """
    seeds = _topic_seeds(sb, db)
    if not seeds:
        return 0
    ctx = _plan_context(sb, db)  # DB 읽기는 스레드 밖에서 끝낸다 (_plan_context 참고)

    def one(seed: tuple[str, str]):
        try:
            return _plan_with(ctx, seed[1])
        except Exception:
            logger.exception("제안 하나를 만들지 못했습니다: %s", seed[0])
            return None

    with ThreadPoolExecutor(max_workers=len(seeds)) as pool:
        results = list(pool.map(one, seeds))

    pending = dict(sb.pending or {})
    group = new_pid()
    items = []
    for (label, _seed), result in zip(seeds, results):
        if not result or not result[0]:
            continue
        cuts = result[0]
        pid = new_pid()
        pending[pid] = {
            # group — 하나를 고르면 같은 묶음의 나머지를 닫는 데 쓴다(confirm_pending).
            "which": "sb", "kind": "plan", "group": group,
            "diffs": _plan_diffs(sb, cuts),
            "payload": {"plan": cuts}, "status": "open",
        }
        items.append({
            "pid": pid, "topic": label,
            "cuts": [{"n": c["n"], "line": c["line"]} for c in cuts],
        })

    if not items:
        return 0
    sb.pending = pending
    messages.append({"role": "ai", "kind": "text", "text": intro})
    messages.append({"role": "ai", "kind": "options", "group": group, "items": items})
    return len(items)


@router.get("", response_model=schemas.StoryboardOut)
def get_storyboard(db: Session = Depends(get_db)):
    return schemas.storyboard_out(_get(db), jobs.queue_depth())


@router.post("/chat", response_model=schemas.StoryboardOut)
def chat(body: schemas.ChatIn, db: Session = Depends(get_db)):
    """스토리보드 채팅 — 사장님이 쓴 내용으로 컷 구성을 만든다.

    한 번의 대화가 세 가지를 할 수 있다. 무엇이든 **바로 반영하지 않고 카드로 물어본다.**

    1. **스토리** — 늘 하던 일. 컷 구성을 만들어 confirm 카드로 올린다.
    2. **생산 기록**(곁들임) — "소금빵 50개 구웠어요"처럼 만든 사실이 섞여 있으면
       기록으로 남길지 같이 물어본다. **스토리와 갈라지지 않는다**(`_offer_record`).
    3. **가게 정보 수정** — "오픈시간 9시로 바꿔줘"처럼 고치라는 말이면 before→after
       카드를 띄운다. 이건 광고 소재가 아니라서 **갈라진다**(`_offer_store_edit`).

    🔴 셋을 **병렬로** 부른다. 순차로 이으면 사장님이 기다리는 시간이 그대로 세 배다.
    호출 수는 늘지만(메시지당 3회) 기다리는 시간은 그대로다 — 실측 1.9초.

    🔴 **가게 정보 수정이 스토리보다 먼저다.** 처음엔 "고쳐 달라는 말은 광고 소재가
    아니니 스토리 쪽에서 거절될 것"이라 보고 거절 뒤에만 확인했는데, 재보니 틀렸다.
    "오픈시간 9시로 바꿔줘"에 스토리 쪽은 3/3으로 컷을 만들었고, 그 내용이
    **"오픈시간이 9시로 바뀌었어요!"** 였다 — 아직 바꾸지도 않은 것을 광고로 내보낼
    뻔했다. 그래서 수정으로 읽히면 스토리를 만들지 않는다.
    """
    sb = _get(db)
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "내용을 입력해주세요")

    messages = list(sb.messages or [])
    messages.append({"role": "me", "kind": "text", "text": text})

    _require_character(db)
    # DB 읽기를 먼저 끝내고 스레드에는 dict만 넘긴다(_plan_context 참고).
    ctx = _plan_context(sb, db)
    with ThreadPoolExecutor(max_workers=3) as pool:
        planned = pool.submit(_plan_with, ctx, text)
        extracted = pool.submit(story_llm.extract_record, text)
        store_edit = pool.submit(story_llm.extract_store_edit, text)
        result = planned.result()
        record = extracted.result()
        edit = store_edit.result()

    if edit:
        # 가게 정보를 고치라는 말이다. 스토리는 만들지 않는다 — 위 docstring 참고.
        _offer_store_edit(sb, db, edit, messages)
    elif result is None:
        # GPT가 "알릴 거리가 없다"고 본 경우다("뭐 만들까?"·인사·"몰라").
        # 여기서 아무 장면이나 만들면 사장님이 말한 적 없는 광고가 된다 — 지어내지 않는다.
        #
        # 대신 **막다른 길로 두지도 않는다.** 전에는 "한 줄로 적어주세요"만 돌려줘서,
        # 무엇을 적을 수 있는지 모르는 사장님이 같은 말을 고쳐 쓰다 또 거절당했다.
        # 이제 실제 데이터에서 뽑은 씨앗으로 스토리를 몇 개 만들어 보여준다 —
        # 고르는 건 여전히 사장님이고, 누르기 전까지 plan은 안 바뀐다.
        #
        # _topic_seeds가 읽는 sb.messages에는 방금 그 말이 아직 안 들어 있다(맨 끝에서
        # 한 번에 저장한다). 그래서 방금 거절당한 문장이 씨앗으로 다시 들어가지 않는다.
        # "다른 밈 추천해줘" 같은 말은 스토리 소재가 아니라 여기(거절)로 떨어진다.
        # 버튼을 말로 누른 것이므로 같은 함수를 부른다. _recommend_memes 는 async 라
        # 여기서 새 루프로 돌린다 — chat 은 sync 라 FastAPI 가 스레드풀에서 부르고,
        # 그 스레드에는 도는 루프가 없어서 asyncio.run 이 안전하다.
        if _asks_for_meme(text):
            asyncio.run(_recommend_memes(sb, db, messages))
        elif not _propose_options(
            sb, db, messages,
            "무엇을 알릴지 아직 못 잡았어요. 이런 스토리는 어떠세요? 마음에 드는 걸 골라주세요.",
        ):
            messages.append({"role": "ai", "kind": "text", "text": _NOTHING_TO_USE})
    else:
        cuts, meme_used = result
        if not cuts:
            messages.append({
                "role": "ai", "kind": "text",
                "text": "어떤 장면인지 한 문장으로 적어주세요. 문장 하나가 한 컷이 돼요.",
            })
        else:
            messages.append({"role": "ai", "kind": "text", "text": _propose_intro(meme_used)})
            _propose_plan(sb, cuts, messages)
            # 스토리를 만든 **뒤에** 곁들인다. 순서가 중요하다 — 기록 카드가 먼저 뜨면
            # 사장님이 스토리보다 기록을 먼저 보게 되고, 대화의 주인공이 바뀐다.
            _offer_record(sb, record, messages)

    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.put("/plan", response_model=schemas.StoryboardOut)
def update_plan(body: schemas.PlanUpdate, db: Session = Depends(get_db)):
    """사장님이 컷을 **직접** 고친다. 캐릭터 시트의 "수정하기"와 같은 자리다.

    대화로만 고칠 수 있으면 한 글자 바꾸려고 문장을 새로 말해야 하고, 그러면 GPT가
    나머지 컷까지 다시 쓴다. 손으로 고치는 길이 따로 있어야 한다.

    확인 카드를 안 거친다 — 사장님이 직접 친 글자다. 지어낼 여지가 없다.
    """
    sb = _get(db)
    current = {c.get("n"): dict(c) for c in (sb.plan or [])}
    for patch in body.cuts:
        cut = current.get(patch.n)
        if cut is None:
            continue
        if patch.line is not None:
            cut["line"] = patch.line.strip()
            # short 는 목록에서 줄여 보여줄 때 쓰는 값이라 대사를 고치면 같이 따라가야 한다.
            cut["short"] = cut["line"][:14]
        if patch.action is not None:
            cut["action"] = patch.action.strip()
        if patch.camera is not None:
            # 여섯 개 태그 아니면 통째로 버리고 "지정 안 함"으로 둔다. 화면이 뱃지로만
            # 고르게 해도, 라우터는 화면을 안 믿는다(_invents_numbers 와 같은 태도).
            camera = patch.camera.strip()
            cut["camera"] = camera if camera in story_llm.CAMERA_TAGS else ""
        current[patch.n] = cut
    sb.plan = [current[n] for n in sorted(current)]

    # 캡션은 확정된 컷으로 쓴 글이라 컷이 바뀌면 같이 다시 쓴다(confirm 과 같은 규칙).
    # 실패해도 조용히 빈 문자열이고, 화면이 옛 방식(컷 이어붙이기)으로 대신 보여준다.
    sb.caption = _generate_caption(sb, db) or ""
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


def _bake_poster(db: Session) -> str:
    """네컷 + 대사를 **한 장으로 구워** 내려받을 URL을 돌려준다.

    화면의 말풍선은 프론트가 그림 위에 얹은 CSS 레이어라, "이미지 저장"으로 받으면
    ComfyUI 원본만 받아져 **대사가 통째로 사라진다.** 여기서 굽는다.

    굽는 쪽은 `comic_bake` 다 — 말풍선을 캐릭터 반대편에 두고 3배로 그려 줄인다.
    """
    sb = _get(db)
    cuts = [c for c in (sb.comic_cuts or []) if c.get("status") == "done" and c.get("image")]
    if not cuts:
        raise HTTPException(400, "먼저 네컷을 그려주세요")

    by_n = {c.get("n"): c for c in (sb.plan or [])}
    paths, lines = [], []
    for c in sorted(cuts, key=lambda x: x.get("n") or 0):
        name = str(c["image"]).rsplit("/", 1)[-1]
        path = settings.media_path / name
        if not path.exists():
            logger.warning("네컷 파일이 사라졌습니다: %s", name)
            continue
        paths.append(path)
        lines.append((by_n.get(c.get("n")) or {}).get("line", ""))

    if not paths:
        raise HTTPException(400, "그림 파일을 찾지 못했어요. 네컷을 다시 그려주세요")

    try:
        return comic_bake.compose_poster(paths, lines)
    except Exception:
        logger.exception("완성본 합성 실패")
        raise HTTPException(500, "완성본을 만들지 못했어요")


@router.post("/poster")
def make_poster(db: Session = Depends(get_db)):
    """완성본을 굽고 내려받을 URL을 돌려준다. 굽는 일은 _bake_poster 가 한다
    (인스타 게시도 같은 완성본을 써야 해서 갈라 뒀다)."""
    return {"image": _bake_poster(db)}


def _instagram_status(db: Session) -> schemas.InstagramStatusOut:
    """연결 상태 한 곳에서 만든다 — 연결/해제 뒤에도 같은 모양을 돌려주려고."""
    instagram.refresh_if_due()          # 만료가 가까우면 여기서 미리 갱신한다(실패해도 그냥 진행)
    db.expire_all()                     # 갱신이 토큰을 바꿨을 수 있다 — 다시 읽는다
    row = db.get(models.InstagramAccount, 1)
    saved = bool(row and row.user_id and row.access_token)
    expires_at = (row.expires_at if row else "") or ""
    left = instagram.days_left(expires_at)
    if not instagram.available():
        return schemas.InstagramStatusOut(connected=False, saved=saved,
                                          reason=instagram.missing_reason())
    try:
        return schemas.InstagramStatusOut(connected=True, saved=saved, expires_at=expires_at,
                                          days_left=left if left is not None else -1,
                                          username=instagram.account_name())
    except instagram.InstagramError as e:
        # 저장은 돼 있는데 토큰이 만료된 경우가 대부분이다 — 화면이 "다시 연결"을 권할 수 있게
        # saved 는 그대로 true 로 둔다.
        return schemas.InstagramStatusOut(connected=False, saved=saved, reason=str(e))


@router.get("/instagram", response_model=schemas.InstagramStatusOut)
def instagram_status(db: Session = Depends(get_db)):
    """인스타 계정이 연결됐는지. 화면은 이 값으로 게시 버튼을 보일지 정한다.

    토큰이 살아 있는지까지 확인한다 — 저장만 돼 있고 만료된 토큰이면 눌러 봐야 실패하니,
    여기서 계정 이름을 한 번 불러와 본다."""
    return _instagram_status(db)


@router.post("/instagram/connect", response_model=schemas.InstagramStatusOut)
def instagram_connect(body: schemas.InstagramConnectIn, db: Session = Depends(get_db)):
    """온보딩 화면에서 받은 사용자 ID·토큰을 저장한다.

    **저장하기 전에 인스타에 한 번 물어본다** — 값이 틀렸는데 저장해 두면, 사장님은 나중에
    게시를 눌러 보고서야 잘못됐다는 걸 알게 된다. 여기서 막고 이유를 알려준다."""
    uid = (body.user_id or "").strip()
    token = (body.access_token or "").strip()
    if not uid or not token:
        raise HTTPException(400, "사용자 ID와 액세스 토큰을 모두 넣어주세요")
    try:
        username, token, expires_at = instagram.verify(token)
    except instagram.InstagramError as e:
        raise HTTPException(400, str(e))

    row = db.get(models.InstagramAccount, 1) or models.InstagramAccount(id=1)
    row.user_id, row.access_token, row.username = uid, token, username
    row.expires_at = expires_at
    row.updated_at = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    db.add(row)
    db.commit()
    return _instagram_status(db)


@router.post("/instagram/disconnect", response_model=schemas.InstagramStatusOut)
def instagram_disconnect(db: Session = Depends(get_db)):
    """연결 끊기. 저장해 둔 토큰을 지운다 — 남의 컴퓨터에서 로그인해 둔 걸 푸는 것과 같다."""
    row = db.get(models.InstagramAccount, 1)
    if row:
        db.delete(row)
        db.commit()
    return _instagram_status(db)


@router.post("/instagram", response_model=schemas.InstagramPublishOut)
def publish_instagram(body: schemas.InstagramPublishIn, db: Session = Depends(get_db)):
    """완성본 + 캡션을 인스타에 올린다. **되돌릴 수 없다** — 화면에서 확인을 받고 부른다.

    캡션은 사장님이 화면에서 고친 것을 우선하고, 비어 있으면 GPT가 써 둔 것을 쓴다.
    올린 뒤 같은 캡션을 DB에도 남긴다 — 무엇을 올렸는지가 기록으로 남아야 한다."""
    instagram.refresh_if_due()      # 만료 직전이면 여기서 갱신하고 올린다
    sb = _get(db)
    caption = (body.caption or sb.caption or '').strip()
    url = _bake_poster(db)          # 네컷이 없으면 여기서 400 으로 막힌다
    poster = settings.media_path / url.rsplit('/', 1)[-1]
    try:
        result = instagram.publish(poster, caption)
    except instagram.InstagramError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception('인스타 게시 실패')
        raise HTTPException(500, '인스타그램에 올리지 못했어요')
    if caption and caption != (sb.caption or ''):
        sb.caption = caption
        db.commit()
    return schemas.InstagramPublishOut(**result)


@router.post("/reset", response_model=schemas.StoryboardOut)
def reset_chat(db: Session = Depends(get_db)):
    """광고 대화를 처음 상태로 되돌린다. 대화가 꼬였을 때 빠져나갈 길이 필요하다
    (캐릭터 쪽 `POST /api/character/reset`과 같은 이유·같은 모양이다).

    **트렌드 화면에서 골라 온 밈은 남긴다.** 그건 이 대화에서 정한 게 아니라 앞 화면에서
    고르고 들어온 것이라, 대화를 지운다고 사라지면 사장님이 밈을 다시 고르러 가야 한다.

    그려둔 그림 파일(media/)은 안 지운다 — 참조만 끊는다. 지우는 건 나중에도 할 수
    있지만 되돌리는 건 못 한다(캐릭터 reset과 같은 판단).

    생산 기록과 가게 정보는 **안 건드린다.** 대화로 남겼더라도 그건 이 대화의 산출물이
    아니라 가게의 기록이다.
    """
    sb = _get(db)
    return schemas.storyboard_out(
        reset_storyboard(db, sb.trend_meme_id or None), jobs.queue_depth(),
    )


@router.post("/suggest", response_model=schemas.StoryboardOut)
def suggest(db: Session = Depends(get_db)):
    """대화창의 "스토리 제안받기" 버튼 — 자동으로는 절대 안 뜬다(사장님이 버튼을
    눌러야만 부른다).

    **한 개가 아니라 여러 개를 제안한다.** 전에는 하나만 만들어 "이대로 바꿀까요?"를
    물었는데, 사장님이 할 수 있는 건 예/아니오뿐이라 마음에 안 들면 다시 막다른
    길이었다. 지금은 서로 다른 씨앗(`_topic_seeds`)으로 2~3개를 만들어 고르게 한다.

    대화에서 "뭐 만들까?"라고 말하는 것도 이 버튼을 말로 누른 것이라, `chat()`의
    거절 분기가 같은 함수를 부른다 — 버튼이든 말이든 같은 동작이어야 한다.
    """
    sb = _get(db)
    _require_character(db)
    messages = list(sb.messages or [])
    if not _propose_options(
        sb, db, messages, "이런 스토리는 어떠세요? 마음에 드는 걸 골라주세요.",
    ):
        messages.append({"role": "ai", "kind": "text", "text": _NOTHING_TO_USE})
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


async def _recommend_memes(sb: models.Storyboard, db: Session, messages: list[dict]) -> None:
    """밈을 추천해 `messages` 에 고를 수 있는 카드를 붙인다. 못 하면 이유를 글로 붙인다.

    버튼("밈 추천받기")과 말("다른 밈 추천해줘") 둘 다 여기로 온다 — 같은 요청이
    입구만 다른 것이라 같은 함수를 쓴다. 승인해야만 trend_meme_id 가 바뀐다.
    """
    note = _chat_note(messages)
    if not note:
        messages.append({
            "role": "ai", "kind": "text",
            "text": "대화에서 알릴 내용을 먼저 말씀해주시면 그걸 보고 밈을 추천해드릴게요.",
        })
        return

    # 밈 분류명을 다시 정리하면서 "미분류"도 정상적인 활용 상황 후보 중 하나로 포함한다
    # (trend.py의 /recommend와 같은 이유).
    all_memes = [m for m in db.query(models.Meme).all() if m.situation]
    if not all_memes:
        messages.append({"role": "ai", "kind": "text", "text": "지금 추천할 수 있는 밈이 없어요."})
        return

    store = db.get(models.Store, 1)
    store_desc = ""
    if store and store.saved:
        parts = [store.category, store.address, store.hours, store.desc]
        store_desc = " / ".join(p for p in parts if p)

    char = db.get(models.Character, 1)
    character_desc = ""
    if char and char.confirmed:
        parts = [char.name, char.look, char.outfit, char.abilities, ", ".join(char.keywords or []), char.desc]
        character_desc = " / ".join(p for p in parts if p)

    try:
        result = await recommend_meme(
            note, character_desc, store_desc,
            candidates=[
                {"id": m.id, "name": m.meme_name, "situation": m.situation,
                 "origin": m.origin, "usage_example": m.usage_example}
                for m in all_memes
            ],
            n=MEME_OPTIONS,
            exclude=_shown_meme_ids(sb),
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("대화 기반 밈 추천 실패")
        raise HTTPException(502, "추천을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")

    by_id = {m.id: m for m in all_memes}
    pending = dict(sb.pending or {})
    group = new_pid()
    items = []
    for pick in result["picks"]:
        meme = by_id.get(pick["meme_id"])
        if not meme:
            continue  # GPT가 후보 밖 id를 냈다 — 그 줄만 버린다
        pid = new_pid()
        pending[pid] = {
            # group — 하나를 고르면 나머지를 닫는다(confirm_pending).
            "which": "sb", "kind": "meme", "group": group,
            "diffs": [{"label": "트렌드 밈", "from": sb.trend_meme_name or "아직 없음",
                       "to": meme.meme_name}],
            "why": pick["reason"],
            "payload": {"meme_id": meme.id, "meme_name": meme.meme_name},
            "status": "open",
        }
        items.append({"pid": pid, "reason": pick["reason"], "meme": _meme_card(meme)})

    if not items:
        messages.append({"role": "ai", "kind": "text", "text": "지금 추천할 수 있는 밈이 없어요."})
    else:
        sb.pending = pending
        messages.append({
            "role": "ai", "kind": "text",
            "text": f"'{result['situation']}' 상황에 어울리는 밈 {len(items)}개를 골랐어요. "
                    "눌러서 어떤 밈인지 보고 하나만 골라주세요.",
        })
        messages.append({"role": "ai", "kind": "meme_options", "group": group, "items": items})


@router.post("/recommend-meme", response_model=schemas.StoryboardOut)
async def recommend_meme_from_chat(db: Session = Depends(get_db)):
    """대화창의 "밈 추천받기" 버튼. 자동으로는 안 뜬다 — 사장님이 눌러야 부른다."""
    sb = _get(db)
    messages = list(sb.messages or [])
    await _recommend_memes(sb, db, messages)
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


def _reference_path(char) -> Path | None:
    """확정한 후보 그림의 디스크 경로. /api/media/<파일명> URL을 media_path의 파일로 되돌린다."""
    cands = list(char.candidates or [])
    index = char.selected_index if char.selected_index is not None else -1
    if not 0 <= index < len(cands):
        return None
    image = (cands[index] or {}).get("image") or ""
    name = image.rsplit("/", 1)[-1]
    path = settings.media_path / name if name else None
    return path if path and path.is_file() else None


# 마지막 컷 규칙 — 가게 앞 전경(wide_shot) + 캐릭터 오른쪽(크롭) + 왼쪽 아래 코드 입간판.
# sign 태그는 일부러 뺀다: 넣으면 모델이 제 칠판을 그려 우리 입간판과 두 개가 된다(09-22 실측).
_STOREFRONT_TAGS = ["wide_shot", "full_body", "solo", "outdoors", "shop", "door", "standing", "waving", "smile", "looking_at_viewer"]
_SIGN_RETRIES = 2


def _storefront_prompt(char_part_text: str) -> str:
    return ", ".join(p for p in [COMIC_GLOBAL_TAGS, char_part_text, ", ".join(verify_tags(_STOREFRONT_TAGS))] if p)


def _fill_cuts(indexes: list[int], scenes: list[dict], char_part_text: str, reference: Path,
               trace_id: str | None = None, board_lines: list[str] | None = None) -> None:
    """백그라운드 본체 — 컷마다 프롬프트를 만들고 한 장씩 뽑아 comic_cuts의 칸을 채운다.
    scenes[i] = {"text", "camera", "slots"(연출, 없을 수 있음), "last": 마지막 컷인가, "n", "line"}.
    슬롯이 있으면 연출 경로(comic_prompt_slots + 위치 크롭), 없으면 옛 경로(comic_prompt).
    마지막 컷은 가게 앞 전경 + 간판 검사·재시도 + 입간판 굽기. 다 끝나면 2×2 완성본을 만든다.
    trace_id 가 있으면 제안 때 시작한 단계별 기록에 이어 쓴다(다른 스레드라 여기서 다시 잡는다)."""
    tr = trace.Tracer.resume(trace_id)
    with trace.use(tr):
        for index, scene in zip(indexes, scenes):
            slots = scene.get("slots")
            slot_trace = None
            position = None
            tries: list[dict] = []
            if scene.get("last"):
                prompt = _storefront_prompt(char_part_text)
                position = "오른쪽"
                trace.step(f"컷 {scene.get('n')} 규칙", who="code", rule="마지막 컷 = 가게 앞 전경 + 캐릭터 오른쪽 + 왼쪽 아래 입간판", prompt=prompt)
                image = None
                for attempt in range(_SIGN_RETRIES + 1):
                    images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                             reference_path=reference, position=position)
                    image = images[0] if images else None
                    if not image:
                        break
                    hit = sign_check.sign_tags(settings.media_path / image.rsplit("/", 1)[-1])
                    tries.append({"attempt": attempt + 1, "image": image, "sign_tags": hit})
                    trace.step(f"컷 {scene.get('n')} 간판 검사 {attempt + 1}회", who="wd14", image=image, sign_tags=hit,
                               verdict="검사 없음(태거 없음)" if hit is None else ("다시" if hit and attempt < _SIGN_RETRIES else "채택"))
                    if not hit:
                        break
                if image and board_lines:
                    from PIL import Image
                    src = settings.media_path / image.rsplit("/", 1)[-1]
                    baked = comic_bake.board(Image.open(src), board_lines)
                    from io import BytesIO
                    buf = BytesIO(); baked.save(buf, format="PNG")
                    image = _save_png(buf.getvalue()) or image
                    trace.step(f"컷 {scene.get('n')} 입간판 굽기", who="code", lines=board_lines, image=image)
            else:
                if slots:
                    prompt, slot_trace = comic_prompt_slots(char_part_text, slots)
                    position = (slots.get("shot") or {}).get("position")
                else:
                    prompt = comic_prompt(char_part_text, scene.get("text", ""), scene.get("camera", ""))
                trace.step(f"컷 {scene.get('n')} 프롬프트 조립", who="code", prompt=prompt, slot_to_tags=slot_trace, position=position)
                images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                         reference_path=reference, position=position)
                image = images[0] if images else None

            def write(db: Session, index=index, image=image, prompt=prompt, slot_trace=slot_trace, tries=tries):
                sb = db.get(models.Storyboard, 1)
                if not sb:
                    return
                cuts = list(sb.comic_cuts or [])
                if 0 <= index < len(cuts):
                    cuts[index] = {**cuts[index], "image": image, "status": "done" if image else "failed",
                                   "prompt": prompt, "trace": slot_trace, "tries": tries}
                    sb.comic_cuts = cuts
                    db.commit()

            jobs.with_session(write)
        _compose_if_done()


def _compose_if_done() -> None:
    """모든 컷이 done 이면 말풍선을 굽고 2×2 로 합쳐 완성본 URL 을 각 컷의 final 에 적는다."""
    from PIL import Image

    def run(db: Session):
        sb = db.get(models.Storyboard, 1)
        if not sb:
            return
        cuts = list(sb.comic_cuts or [])
        if not cuts or any(c.get("status") != "done" or not c.get("image") for c in cuts):
            return
        panels = []
        for c in cuts:
            im = Image.open(settings.media_path / c["image"].rsplit("/", 1)[-1])
            side = comic_bake.bubble_side(((c.get("slots") or {}).get("shot") or {}).get("position"), c.get("n", 1))
            panels.append(comic_bake.bubble(im, c.get("line", ""), side))
        from io import BytesIO
        buf = BytesIO(); comic_bake.compose(panels).save(buf, format="PNG")
        final = _save_png(buf.getvalue())
        sb.comic_cuts = [{**c, "final": final} for c in cuts]
        db.commit()
        trace.step("말풍선 굽기 · 2×2 합치기", who="code", final=final)

    jobs.with_session(run)


def _start_cuts(sb: models.Storyboard, char: models.Character, indexes: list[int], db: Session) -> None:
    reference = _reference_path(char)
    if reference is None:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 확정한 캐릭터 그림을 참조로 씁니다")
    cuts = list(sb.comic_cuts or [])
    last = len(cuts) - 1
    # 그림엔 대사가 아니라 동작을 넣는다(대사·글자는 말풍선 몫). 동작이 없으면(직접 쓴 컷) 대사 문장을 쓴다.
    scenes = [{"n": cuts[i].get("n", i + 1), "line": cuts[i].get("line", ""),
               "text": cuts[i].get("action") or cuts[i].get("line", ""), "camera": cuts[i].get("camera", ""),
               "slots": cuts[i].get("slots"), "last": i == last}
              for i in indexes]
    for i in indexes:
        cuts[i] = {**cuts[i], "image": None, "status": "generating", "final": None}
    sb.comic_cuts = cuts
    db.commit()
    # 입간판 글 — 가게 정보 + 최근 생산 기록
    store = db.get(models.Store, 1)
    prods = db.query(models.ProductionRecord).order_by(models.ProductionRecord.id.desc()).limit(1).all()
    board_lines = comic_bake.board_lines(
        {"hours": store.hours, "address": store.address} if store else {},
        [{"name": p.name, "qty": p.qty} for p in prods])
    # 뜯어보기: 제안 때 시작한 기록(trace_id)에 이어 쓴다. 캐릭터 태깅도 그 기록 안에.
    trace_id = next((c.get("trace_id") for c in cuts if c.get("trace_id")), None)
    tr = trace.Tracer.resume(trace_id)
    with trace.use(tr):
        trace.step("그림 단계 시작", who="code", cuts=indexes, board_lines=board_lines,
                   character_sheet={"look": char.look, "outfit": char.outfit, "age": char.age})
        # 캐릭터 태그는 여기서 한 번만 계산한다(GPT 1회). 생김새·옷·나이만(COMIC_IDENTITY_FIELDS).
        char_text = character_part(char, COMIC_IDENTITY_FIELDS)
        trace.step("캐릭터 태그 확정", who="code", character_tags=char_text)
    jobs.submit(_fill_cuts, indexes, scenes, char_text, reference, trace_id, board_lines)


@router.post("/comic", response_model=schemas.StoryboardOut)
def make_comic(db: Session = Depends(get_db)):
    """컷 구성 전부를 네컷 그림으로 뽑는다(비동기). 화면은 GET /api/storyboard를 폴링한다."""
    sb = _get(db)
    plan = list(sb.plan or [])
    if not plan:
        raise HTTPException(400, "먼저 대화로 컷 구성을 만들어주세요")
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요")
    # 연출 — 대사·상황을 그림 슬롯으로(크기·각도·위치·시선·표정…). GPT 를 못 쓰면 None → 옛 경로.
    ad = db.get(models.AdSettings, 1)
    trace_id = next((c.get("trace_id") for c in plan if c.get("trace_id")), None)
    with trace.use(trace.Tracer.resume(trace_id)):
        slots = director.direct([c.get("line", "") for c in plan], [c.get("action") or c.get("line", "") for c in plan],
                                (ad.ad_concept if ad else "") or "")
        trace.step("연출 정리", who="code", slots=slots)
    sb.comic_cuts = [
        {"n": c["n"], "short": c.get("short", ""), "line": c.get("line", ""),
         "action": c.get("action", ""), "camera": c.get("camera", ""),
         "slots": slots[i] if slots and i < len(slots) else None, "trace_id": c.get("trace_id"),
         "label": f"{c['n']}컷", "image": None, "status": "generating"}
        for i, c in enumerate(plan)
    ]
    # 네컷은 대화창 안에서 보여준다. 그림이 대화 흐름 밖에서 나오면 사장님은 무엇 때문에
    # 그게 나왔는지 놓친다. 말풍선은 comic_cuts를 그대로 비추므로 **하나만** 둔다 —
    # 다시 그려도 새 말풍선이 생기는 게 아니라 그 자리가 다시 채워진다. 안내 문구도 같이
    # 걷어내야 한다(ref로 표시해 둔다). 말풍선만 지우면 "그릴게요"가 다시 그릴 때마다
    # 한 줄씩 쌓여, 대화 기록만 보면 네 번 그린 것처럼 보인다.
    messages = [
        m for m in list(sb.messages or [])
        if m.get("kind") != "comic" and m.get("ref") != "comic-start"
    ]
    messages.append({
        "role": "ai", "kind": "text", "ref": "comic-start",
        "text": f"정해진 {len(plan)}컷을 그릴게요. 이 화면을 닫아도 서버에서 계속 그립니다.",
    })
    messages.append({"role": "ai", "kind": "comic"})
    sb.messages = messages
    _start_cuts(sb, char, list(range(len(plan))), db)
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/comic/{n}/reroll", response_model=schemas.StoryboardOut)
def reroll_cut(n: int, db: Session = Depends(get_db)):
    """컷 하나만 다시 뽑는다.

    되살린 것이다 — 2787723("컷별 리롤과 결과 화면 이미지 크기를 정리한다")이 이 라우트를
    지웠고, 00095fe 가 남아 있던 프론트 배선(ComicBubble 의 onReroll)까지 걷어냈다.
    제목만 보면 정리한 것처럼 읽히지만 실제로는 기능이 사라졌다.

    한 컷만 마음에 안 들 때 넷을 다 다시 그리면 1분을 더 기다리고, 마음에 들던
    나머지 셋도 다른 그림이 된다.
    """
    sb = _get(db)
    cuts = list(sb.comic_cuts or [])
    index = next((i for i, c in enumerate(cuts) if c.get("n") == n), None)
    if index is None:
        raise HTTPException(404, "그 컷이 없어요")
    char = db.get(models.Character, 1)
    if not char or not char.confirmed:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요")
    _start_cuts(sb, char, [index], db)
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/confirm/{pid}", response_model=schemas.StoryboardOut)
def confirm_pending(pid: str, db: Session = Depends(get_db)):
    sb = _get(db)
    pending = dict(sb.pending or {})
    p = pending.get(pid)
    if not p:
        raise HTTPException(404, "pending not found")
    if p.get("status") != "open":
        raise HTTPException(400, "이미 처리된 제안이에요")

    pending[pid] = {**p, "status": "applied"}
    # 🔴 같은 제안 묶음의 다른 카드는 닫는다. 안 닫으면 사장님이 스크롤을 올려
    # 다른 카드를 또 누를 수 있고, 그러면 방금 정한 구성이 조용히 덮어써진다.
    group = p.get("group")
    if group:
        for other_pid, other in list(pending.items()):
            if other_pid != pid and other.get("group") == group and other.get("status") == "open":
                pending[other_pid] = {**other, "status": "closed"}
    messages = list(sb.messages or [])
    if p["kind"] == "plan":
        sb.plan = p["payload"]["plan"]
        messages.append({"role": "ai", "kind": "plan", "ref": "plan"})
        # 컷 대사를 그대로 이어붙이면 SNS 톤이 안 산다 — 확정된 컷으로 캡션을 따로
        # 새로 쓴다. 실패해도(키 없음 등) 조용히 빈 문자열로 남고, 화면이 옛 방식
        # (컷 이어붙이기)으로 대신 보여준다.
        sb.caption = _generate_caption(sb, db) or ""
    elif p["kind"] == "store_edit":
        store = db.get(models.Store, 1)
        changed = []
        for field, value in p["payload"]["fields"].items():
            if field in story_llm.STORE_FIELDS:
                setattr(store, field, value)
                changed.append(story_llm.STORE_FIELDS[field])
        # 표시용 영업시간 문자열은 화면·프롬프트가 같이 읽는다. 여기서 다시 계산하지
        # 않으면 open_time만 바뀌고 "18:04 – 16:06"은 옛날 값으로 남는다.
        from app.api.routes.store import _format_hours
        store.hours = _format_hours(store)
        messages.append({
            "role": "ai", "kind": "text",
            "text": f"{' · '.join(changed)}을(를) 바꿨어요. 다음 스토리부터 이 값으로 만들어요.",
        })
    elif p["kind"] == "prod_add":
        # production.add_record와 같은 규칙 — 처음 보는 품목이면 품목 목록에도 넣는다.
        rec = models.ProductionRecord(**p["payload"])
        db.add(rec)
        if not db.query(models.ProductionItem).filter_by(name=rec.name).first():
            db.add(models.ProductionItem(name=rec.name))
        db.flush()  # 아래 메시지에 넣을 id가 필요하다
        # ProdBubble이 그린다 — 남긴 기록을 대화창에서 바로 고칠 수 있다(매진 시각 등).
        messages.append({"role": "ai", "kind": "prod", "prodId": rec.id})
    elif p["kind"] == "meme":
        sb.trend_meme_id = p["payload"]["meme_id"]
        sb.trend_meme_name = p["payload"]["meme_name"]
        messages.append({
            "role": "ai", "kind": "text",
            "text": f"'{p['payload']['meme_name']}' 밈으로 바꿨어요. 다음 스토리부터 이 밈을 참고할게요.",
        })
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


@router.post("/decline/{pid}", response_model=schemas.StoryboardOut)
def decline_pending(pid: str, db: Session = Depends(get_db)):
    sb = _get(db)
    pending = dict(sb.pending or {})
    p = pending.get(pid)
    if not p or p.get("status") != "open":
        raise HTTPException(404, "pending not open")
    pending[pid] = {**p, "status": "declined"}
    messages = list(sb.messages or [])
    messages.append({
        "role": "ai", "kind": "text",
        "text": "그대로 둘게요. 어떻게 바꾸면 좋을지 다시 적어주세요.",
    })
    sb.pending = pending
    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())
