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

생산 기록은 여기서 안 받는다 — "내 정보 > 생산 기록" 탭에서만 남긴다. 예전엔 대화
첫 마디를 생산 기록으로 파싱했는데, 대화 한 번으로 두 가지 일을 하는 게 헷갈린다는
판단으로 뺐다. `_plan_cuts`가 매번 최근 생산 기록을 조회해서 스토리에 반영하는 건
그대로다 — 그 기록을 만드는 자리만 옮긴 것이다.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.config import settings
from app.core.database import get_db
from app.services import jobs, story_llm
from app.services.chat_ai import COMIC_IDENTITY_FIELDS, character_part, comic_prompt, new_pid
from app.services.image_gen import generate_images
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
    proposed = story_llm.plan_from_text(text, **ctx)
    if proposed is None:
        return _cuts_from_text(text), None
    if not proposed["cuts"]:
        return None
    return proposed["cuts"], proposed["meme_used"]


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

    생산 기록은 여기서 안 받는다("내 정보 > 생산 기록" 탭에서만 남긴다) — 대화는
    스토리를 만드는 자리다. 만든 구성은 바로 반영하지 않고 confirm 카드로 보여준다 —
    사장님이 '이렇게 바뀝니다'를 보고 승인해야 실제로 반영된다.
    """
    sb = _get(db)
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "내용을 입력해주세요")

    messages = list(sb.messages or [])
    messages.append({"role": "me", "kind": "text", "text": text})

    _require_character(db)
    result = _plan_cuts(text, sb, db)
    if result is None:
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
        if not _propose_options(
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

    sb.messages = messages
    db.commit()
    db.refresh(sb)
    return schemas.storyboard_out(sb, jobs.queue_depth())


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


@router.post("/recommend-meme", response_model=schemas.StoryboardOut)
async def recommend_meme_from_chat(db: Session = Depends(get_db)):
    """대화창의 "밈 추천받기" 버튼 — 자동으로는 안 뜬다. 지금까지 사장님이 대화에서 쓴
    문장을 모아 trend/recommend.py와 같은 GPT 추천(meme_recommend.recommend)을 돌리고,
    결과를 confirm 카드로 올린다. 승인해야만 trend_meme_id가 바뀐다 — 대화 흐름만 보고
    GPT가 알아서 밈을 끼워 넣지 않는다.
    """
    sb = _get(db)
    messages = list(sb.messages or [])
    note = _chat_note(messages)
    if not note:
        messages.append({
            "role": "ai", "kind": "text",
            "text": "대화에서 알릴 내용을 먼저 말씀해주시면 그걸 보고 밈을 추천해드릴게요.",
        })
        sb.messages = messages
        db.commit()
        db.refresh(sb)
        return schemas.storyboard_out(sb, jobs.queue_depth())

    all_memes = [m for m in db.query(models.Meme).all() if m.situation and m.situation != "미분류"]
    if not all_memes:
        messages.append({"role": "ai", "kind": "text", "text": "지금 추천할 수 있는 밈이 없어요."})
        sb.messages = messages
        db.commit()
        db.refresh(sb)
        return schemas.storyboard_out(sb, jobs.queue_depth())

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
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("대화 기반 밈 추천 실패")
        raise HTTPException(502, "추천을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요")

    by_id = {m.id: m for m in all_memes}
    pick = result["picks"][0]
    meme = by_id[pick["meme_id"]]

    pending = dict(sb.pending or {})
    pid = new_pid()
    pending[pid] = {
        "which": "sb", "kind": "meme",
        "diffs": [{"label": "트렌드 밈", "from": sb.trend_meme_name or "아직 없음", "to": meme.meme_name}],
        "why": pick["reason"],
        "payload": {"meme_id": meme.id, "meme_name": meme.meme_name},
        "status": "open",
    }
    sb.pending = pending
    messages.append({
        "role": "ai", "kind": "text",
        "text": f"지금까지 나눈 얘기를 보니 '{meme.meme_name}' 밈이 어울릴 것 같아요.",
    })
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})
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


def _fill_cuts(indexes: list[int], scenes: list[dict], char_part_text: str, reference: Path) -> None:
    """백그라운드 본체 — 컷마다 프롬프트를 만들고 한 장씩 뽑아 comic_cuts의 칸을 채운다.
    컷 문장의 태그 변환(GPT)도 여기서 한다. 실패한 칸은 failed로 남긴다.
    scenes[i] = {"text": 동작 문장(없으면 대사), "camera": 구도 태그 또는 ""}."""
    for index, scene in zip(indexes, scenes):
        prompt = comic_prompt(char_part_text, scene.get("text", ""), scene.get("camera", ""))
        images = generate_images(prompt, 1, workflow_file=settings.comfy_comic_workflow_file,
                                 reference_path=reference)
        image = images[0] if images else None

        def write(db: Session, index=index, image=image):
            sb = db.get(models.Storyboard, 1)
            if not sb:
                return
            cuts = list(sb.comic_cuts or [])
            if 0 <= index < len(cuts):
                cuts[index] = {**cuts[index], "image": image, "status": "done" if image else "failed"}
                sb.comic_cuts = cuts
                db.commit()

        jobs.with_session(write)


def _start_cuts(sb: models.Storyboard, char: models.Character, indexes: list[int], db: Session) -> None:
    reference = _reference_path(char)
    if reference is None:
        raise HTTPException(400, "캐릭터를 먼저 확정해주세요 — 확정한 캐릭터 그림을 참조로 씁니다")
    cuts = list(sb.comic_cuts or [])
    # 그림엔 대사가 아니라 동작을 넣는다(대사·글자는 말풍선 몫). 동작이 없으면(직접 쓴 컷) 대사 문장을 쓴다.
    scenes = [{"text": cuts[i].get("action") or cuts[i].get("line", ""), "camera": cuts[i].get("camera", "")}
              for i in indexes]
    for i in indexes:
        cuts[i] = {**cuts[i], "image": None, "status": "generating"}
    sb.comic_cuts = cuts
    db.commit()
    # 캐릭터 태그는 여기서 한 번만 계산한다(GPT 1회). 컷 문장 변환은 백그라운드에서.
    # 생김새·옷·나이만 넘긴다 — 성격·능력에서 나오는 표정·소품 태그는 컷마다 정해지는
    # 표정과 부딪친다(chat_ai.COMIC_IDENTITY_FIELDS).
    jobs.submit(_fill_cuts, indexes, scenes, character_part(char, COMIC_IDENTITY_FIELDS), reference)


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
    sb.comic_cuts = [
        {"n": c["n"], "short": c.get("short", ""), "line": c.get("line", ""),
         "action": c.get("action", ""), "camera": c.get("camera", ""),
         "label": f"{c['n']}컷", "image": None, "status": "generating"}
        for c in plan
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
