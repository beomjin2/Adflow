"""캐릭터 대화를 **실제 사장님이 칠 법한 말들**로 넓게 돌려 본다.

돌리는 법 (backend/ 에서):  .venv/bin/python check_flow.py

각 turn 마다 무엇이 일어났는지와 모델이 그렇게 판단한 이유(reasoning)를 함께 찍는다.
기대한 칸과 다르면 FAIL 로 표시한다 — 어디서 멍청해지는지 눈으로 보려고 만든 것이다.
임시 sqlite 를 쓰므로 운영 DB(app.db)는 건드리지 않는다. 그림도 만들지 않는다.
"""

import io
import logging
import os
import sys
import tempfile

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'flow.db')}"
os.environ["COMFY_BASE_URL"] = ""

from app import models, schemas  # noqa: E402
from app.api.routes import character as route  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.db.seed import ensure_rows  # noqa: E402
from app.services import sheet_llm  # noqa: E402

init_db()
with SessionLocal() as db:
    ensure_rows(db)

if not sheet_llm.available():
    sys.exit("OPENAI_API_KEY 가 없습니다.")

# sheet_llm 이 남기는 reasoning 을 잡아 둔다.
_buf = io.StringIO()
_h = logging.StreamHandler(_buf)
_h.setFormatter(logging.Formatter("%(message)s"))
_lg = logging.getLogger("app.services.sheet_llm")
_lg.setLevel(logging.INFO)
_lg.addHandler(_h)
_lg.propagate = False

TOTAL = {"pass": 0, "fail": 0}
FAILURES = []


def call(fn, *args):
    with SessionLocal() as db:
        return fn(*args, db).model_dump()


def sheet_of(data):
    return {r["field"]: r["value"] for r in data["sheet"]}


def open_card(data):
    for pid, p in data["pending"].items():
        if p["status"] == "open":
            return pid, p
    return "", None


def ai_text(data):
    said = [m for m in data["messages"] if m.get("role") == "ai" and m.get("text")]
    return said[-1]["text"] if said else ""


def set_store(category, desc, products=()):
    with SessionLocal() as db:
        s = db.get(models.Store, 1)
        s.saved = True
        s.category = category
        s.desc = desc
        s.images = [{"label": n, "image": ""} for n in products]
        db.commit()


def turn(msg, expect_field=None, accept=True, note=""):
    """한 마디 보내고 무슨 일이 났는지 찍는다. expect_field 를 주면 판정한다."""
    _buf.truncate(0), _buf.seek(0)
    before = sheet_of(call(route.get_character))
    data = call(route.chat, schemas.ChatIn(text=msg))
    reasoning = [ln for ln in _buf.getvalue().splitlines() if ln.strip()]
    pid, card = open_card(data)
    card_fields = list(card["payload"]["changes"]) if card and card["kind"] == "field" else (
        ["keywords"] if card else [])

    # 이번 턴에 **실제로 건드려진 칸**. 값이 바로 흡수되면 카드가 없으므로
    # 시트 전후를 견줘서 찾는다 — editing 은 그다음에 물을 칸이라 다른 얘기다.
    after = sheet_of(data)
    changed = [f for f in after if after[f] != before.get(f, "")]
    touched = card_fields or changed or ([data["editing"]] if data["editing"] else [])

    print(f"\n  >> {msg}")
    for ln in reasoning[:3]:
        print(f"     · {ln[:150]}")
    print(f"     AI    : {ai_text(data)[:120]}")
    if card:
        for d in card["diffs"]:
            print(f"     카드  : {d['label']}: {d['from'][:28]} -> {d['to'][:60]}")
    print(f"     묻는칸: {data['editing'] or '(없음)'}")

    if changed:
        print(f"     채움  : {', '.join(changed)}")
    if expect_field:
        ok = expect_field in touched
        TOTAL["pass" if ok else "fail"] += 1
        print(f"     판정  : {'PASS' if ok else 'FAIL  (기대: ' + expect_field + ')'}{'  ' + note if note else ''}")
        if not ok:
            FAILURES.append(f"{msg}  -> 다룬 칸 {touched} / 기대 {expect_field}")
            print(f"     * 카드={card_fields} 바뀐칸={changed} 묻는칸={data['editing']}")

    if card and accept:
        data = call(route.accept_suggestion, pid)
    return data


def scenario(title, store=("베이커리", "내맘대로 베이커리", ("소금빵",))):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)
    call(route.reset_character)
    set_store(*store)


# ─────────────────────────────────────────────────────────── 시나리오
scenario("A. 아무 생각 없는 사장님 — 전부 떠넘긴다")
turn("뭐부터 해야돼?", accept=False)
turn("몰라 알아서 해줘", expect_field="look")
turn("그것도 알아서", expect_field="outfit")

scenario("B. 앞 칸으로 돌아가기 — 여러 말투")
turn("갈색 털에 동그란 눈을 가진 곰", expect_field="look")
turn("아 외형 다시 할래", expect_field="look")
turn("아웃핏 말고 외형", expect_field="look")
turn("외형을 바꾸고 싶어 아웃핏은 놔두고", expect_field="look")
turn("아니 외형 아웃핏말고", expect_field="look", note="(끝에 제외가 붙는 꼴)")

scenario("C. 고치지 말고 덧붙이기")
turn("하얀 털에 파란 눈을 가진 고양이", expect_field="look")
turn("거기에 꼬리가 길었으면 좋겠어", expect_field="look")

scenario("D. 한 문장에 여러 칸")
turn("앞치마 두른 세 살 곰이고 이름은 빵돌이야", expect_field="look")

scenario("E. 질문을 던진다 — 답을 해야 한다")
turn("캐릭터 만들면 뭐가 좋아?", accept=False)
turn("빵집엔 뭐가 어울려?", accept=False)

scenario("F. 거부·불만")
turn("알아서 해줘", expect_field="look")
turn("마음에 안들어 다시", expect_field="look")

scenario("G. 같은 말 반복 — 못 알아들으면 안 된다")
turn("알아서 해줘", expect_field="look")
turn("아니 외형 말고 이름부터 정하자", expect_field="name")
turn("이름부터 하자니까", expect_field="name")

scenario("J. 능력 칸 — 설명과 헷갈리기 쉽다")
turn("갈색 털에 큰 눈을 가진 곰", expect_field="look")
turn("흰 앞치마와 빵집 모자", expect_field="outfit")
turn("느긋하지만 손님 이름은 다 외워요", expect_field="desc")
turn("알아서 해줘", expect_field="abilities", note="(대신 정해주기)")
turn("소금빵을 진짜 잘 구워요", expect_field="abilities", note="(직접 말하기)")

scenario("K. 덮어쓰기 — 사장님 말이 버려지면 안 된다")
turn("하얀 고양이", expect_field="look")
turn("아니 까만 고양이로", expect_field="look", note="(말한 값이 살아야 한다)")

scenario("H. 잡담·딴소리")
turn("오늘 날씨 좋네", accept=False)
turn("ㅋㅋㅋ", accept=False)

scenario("I. 업종이 다른 가게 — 빵집 답이 나오면 안 된다",
         store=("세탁소", "20년째 동네 세탁물을 받는 세탁소", ("드라이클리닝",)))
d = turn("알아서 추천해줘", expect_field="look")
card_text = sheet_of(d)["look"]
bread = any(w in card_text for w in ("빵", "베이커리", "제빵"))
TOTAL["fail" if bread else "pass"] += 1
print(f"     빵집 흔적: {'FAIL  ' + card_text if bread else 'PASS 없음'}")
if bread:
    FAILURES.append(f"세탁소인데 빵 얘기: {card_text}")

# ─────────────────────────────────────────────────────────── 요약
print("\n" + "=" * 74)
print(f"통과 {TOTAL['pass']} · 실패 {TOTAL['fail']}")
if FAILURES:
    print("\n실패한 것:")
    for f in FAILURES:
        print(f"  - {f}")
print("=" * 74)
