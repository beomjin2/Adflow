"""캐릭터 시트 대화가 **정해진 답을 띄우는지** 실제 LLM으로 확인한다.

돌리는 법 (backend/ 에서):

    .venv/bin/python check_character_llm.py

`.env`의 OPENAI_API_KEY를 그대로 쓴다. 임시 sqlite에 붙으므로 운영 DB(app.db)는
건드리지 않는다. 그림은 만들지 않는다(ComfyUI 호출 없음).

무엇을 보는가:
  1. 업종이 다른 가게 둘에 똑같이 "알아서 정해줘"를 넣었을 때 **다른 답**이 나오는가.
     예전에는 프롬프트에 박힌 예시(갈색 곰 + 흰 앞치마 + 소금빵) 탓에 어느 가게든
     같은 캐릭터가 나왔다 — 사장님 눈에는 목 데이터를 띄우는 것으로 보인다.
  2. 다 찬 시트에서 "외형 다시 하고 싶어" 가 실제로 외형 칸을 여는가.
     예전에는 "시트에서 칸을 눌러주세요"만 반복해 대화로는 못 고쳤다.
  3. 한 문장에서 여러 칸을 읽어내고, 사장님이 쓴 디테일을 버리지 않는가.
"""

import os
import sys
import tempfile

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'check.db')}"
os.environ["COMFY_BASE_URL"] = ""

from app import models, schemas  # noqa: E402
from app.api.routes import character as route  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.db.seed import ensure_rows  # noqa: E402
from app.services import character_sheet as sheet  # noqa: E402
from app.services import sheet_llm  # noqa: E402
from app.services.chat_ai import character_sheet_text  # noqa: E402

init_db()
with SessionLocal() as db:
    ensure_rows(db)

if not sheet_llm.available():
    sys.exit("OPENAI_API_KEY가 없습니다. backend/.env 에 키가 있는지 확인하세요.")


def call(fn, *args):
    with SessionLocal() as db:
        return fn(*args, db).model_dump()


def say(text):
    return call(route.chat, schemas.ChatIn(text=text))


def last_text(data):
    for message in reversed(data["messages"]):
        if message.get("role") == "ai" and message.get("text"):
            return message["text"]
    return ""


def open_proposal(data):
    for pid, proposal in data["pending"].items():
        if proposal["status"] == "open":
            return pid, proposal
    return "", None


def set_store(category, desc, products):
    with SessionLocal() as db:
        store = db.get(models.Store, 1)
        store.saved = True
        store.category = category
        store.desc = desc
        store.images = [{"label": name, "image": ""} for name in products]
        db.commit()


def reset():
    call(route.reset_character)


# 눈으로 확인만 하려고 두는 목록이다. 코드가 이걸로 제안을 막지는 않는다 —
# 소재를 금지하면 그것도 또 하나의 고정이라, 곰을 원하는 사장님이 곰을 못 받는다.
COMMON = ("곰", "토끼", "고양이", "강아지", "갈색 털", "흰 앞치마", "하얀 앞치마", "요리사 모자")

SHOPS = [
    ("꽃집", "새벽 경매에서 떼 온 꽃으로 그날그날 다발을 묶는 동네 꽃집", ["계절 꽃다발", "화분"]),
    ("수선집", "20년째 바지 기장과 지퍼를 고치는 동네 수선집", ["기장 수선", "지퍼 교체"]),
]

print("=" * 72)
print("1. 업종이 다르면 다른 캐릭터를 제안하는가")
print("=" * 72)

proposals = {}
for category, desc, products in SHOPS:
    reset()
    set_store(category, desc, products)
    say("안녕하세요")
    data = say("잘 모르겠어요, 알아서 정해줘요")
    pid, proposal = open_proposal(data)
    value = ""
    if proposal:
        value = " / ".join(f"{d['label']}: {d['to']}" for d in proposal["diffs"])
    proposals[category] = value
    print(f"\n[{category}] {desc}")
    print(f"  AI 대답 : {last_text(data)[:150]}")
    print(f"  제안 값 : {value or '(제안 없음 — 되물었다)'}")
    if proposal:
        basis = proposal.get("basis") or []
        if basis:
            print("  근거    :")
            for b in basis:
                print(f"            [{b['label']}] “{b['quote']}”")
            print(f"            → {proposal.get('why', '')}")
        else:
            print("  근거    : ⚠ 없음 — 무엇을 보고 정했는지 못 보여준다")
    # 흔한 소재가 나오는 것 자체는 문제가 아니다. 근거 없이 어느 가게든 같은 답이
    # 나오는 게 문제였다. 그래서 금지하지 않고 **눈에 띄게 표시만** 한다.
    hit = [word for word in COMMON if word in value]
    if hit:
        print(f"  참고    : 흔한 소재({', '.join(hit)})가 들어 있다 — 위 근거가 납득되면 괜찮다")

same = proposals[SHOPS[0][0]] and proposals[SHOPS[0][0]] == proposals[SHOPS[1][0]]
print(f"\n  두 가게 제안이 같은가: {'⚠ 같다 (목 데이터 의심)' if same else '아니오 — 가게마다 다르다'}")

print()
print("=" * 72)
print("2. 다 찬 시트에서 '외형 다시 하고 싶어' 가 외형 칸을 여는가")
print("=" * 72)

reset()
set_store(*SHOPS[0])
say("안녕하세요")
for line in [
    "연보라색 꽃잎 같은 날개를 단 작은 나비예요. 눈은 연두색이고요",
    "리넨 앞치마에 밀짚모자를 썼으면 좋겠어요",
    "말수는 적은데 손님 이름은 다 외우는 성격이에요",
    "꽃다발을 빠르게 묶어요",
    "다섯 살",
    "없음",
    "꽃순이",
]:
    data = say(line)
    pid, proposal = open_proposal(data)
    if proposal:  # 키워드 자동 제안 등은 승인하고 넘어간다
        data = call(route.accept_suggestion, pid)

print(f"  시트가 다 찼는가: {data['sheet_complete']}  (남은 칸: {data['missing']})")
for row in data["sheet"]:
    print(f"    {row['label']:<8} {row['value']}")

data = say("외형 다시 하고 싶어")
print(f"\n  '외형 다시 하고 싶어' → 열린 칸: {data['editing'] or '(없음)'}")
print(f"  AI 대답: {last_text(data)[:160]}")
print(f"  판정: {'통과 — 외형 칸이 열렸다' if data['editing'] == 'look' else '⚠ 실패 — 칸이 안 열렸다'}")

data = say("날개를 주황색으로 바꾸고 눈은 까맣게 해주세요")
pid, proposal = open_proposal(data)
print("\n  이어서 바꿀 내용을 말했을 때:")
if proposal:
    for d in proposal["diffs"]:
        print(f"    {d['label']}: \"{d['from']}\"  →  \"{d['to']}\"")
    print("  판정: 통과 — 승인 카드가 떴다")
else:
    print(f"    {last_text(data)[:160]}")
    print("  판정: ⚠ 실패 — 수정 카드가 안 떴다")

print()
print("=" * 72)
print("3. 한 문장에서 여러 칸을 읽고 디테일을 버리지 않는가")
print("=" * 72)

reset()
set_store(*SHOPS[0])
say("안녕하세요")
long_line = (
    "연보라색 꽃잎 날개에 연두색 눈을 가진 작은 나비인데, 리넨 앞치마를 두르고 "
    "밀짚모자를 썼어요. 세 살이고 이름은 꽃순이예요."
)
print(f"  입력: {long_line}\n")
data = say(long_line)
for row in data["sheet"]:
    if row["value"]:
        print(f"    {row['label']:<8} {row['value']}")
filled = [r["field"] for r in data["sheet"] if r["value"]]
print(f"\n  한 번에 채워진 칸 {len(filled)}개: {filled}")
print(f"  판정: {'통과' if len(filled) >= 4 else '⚠ 적게 읽었다'}")

print()
print("=" * 72)
print("3-b. 채우는 중에 다른 칸으로 옮겨갈 수 있는가 (실사용에서 막혔던 지점)")
print("=" * 72)
# 배포 서버 실사용: 아웃핏을 묻는 중에 "고양이 말고 다른 외형 추천해줘"라고 했더니
# 계속 아웃핏만 물었고, 외형 값("흰색 털에 긴 꼬리를 가진 강아지")을 아웃핏 칸에 제안했다.
reset()
set_store("베이커리", "동네 빵집", ["소금빵"])
say("안녕하세요")
data = say("몰라 베이커리 잘하게 생기게")
pid, proposal = open_proposal(data)
if proposal:
    data = call(route.accept_suggestion, pid)
print(f"  외형 채운 뒤 묻는 칸: {data['editing']}  (아웃핏이어야 정상)")

data = say("아 고양이 말고 다른거 할래 외형 뭐 다른거 추천좀")
pid, proposal = open_proposal(data)
target = list(proposal["payload"]["changes"])[0] if proposal else ""
print(f"\n  '외형 뭐 다른거 추천좀' →")
print(f"    열린 칸   : {data['editing']}")
print(f"    제안된 칸 : {target or '(제안 없음)'}")
if proposal:
    for d in proposal["diffs"]:
        print(f"    {d['label']}: \"{d['to']}\"")
ok = data["editing"] == "look" and (not target or target == "look")
print(f"    판정: {'통과 — 외형 쪽으로 옮겨갔다' if ok else '⚠ 실패 — 아웃핏에 갇혔다'}")
if proposal:
    data = call(route.decline_suggestion, pid)

data = say("강아지")
looks = {r["field"]: r["value"] for r in data["sheet"]}
print(f"\n  이어서 '강아지' →")
print(f"    외형 : {looks['look']}")
print(f"    아웃핏: {looks['outfit'] or '(비어 있음)'}")
pid, proposal = open_proposal(data)
if proposal:
    for d in proposal["diffs"]:
        print(f"    제안: {d['label']} → \"{d['to']}\"")
print(f"    판정: {'통과 — 아웃핏에 안 들어갔다' if '강아지' not in (looks['outfit'] or '') else '⚠ 실패 — 아웃핏에 들어갔다'}")

print()
print("=" * 72)
print("4. 시트 정보가 그림 프롬프트로 얼마나 넘어가는가")
print("=" * 72)
with SessionLocal() as db:
    char = db.get(models.Character, 1)
    print("  태그 변환기에 넘어가는 입력:")
    for line in character_sheet_text(char).splitlines():
        print(f"    {line}")
    print(f"\n  넘기지 않는 칸: 이름, 성별  (IMAGE_FIELDS = {sheet.IMAGE_FIELDS})")
