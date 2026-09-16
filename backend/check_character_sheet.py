#!/usr/bin/env python3
"""캐릭터 시트 흐름이 기획대로 도는지 확인한다.

    cd backend && .venv/bin/pip install httpx   # TestClient가 쓴다. 서버 구동에는 불필요
    cd backend && .venv/bin/python check_character_sheet.py

임시 DB에서 돈다 — 운영 app.db도, ComfyUI도, OpenAI도 건드리지 않는다(LLM은 가짜
응답으로 대신한다). 배포 직후 한 번 돌려 보면 시트가 잠겨 있는지, 대화가 순서대로
묻는지, 승인 전에 값이 바뀌지 않는지를 몇 초 만에 확인할 수 있다.

확인하는 규칙:
  - 시트가 다 차기 전에는 후보 생성이 400
  - 생성은 버튼에서만 시작 — 대화는 GPU를 건드리지 않는다
  - 퍼스널 키워드는 맨 마지막에 자동 제안, 승인해야 시트가 완성된다
  - 다 찬 뒤의 수정은 승인 전까지 반영되지 않는다
  - 승인하면 가이드 순서상 다음 칸을 제안한다
  - 태깅에 넘어가는 칸은 외형·아웃핏·설명·나이·이름 다섯뿐
  - LLM이 지어낸 값은 버린다 / LLM이 죽어도 대화는 이어진다
  - 예전 스키마 DB도 마이그레이션되고 살아남는다
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

WORK = Path(tempfile.mkdtemp(prefix="sheetcheck-"))
os.environ["DATABASE_URL"] = f"sqlite:///{WORK / 'check.db'}"
os.environ["COMFY_BASE_URL"] = ""          # 그림은 뽑지 않는다
os.environ["OPENAI_API_KEY"] = ""          # 먼저 LLM 없는 경로부터
sys.path.insert(0, str(Path(__file__).resolve().parent))

PASS = FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  통과  {label}")
    else:
        FAIL += 1
        print(f"  실패  {label}   {detail}")


def section(title):
    print(f"\n{title}")


# --------------------------------------------------------------- 규칙 기반 경로
from app.main import app  # noqa: E402
from app.services.character_sheet import IMAGE_FIELDS  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

with TestClient(app) as client:
    section("[1] 처음 상태 — 시트가 비어 있고 생성이 잠겨 있다")
    c = client.get("/api/character").json()
    check("시트 8칸", len(c["sheet"]) == 8, c["sheet"])
    check("가이드 순서",
          [r["field"] for r in c["sheet"]]
          == ["look", "outfit", "desc", "abilities", "age", "gender", "name", "keywords"])
    check("전부 비어 있음", all(not r["value"] for r in c["sheet"]))
    check("생성 잠김", c["sheet_complete"] is False)

    section("[2] 시트가 덜 찼는데 그림 뽑기 → 400")
    r = client.post("/api/character/candidates")
    check("400으로 막힘", r.status_code == 400, r.status_code)
    check("남은 칸을 알려줌", "외형" in r.json()["detail"])

    section("[3] 말을 거는 첫 마디는 답이 아니다 — 넣지 말고 물어봐야 한다")
    # 실제로 났던 사고: 첫 인사가 외형에 들어가면서 그 뒤 답이 전부 한 칸씩 밀렸다.
    # 외형 칸에 '캐릭터 만들래요', 아웃핏 칸에 생김새, 설명 칸에 옷이 들어갔다.
    c = client.post("/api/character/chat", json={"text": "캐릭터 만들래요"}).json()
    check("시트는 그대로 비어 있음", all(not r["value"] for r in c["sheet"]),
          [r["value"] for r in c["sheet"]])
    check("외형부터 묻기 시작함", c["editing"] == "look", c["editing"])
    check("질문을 건넴", "어떻게 생긴" in c["messages"][-1]["text"], c["messages"][-1]["text"])

    section("[4] 대화로 한 칸씩 채운다 — 대화는 GPU를 건드리지 않는다")
    for text, expect_next in [
        ("통통한 갈색 곰, 동그란 눈", "아웃핏"),
        ("하얀 앞치마와 빵모자", "설명"),
        ("느긋하고 다정한 성격이에요", "능력"),
        ("소금빵을 잘 구워요", "나이"),
        ("3살", "성별"),
        ("없음", "이름"),
    ]:
        c = client.post("/api/character/chat", json={"text": text}).json()
        label = next((r["label"] for r in c["sheet"] if r["field"] == c["editing"]), "")
        check(f"'{text[:12]}' 뒤 → {expect_next}", label == expect_next, f"실제={label}")
        check("  그림이 돌지 않음", not c["generating"] and not c["candidates"])

    section("[5] 마지막 칸 → 퍼스널 키워드 자동 제안")
    c = client.post("/api/character/chat", json={"text": "구름이"}).json()
    pids = [p for p, v in c["pending"].items() if v["status"] == "open"]
    check("제안 1건", len(pids) == 1, c["pending"])
    proposal = c["pending"][pids[0]]
    check("종류 = keywords", proposal["kind"] == "keywords")
    check("사장님이 쓴 형용사에서만 뽑음",
          set(proposal["payload"]["keywords"]) <= {"통통한", "동그란", "느긋한", "다정한"},
          proposal["payload"]["keywords"])
    check("키워드 승인 전까지 생성 잠김", c["sheet_complete"] is False)

    section("[6] 키워드 승인 → 시트 완성, 생성이 열린다")
    c = client.post(f"/api/character/suggestions/{pids[0]}/accept").json()
    check("시트 완성", c["sheet_complete"] is True, c["missing"])
    check("완성을 알려줌", any("완성" in m.get("text", "") for m in c["messages"]))
    check("그래도 그림은 안 돌았음", not c["candidates"])

    section("[7] 다 찬 뒤의 수정은 승인 전까지 반영되지 않는다")
    client.post("/api/character/focus/outfit")
    c = client.post("/api/character/chat", json={"text": "파란 앞치마와 밀짚모자"}).json()
    check("아웃핏 그대로", c["outfit"] == "하얀 앞치마와 빵모자", c["outfit"])
    edit_pid = next(p for p, v in c["pending"].items() if v["status"] == "open")
    diff = c["pending"][edit_pid]["diffs"][0]
    check("전/후가 보임",
          diff["from"] == "하얀 앞치마와 빵모자" and diff["to"] == "파란 앞치마와 밀짚모자", diff)

    section("[8] 승인 → 반영하고 가이드 순서상 다음 칸을 제안한다")
    c = client.post(f"/api/character/suggestions/{edit_pid}/accept").json()
    check("아웃핏 바뀜", c["outfit"] == "파란 앞치마와 밀짚모자", c["outfit"])
    check("다음은 '설명'", "설명" in c["messages"][-1]["text"], c["messages"][-1]["text"])
    check("편집 대상이 desc로", c["editing"] == "desc", c["editing"])

    section("[9] 태깅에 넘어가는 칸은 다섯뿐")
    check("목록", IMAGE_FIELDS == ["look", "outfit", "desc", "age", "name"], IMAGE_FIELDS)
    check("능력·성별·키워드는 제외",
          not ({"abilities", "gender", "keywords"} & set(IMAGE_FIELDS)))

    section("[10] 거절 → 반영하지 않는다")
    client.post("/api/character/focus/name")
    c = client.post("/api/character/chat", json={"text": "먹구름이"}).json()
    pid = next(p for p, v in c["pending"].items() if v["status"] == "open")
    c = client.post(f"/api/character/suggestions/{pid}/decline").json()
    check("이름 그대로", c["name"] == "구름이", c["name"])

    section("[11] 처음부터 다시 → 전부 빈다")
    c = client.post("/api/character/reset").json()
    check("시트 비었음", all(not r["value"] for r in c["sheet"]))
    check("생성 다시 잠김", c["sheet_complete"] is False)
    check("대화 비었음", c["messages"] == [])


# ------------------------------------------------------------------- LLM 경로
# 진짜 OpenAI를 부르지 않는다. 붙었을 때 어떻게 도는지만 확인한다.
section("[12] LLM이 붙었을 때")

from app.core.config import settings  # noqa: E402
from app.services import sheet_llm  # noqa: E402

# 키가 있는 척만 한다. available()이 True가 되면 충분하고, 아래에서 requests.post를
# 갈아끼우기 때문에 이 값은 어디에도 나가지 않는다.
settings.openai_api_key = "x" * 8
SCRIPTED: list[dict] = []


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": json.dumps(self._payload)}}]}


def _fake_post(url, headers=None, json=None, timeout=None):
    assert "chat/completions" in url
    assert headers["Authorization"].startswith("Bearer ")
    return _FakeResponse(SCRIPTED.pop(0))


sheet_llm.requests.post = _fake_post

with TestClient(app) as client:
    client.post("/api/character/reset")

    SCRIPTED.append({"fields": {"look": "통통한 갈색 곰", "outfit": "하얀 앞치마", "age": "3살"}})
    c = client.post("/api/character/chat",
                    json={"text": "하얀 앞치마 두른 3살 통통한 갈색 곰이요"}).json()
    check("한 문장에서 세 칸을 채운다",
          (c["look"], c["outfit"], c["age"]) == ("통통한 갈색 곰", "하얀 앞치마", "3살"))
    check("다음은 가이드상 첫 빈 칸(설명)", c["editing"] == "desc", c["editing"])

    SCRIPTED.append({"fields": {}})
    c = client.post("/api/character/chat", json={"text": "새벽부터 빵 굽는 역할"}).json()
    check("LLM이 못 읽으면 물어본 칸에 그대로", c["desc"] == "새벽부터 빵 굽는 역할")

    # 사장님은 능력만 말했는데 모델이 성별·이름까지 지어내는 경우.
    SCRIPTED.append({"fields": {"abilities": "소금빵 굽기", "gender": "남성", "name": "구름이"}})
    c = client.post("/api/character/chat", json={"text": "소금빵을 잘 구워요"}).json()
    check("근거 있는 칸은 받는다", c["abilities"] == "소금빵 굽기", c["abilities"])
    check("지어낸 성별은 버린다", c["gender"] == "", repr(c["gender"]))
    check("지어낸 이름은 버린다", c["name"] == "", repr(c["name"]))

    # 지금 묻고 있는 칸은 근거 검사를 건너뛴다(사장님이 "아무거나"라고 답할 수 있다).
    SCRIPTED.append({"fields": {"gender": "중성"}})
    c = client.post("/api/character/chat", json={"text": "아무거나 상관없어요"}).json()
    check("묻던 칸은 근거 검사 없이 받는다", c["gender"] == "중성", c["gender"])

    def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    sheet_llm.requests.post = _boom
    c = client.post("/api/character/chat", json={"text": "구름이"}).json()
    check("LLM이 죽어도 대화가 이어진다", c["name"] == "구름이", c["name"])
    check("키워드 제안까지 도달", any(v["kind"] == "keywords" for v in c["pending"].values()))

settings.openai_api_key = ""


# ------------------------------------------------------- 예전 스키마 마이그레이션
section("[13] 예전 스키마 DB도 살아남는다")

OLD = WORK / "old.db"
con = sqlite3.connect(OLD)
con.executescript("""
CREATE TABLE character (id INTEGER PRIMARY KEY, name VARCHAR, age VARCHAR, gender VARCHAR,
  hobby VARCHAR, look VARCHAR, confirmed BOOLEAN, candidates JSON, selected_index INTEGER,
  views JSON, messages JSON);
CREATE TABLE store (id INTEGER PRIMARY KEY, saved BOOLEAN, category VARCHAR, address VARCHAR,
  hours VARCHAR, open_time VARCHAR, close_time VARCHAR, closed_days JSON, desc VARCHAR, images JSON);
CREATE TABLE ad_settings (id INTEGER PRIMARY KEY, ad_type VARCHAR, ad_concept VARCHAR);
CREATE TABLE storyboard (id INTEGER PRIMARY KEY, messages JSON, plan JSON, comic_cuts JSON,
  prod_logged BOOLEAN, pending JSON);
""")
con.execute("INSERT INTO character VALUES (1,'동글이','3살','남성','빵 굽기','갈색 곰',1,'[]',-1,'[]','[]')")
con.commit()
con.close()

# 엔진은 import 시점에 만들어지므로 새 프로세스에서 확인한다.
import subprocess  # noqa: E402

PROBE = f"""
import sys
sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    r = c.get('/api/character')
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['keywords'] == [] and d['pending'] == {{}}, (d['keywords'], d['pending'])
    assert d['name'] == '동글이' and d['look'] == '갈색 곰', d
    assert d['sheet_complete'] is False
    assert c.post('/api/character/candidates').status_code == 400
print('OK')
"""

probe = subprocess.run(
    [sys.executable, "-c", PROBE],
    env={**os.environ, "DATABASE_URL": f"sqlite:///{OLD}"},
    capture_output=True, text=True, check=False,
)
check("옛 DB에서 500 없이 뜬다", probe.stdout.strip().endswith("OK"),
      (probe.stdout[-300:] + probe.stderr[-300:]).strip())

print(f"\n{'=' * 46}\n  통과 {PASS} · 실패 {FAIL}\n{'=' * 46}")
sys.exit(1 if FAIL else 0)
