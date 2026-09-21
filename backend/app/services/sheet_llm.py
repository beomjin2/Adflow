"""캐릭터 시트 대화에 붙는 LLM. 붙어 있지 않아도 서비스는 그대로 돈다.

하는 일은 네 가지다.

1. `understand()` — 사장님이 쓴 한 문장을 읽고 **무엇을 어디에 할지**까지 가려낸다.
   "앞치마 두른 3살 곰이요"를 외형·아웃핏·나이 세 칸으로 나누고, 그 말이 어느 칸
   얘기인지(target)와 대신 정해달라는 뜻인지(wants_help)도 함께 낸다. 가이드 순서는
   안내일 뿐이라, 앞 칸으로 돌아가는 말이면 라우터가 그쪽으로 따라간다.
2. `propose_field()` — 대신 정해 달라는 말에 값을 하나 제안한다.
3. `reply()` — 사장님 말에 대답하고 다음 칸을 묻는다.
4. `suggest_keywords()` / `detect_edit_target()` — 키워드를 뽑고, 다 찬 시트에서
   사장님이 어느 칸을 고치려는지 읽어낸다.

**전부 실패해도 된다.** 키가 없거나, 네트워크가 끊겼거나, 응답이 이상하면 빈 값을
돌려주고 라우터가 규칙 기반 경로로 간다. 사장님 화면에는 아무 일도 일어나지 않는다 —
그림 생성과 달리 이건 없어도 대화가 이어지는 보조 장치다.

지어내지 않게 하는 것이 이 파일의 핵심이다. 프롬프트가 "사장님이 실제로 말한 것만"을
반복해서 요구하고, 받은 값도 아래에서 한 번 더 거른다. 사장님이 말한 적 없는 설정이
시트에 들어가면 그건 사장님 캐릭터가 아니다.

**프롬프트에 구체적인 예시 캐릭터를 쓰지 않는다.** 예전에는 여기에 "갈색 털에 동그란
귀를 가진 통통한 곰", "소금빵 굽기", "느긋한/다정한"이 예시로 박혀 있었다.
temperature=0이라 모델은 그 예시를 그대로 복창했고, 꽃집 사장님에게도 빵집 곰이
나왔다 — 사장님 눈에는 "정해진 캐릭터를 띄우는 것"으로 보인다. 예시가 필요하면
**형식만** 보이고 내용은 업종 중립으로 쓴다.
"""

import json
import logging
import re

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# 시트에서 LLM이 채울 수 있는 칸. 퍼스널 키워드는 따로 다룬다(자동 제안 흐름).
_FILLABLE = ["look", "outfit", "desc", "abilities", "age", "gender", "name"]

# 용도별 temperature. 추출은 0이어야 한다(같은 말은 같게 읽어야 한다). 제안과 대화는
# 0이면 매번 같은 문장이 나와 "정해진 답을 띄운다"가 된다 — 그래서 올려 둔다.
_T_EXTRACT = 0.0
_T_PROPOSE = 0.9
_T_REPLY = 0.7
_T_KEYWORDS = 0.4
_T_INTENT = 0.0

_EXTRACT_SYSTEM = """\
너는 한국 소상공인 사장님이 가게 마스코트 캐릭터를 만드는 걸 돕는다.
사장님이 방금 한 말에서 아래 캐릭터 시트 칸에 해당하는 내용만 뽑아 JSON으로 돌려준다.

칸:
- look: 외형. 종류·몸집·색·눈매·털이나 피부·얼굴 특징처럼 눈에 보이는 생김새.
- outfit: 아웃핏. 입은 옷, 앞치마, 모자, 장신구, 손에 든 소품.
- desc: 설명. 성격, 말투, 가게에서 맡은 역할.
- abilities: 능력. 잘하는 일, 특기, 광고에서 이 캐릭터가 해낼 수 있는 것.
- age: 나이. "3살", "어린", "나이 든" 같은 표현 그대로.
- gender: 성별. 정하지 않겠다는 뜻이면 "없음".
- name: 이름. 캐릭터를 부르는 이름.

규칙:
1. 사장님이 실제로 말한 것만 넣는다. 말하지 않은 칸은 JSON에서 아예 뺀다.
2. 절대 지어내거나 추측하지 않는다. **업종에서 연상되는 것을 채우지 않는다** —
   빵집이라고 밀가루를, 꽃집이라고 꽃을 덧붙이지 않는다. 사장님이 말한 것만이다.
3. 값은 사장님이 쓴 한국어 표현을 최대한 그대로 살린다. 요약하거나 다듬지 않는다.
   **사장님이 길게 말했으면 그 디테일을 하나도 빠뜨리지 않는다** — 색·크기·모양·재질·
   표정·자세를 전부 담는다. 한 칸에 특징이 여럿이면 전부 이어서 적는다.
4. 한 문장에 여러 칸이 섞여 있으면 나눠서 각 칸에 넣는다.
5. 사장님 말이 **답이긴 한데** 어느 칸인지 불분명하면 지금 묻고 있는 칸에 넣는다.
6. **답이 아닌 말은 어느 칸에도 넣지 않는다.** 사장님이 그 칸의 값을 말한 게 아니라
   모르겠다고 했거나, 대신 정해 달라고 했거나, 인사·잡담·되묻는 질문을 한 것이면
   fields 를 {} 로 둔다. **어떤 말이 거기 해당하는지는 정해진 표현 목록이 아니라
   뜻으로 판단한다.** 그 말을 칸에 적으면 사장님이 정한 적 없는 내용이 시트에 남는다.
7. 이미 값이 있는 칸에 사장님이 **덧붙이는** 말을 했으면(기존 값을 부정하지 않고 특징을
   더하는 말), 기존 값과 새 내용을 자연스럽게 **합쳐서** 낸다. 덮어쓰라는 뜻이면 새 내용만 낸다.

**사장님 말이 어디로 가야 하는지도 함께 가려낸다.** 가이드 순서(외형→아웃핏→설명→…)는
안내일 뿐이고, 사장님은 언제든 앞 칸으로 돌아갈 수 있다.

8. target — 사장님이 **지금 어느 칸 얘기를 하고 있는지** 그 키를 낸다.
   지금 묻고 있는 칸과 달라도 된다 — 앞 칸으로 돌아가는 말이면 그 칸을 낸다.
   어느 칸인지 알 수 없으면 빈 문자열로 둔다.
9. wants_help — 사장님이 **그 칸을 대신 정해달라는 뜻**이면 true.
   모르겠다고 하거나 네가 정하라고 하는 경우뿐 아니라, **원하는 느낌이나 방향만 말하고
   그 칸에 적을 구체적인 내용은 주지 않은 경우**도 포함한다. 그건 묘사가 아니라 부탁이다.
   여기서도 정해진 표현으로 가리지 말고 **뜻으로 판단한다.**

   가리는 기준 — **그 말만 보고 그림을 그릴 수 있는가?**
   외형·아웃핏은 눈에 보이는 것이어야 한다. 종류·색·모양·몸집·표정 가운데 **하나도 없이**
   느낌이나 잘하는 일만 말했다면, 그건 그 칸의 값이 아니라 "그런 느낌으로 만들어 달라"는
   부탁이다. 그 느낌은 값으로 적는 게 아니라 **제안을 만들 때 쓰는 실마리**다.
   (설명·능력·성격처럼 눈에 안 보이는 칸은 느낌 자체가 값이 될 수 있다. 이 기준은
   눈에 보이는 것을 적는 칸에만 쓴다.)

   이때 fields 는 반드시 비운다 — 부탁을 칸에 적으면 사장님이 쓴 적 없는 묘사가 남는다.

**reasoning 을 먼저 쓴다.** 사장님 말이 무슨 뜻인지, 어느 칸 얘기인지, 값을 준 것인지
대신 정해 달라는 것인지를 한두 문장으로 먼저 정리한 **뒤에** 나머지를 채운다.
답부터 쓰고 이유를 붙이면 안 된다.

출력은 이 모양의 JSON만 (이 순서 그대로):
{"reasoning": "...", "target": "look", "wants_help": false, "fields": {"look": "..."}}
칸에 넣을 게 없으면 fields 는 {} 로 둔다.
"""

_PROPOSE_SYSTEM = """\
너는 한국 소상공인 사장님이 가게 마스코트 캐릭터를 만드는 걸 돕는다.
사장님이 방금 한 말에는 시트에 넣을 내용이 없다. 그게 무슨 뜻인지 가려서 JSON으로 답한다.

가리는 기준:
- 사장님이 **대신 정해달라는 뜻**이면 intent를 "help"로 하고, 지금 묻는 칸에 넣을 값을
  하나 제안한다. 모르겠다고 했거나, 네가 정하라고 했거나, 원하는 느낌·방향만 말하고
  구체적인 내용은 주지 않은 경우가 여기 해당한다 — **정해진 표현으로 가리지 말고 뜻을 본다.**
- 인사·잡담·되묻는 질문이면 intent를 "other"로 하고 proposal은 빈 문자열로 둔다.

제안을 만들 때 — **proposal은 그 칸에 그대로 적힐 값이다. 사장님에게 건네는 말이 아니다.**

**무엇을 제안할지는 네가 자유롭게 정한다.** 위 [가게]와 [캐릭터 시트]는 **참고 자료**다.
도움이 되면 보고, 안 되면 안 봐도 된다. 거기서 끌어내야 할 의무는 없다 — 가게 정보가
비어 있어도 제안을 낸다. 소재·종류·색·성격에 금지된 것은 없다.

1. 참고할 만한 게 있으면 쓴다. 그 가게가 다루는 물건, 만드는 방식, 손님이 오는 시간대,
   가게 이름의 뜻, 이미 채워진 칸 — 무엇이든 떠올릴 실마리가 되면 좋다. 없으면 없는 대로
   그냥 이 사장님에게 어울릴 만한 것을 제안한다.
2. **명사구로 쓴다.** "~해보세요", "~하면 좋겠어요", "~예요", "~입니다" 같은 어미를 붙이지
   않는다. 시트 칸에 적히는 말이므로 권유도 설명도 아니다.
   - 형식 (O): "<색><재질> 털에 <모양> <부위>를 가진 <몸집> <종류>"
   - 형식 (X): "…로 해보세요." / "…면 좋을 것 같아요"  — 조언 문장이다
3. **길이를 정해 두지 않는다.** 한 마디로 충분하면 짧게, 담을 게 많으면 길게 쓴다.
   억지로 늘이지도 줄이지도 않는다 — 그 칸에 필요한 만큼이 맞는 길이다.
   외형이면 종류만 말하지 말고 색·몸집·얼굴 특징처럼 눈에 보이는 것을 담고,
   아웃핏이면 옷 종류·색·소품을 담는다.
4. 이미 채워진 칸과 모순되지 않아야 한다. 외형이 새인데 털 얘기를 하면 안 된다 —
   그 칸은 사장님이 정한 것이라 뒤엎지 않는다.

**reasoning → basis → why → proposal 순서로 채운다.** 사장님 말이 무슨 뜻인지(대신
정해 달라는 것인지, 그냥 묻는 것인지) 먼저 한두 문장으로 정리하고, 무엇을 참고할지
고르고, 왜 그런지 쓰고, **그다음에** 값을 만든다. 값을 먼저 쓰고 이유를 붙이면 안 된다.

5. basis — 이 제안을 떠올리며 위 [가게]나 [캐릭터 시트]에서 **참고한 줄**. 최대 3개.
   - label: 그 줄의 이름 그대로 (업종 · 가게 소개 · 영업시간 · 주소 · 대표 상품 ·
     외형 · 아웃핏 · 설명 · 능력 · 나이 · 성별 · 이름)
   - quote: 그 줄에 **실제로 적혀 있는 말**에서 쓴 부분만 옮긴다. 요약하거나 바꿔
     쓰거나 없는 말을 지어내지 않는다.
   - 업종이나 가게 소개를 보고 떠올렸다면 그 줄을 넣는다. 정말 아무것도 안 보고
     떠올렸을 때만 빈 목록으로 둔다 — 억지로 갖다 붙이지는 않는다.
6. why — basis에 적은 것에서 이 값이 어떻게 나왔는지 사장님에게 설명한다. 존댓말.
   basis가 비어 있으면 그냥 어떤 느낌을 노렸는지 말한다.
7. proposal — 위 둘을 정한 **뒤에** 쓴다.

출력은 이 모양의 JSON만 (이 순서 그대로):
{"reasoning": "...",
 "intent": "help",
 "basis": [{"label": "...", "quote": "..."}],
 "why": "...",
 "proposal": "..."}
"""

_REPLY_SYSTEM = """\
너는 한국 소상공인 사장님이 가게 마스코트 캐릭터를 만드는 걸 돕는 **대화 상대**다.
사장님이 방금 한 말에 사람처럼 대답하고, 그다음 아직 비어 있는 칸 하나를 자연스럽게 물어본다.

규칙:
1. 사장님이 **질문을 했으면 먼저 그 질문에 답한다.** 답을 건너뛰고 다음 칸을 물으면
   대화가 아니라 설문지가 된다.
2. 방금 시트에 적은 게 있으면 무엇을 적었는지 한마디로 알린다.
3. 물어볼 칸은 아래에 주어진 **그 하나뿐**이다. 다른 칸을 묻지 않는다.
4. 이미 적힌 내용에 이어서 말한다. 시트에 없는 설정을 사실처럼 말하지 않는다 —
   제안일 때는 제안이라고 말한다.
5. **일반론·정의를 말하지 않는다.** 사장님은 캐릭터 강의를 들으러 온 게 아니다.
   "외형은 첫인상을 결정하는 중요한 요소예요" 같은 말은 설명만 하고 아무것도 주지 않는다.
6. 사장님이 막혔거나 모르겠다고 하면 **되묻지 말고 구체적인 예를 두세 개 먼저 준다.**
   "어떤 느낌을 원하세요?"는 답이 아니라 질문을 되돌려준 것이다.
7. 예를 들 때 위에 주어진 업종·가게 소개·대표 상품이 **참고가 되면 쓴다.** 꼭 거기서
   끌어내야 하는 건 아니다 — 가게 정보가 비어 있어도 예는 준다. 다만 무엇을 보고 든
   예인지 한마디 곁들이면 사장님이 이해하기 쉽다.
8. 물어볼 때는 **무엇을 말하면 되는지 구체적으로 짚어 준다.** "외형을 알려주세요"보다
   "종류·색·몸집·얼굴에서 눈에 띄는 것" 처럼 답할 거리를 준다.
9. **서비스 내부 사정을 말하지 않는다.** "비워두면 모델이 임의로 결정한다" 같은 말은
   사장님이 알 바 아니고, 안 해도 될 걱정을 시킨다.
10. 존댓말로, 동네 가게 사장님에게 말하듯 쉽게. 길이는 할 말에 맞춘다 — 짧게 끝날
    얘기를 늘이지 말고, 설명이 필요하면 줄이지도 않는다.

**reasoning 을 먼저 쓴다.** 사장님이 방금 한 말이 무슨 뜻인지, 지금 무엇이 필요한지
(질문에 답해야 하는지, 예를 줘야 하는지, 그냥 다음 칸을 물으면 되는지)를 한두 문장으로
정리한 **뒤에** reply 를 쓴다.

출력은 이 모양의 JSON만 (이 순서 그대로): {"reasoning": "...", "reply": "..."}
"""

_KEYWORDS_SYSTEM = """\
너는 한국 소상공인 사장님이 만든 가게 마스코트 캐릭터의 퍼스널 키워드를 정한다.

사장님이 적은 캐릭터 시트를 보고, 이 캐릭터의 성격을 나타내는 키워드를 3~5개 뽑는다.

규칙:
1. **사장님이 적은 내용에서만 뽑는다.** 시트에 근거가 없는 성격은 넣지 않는다.
   업종에서 연상한 성격도 넣지 않는다.
2. 한국어 형용사를 관형형("-한", "-운", "-로운")으로 쓰거나 짧은 명사구로 쓴다.
3. 외모 묘사(색·몸집)보다 성격·태도를 우선한다.
4. 아무 캐릭터에나 붙는 말(좋은·멋진·귀여운)은 피하고, 이 시트에만 맞는 말을 고른다.
5. 뽑을 근거가 부족하면 억지로 채우지 말고 적게 낸다. 하나도 없으면 빈 목록.
6. **reasoning → basis → why → keywords 순서로 채운다.** 시트를 읽고 이 캐릭터가 어떤
   성격으로 보이는지 먼저 한두 문장으로 정리하고, 어느 칸을 근거로 삼을지 고른 뒤에
   키워드를 쓴다. 키워드를 먼저 쓰고 근거를 붙이면 안 된다.
   basis의 label은 그 칸의 이름, quote는 그 칸에 **실제로 적혀 있는 말**에서 쓴
   부분이다. 요약하거나 지어내지 않는다. 최대 3개.
7. why — 그 말에서 이 키워드들이 어떻게 나왔는지 설명한다. 존댓말.

출력은 이 모양의 JSON만 (이 순서 그대로):
{"reasoning": "...", "basis": [{"label": "...", "quote": "..."}],
 "why": "...", "keywords": ["...", "..."]}
"""

# "외형 다시 하고 싶어"·"아웃핏 말고 외형 바꿀래" 같은 말을 받아내기 위한 것.
# **시트를 채우는 중에도 쓴다** — 아웃핏을 묻고 있는데 사장님이 외형 얘기를 하면
# 그쪽으로 옮겨가야 한다. 이게 없으면 묻는 칸에 갇혀 같은 질문만 반복했다.
_EDIT_SYSTEM = """\
사장님이 캐릭터 시트를 만들다가 한 말이다. 이 말이 **어느 칸 얘기인지**
가려내 JSON으로 답한다. 시트가 다 찼을 수도, 채우는 중일 수도 있다.

칸의 키: look(외형) outfit(아웃핏) desc(설명) abilities(능력) age(나이) gender(성별)
name(이름) keywords(퍼스널 키워드)

규칙:
1. 특정 칸을 정하거나 다시 정하고 싶다는 뜻이면 intent를 "edit"로, field에 그 칸의
   키를 넣는다. 칸 이름을 직접 말할 수도 있고, 지금 적힌 값이 마음에 안 든다는 식으로
   말할 수도 있다 — 어느 쪽이든 **그 말이 가리키는 칸**을 낸다.
   정해진 표현으로 가리지 말고 뜻을 본다.
   **지금 묻고 있는 칸과 다른 칸을 말해도 그 칸을 낸다** — 사장님은 순서대로
   답할 의무가 없고, 한 칸을 정하다가 앞 칸으로 돌아갈 수도 있다.
2. 어떻게 바꿀지까지 말했으면 value에 **그 칸에 적힐 새 값**을 넣는다. 아직 안 말했으면
   value는 빈 문자열로 둔다. value는 명사구로 쓰고 지어내지 않는다 — 사장님이 말한 것만.
3. **캐릭터를 통째로 다시 만들고 싶다는 뜻**이면 intent를 "restart"로 한다.
4. 그림을 다시 뽑아달라는 뜻이면 intent를 "regenerate"로 한다.
5. 캐릭터 얘기가 아니거나 어느 칸인지 알 수 없으면 intent를 "none"으로 한다.

**reasoning 을 먼저 쓴다.** 이 말이 무슨 뜻인지 한 문장으로 정리한 뒤에 나머지를 채운다.

출력은 이 모양의 JSON만 (이 순서 그대로):
{"reasoning": "...", "intent": "edit", "field": "look", "value": ""}
"""


def available() -> bool:
    """LLM을 쓸 수 있는가. 키가 없으면 조용히 규칙 기반으로 돈다."""
    return bool(settings.openai_api_key)


def _ask(system: str, user: str, temperature: float = 0.0) -> dict:
    """LLM에 묻고 JSON을 받는다. 무엇이 잘못되든 빈 dict — 대화를 막지 않는다."""
    if not available():
        return {}
    try:
        response = requests.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": temperature,
            },
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:  # 네트워크·인증·응답 형식 무엇이든
        # 키를 로그에 흘리지 않는다 — 예외 문자열에 URL은 남아도 헤더는 남지 않는다.
        logger.warning("시트 LLM 호출 실패, 규칙 기반으로 진행합니다: %s", type(exc).__name__)
        return {}


def _log_reasoning(where: str, parsed: dict) -> None:
    """모델이 먼저 적은 추론을 로그에 남긴다.

    값으로 쓰지는 않는다. 판단이 이상하게 나왔을 때 **무엇을 어떻게 읽었는지**를
    되짚을 단서가 이것뿐이라 남긴다 — 예전처럼 키워드 목록으로 가리지 않으니,
    틀렸을 때 고칠 자리는 프롬프트고 그 단서가 여기 있다.
    """
    reasoning = parsed.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        logger.info("[%s] %s", where, reasoning.strip()[:200])


def _sheet_summary(char) -> str:
    from app.services import character_sheet as sheet

    lines = []
    for field in sheet.ORDER:
        value = sheet.value_of(char, field)
        lines.append(f"- {sheet.LABELS[field]}({field}): {value or '(아직 비어 있음)'}")
    keywords = sheet.value_of(char, sheet.KEYWORDS_FIELD)
    lines.append(f"- {sheet.KEYWORDS_LABEL}({sheet.KEYWORDS_FIELD}): {keywords or '(아직 비어 있음)'}")
    return "\n".join(lines)


def _context_rows(char, store) -> list[tuple[str, str]]:
    """모델에게 준 배경을 (라벨, 값) 쌍으로. 근거를 되짚을 때 이 목록에 대고 맞춘다."""
    from app.services import character_sheet as sheet

    rows: list[tuple[str, str]] = []
    if store is not None:
        for label, attr in (("업종", "category"), ("가게 소개", "desc"),
                            ("영업시간", "hours"), ("주소", "address")):
            value = (getattr(store, attr, "") or "").strip()
            if value:
                rows.append((label, value))
        for item in (getattr(store, "images", None) or []):
            name = str(item.get("label", "")).strip() if isinstance(item, dict) else ""
            if name:
                rows.append(("대표 상품", name))
    for field in sheet.ORDER + [sheet.KEYWORDS_FIELD]:
        value = sheet.value_of(char, field)
        if value:
            rows.append((sheet.LABELS.get(field, sheet.KEYWORDS_LABEL), value))
    return rows


def _infer_basis(why: str, char, store) -> list[dict]:
    """모델이 basis를 비워 보냈을 때, why에 실제로 나온 말을 배경에서 찾아 근거로 삼는다.

    temperature를 올려 뒀기 때문에(제안이 매번 같으면 그게 고정이다) 모델이 출력 형식을
    **매번** 지키지는 않는다. 배포 서버 실측: why에 "꽃집에 어울리는"이라고 써 놓고
    basis는 []로 보내는 경우가 잦았다. 그럴 때 조용히 근거 없는 카드가 된다.

    지어내지 않는다 — **why와 배경 양쪽에 다 있는 말**만 근거로 올린다. 모델이 스스로
    근거라고 말한 것을 원문에 대고 확인하는 것이라, 없는 말이 붙을 일은 없다.
    """
    said = (why or "").replace(" ", "")
    if not said:
        return []
    found: list[dict] = []
    for label, value in _context_rows(char, store):
        stripped = value.replace(" ", "")
        # 값이 통째로 언급됐거나(업종 "꽃집"), 값의 특징적인 조각이 언급됐을 때.
        hit = stripped in said or any(
            len(stripped[i:i + 3]) == 3 and stripped[i:i + 3] in said
            for i in range(max(len(stripped) - 2, 0))
        )
        if hit and not any(b["quote"] == value for b in found):
            found.append({"label": label, "quote": value})
        if len(found) == 3:
            break
    return found


def _store_summary(store) -> str:
    """가게 정보를 프롬프트에 넣을 몇 줄로. 없으면 '모른다'고 분명히 적는다.

    이게 없으면 모델이 아는 업종은 프롬프트에 적힌 예시뿐이다. 실제로 그래서 어느
    가게에나 빵집 캐릭터를 제안했다 — 사장님 눈에는 정해진 답을 띄우는 것으로 보인다.
    모른다는 사실을 적어 두는 것도 중요하다. 비워 두면 모델이 빈칸을 상상으로 메운다.
    """
    if store is None:
        return "(가게 정보를 아직 모른다. 업종을 짐작해서 제안하지 마라.)"

    rows = [
        ("업종", (getattr(store, "category", "") or "").strip()),
        ("가게 소개", (getattr(store, "desc", "") or "").strip()),
        ("영업시간", (getattr(store, "hours", "") or "").strip()),
        ("주소", (getattr(store, "address", "") or "").strip()),
    ]
    known = [f"- {label}: {value}" for label, value in rows if value]
    if not known:
        return "(가게 정보가 아직 비어 있다. 업종을 짐작해서 제안하지 마라.)"

    images = getattr(store, "images", None) or []
    labels = [str(i.get("label", "")).strip() for i in images if isinstance(i, dict)]
    labels = [label for label in labels if label]
    if labels:
        known.append(f"- 대표 상품: {', '.join(labels[:5])}")
    return "\n".join(known)


def _context(char, store, extra: str = "") -> str:
    """모델에게 주는 배경 전부 — 가게 + 시트. 모든 호출이 같은 배경을 본다."""
    block = (
        f"[가게]\n{_store_summary(store)}\n\n"
        f"[지금까지 채워진 캐릭터 시트]\n{_sheet_summary(char)}"
    )
    return f"{block}\n\n{extra}" if extra else block


def understand(char, text: str, asked_field: str = "", store=None) -> dict:
    """사장님 문장 하나를 읽고 **무엇을 어디에 할지**까지 한 번에 가려낸다.

    돌려주는 모양:
        {"fields": {"look": "..."},   # 시트에 넣을 값 (없으면 {})
         "target": "look",            # 사장님이 지금 얘기하는 칸 (모르면 "")
         "wants_help": False}         # 그 칸을 대신 정해달라는 뜻인가

    **가이드 순서(외형→아웃핏→…)는 안내일 뿐이다.** 어느 칸 얘기인지는 여기서 LLM이
    가리고, 라우터는 그 결과를 따라간다. 예전에는 라우터가 "지금 묻는 칸"에 못 박아
    둬서, 아웃핏을 묻는 중에 외형 얘기를 해도 계속 아웃핏만 물었다.

    `wants_help`가 중요한 이유 — "베이커리 잘하게 생긴 놈으로"는 **묘사가 아니라
    부탁**이다. 예전에는 이 말이 외형 칸에 글자 그대로 적혔다. 사장님은 그렇게
    생긴 걸 만들어 달라고 한 것이지, 그 문장을 시트에 적어 달라고 한 게 아니다.

    fields 값은 전부 사장님 문장(또는 그 칸의 기존 값)에 뿌리를 둬야 한다. 아래에서
    한 번 더 거른다 — 모델이 규칙을 어기고 빈 칸을 채우려 드는 경우가 있다.
    """
    from app.services import character_sheet as sheet

    empty = {"fields": {}, "target": "", "wants_help": False}
    if not available() or not (text or "").strip():
        return empty

    asked_label = sheet.LABELS.get(asked_field, "")
    prompt = _context(
        char, store,
        f"[지금 묻고 있는 칸]\n{asked_label or '(없음)'}\n\n"
        f"[사장님이 방금 한 말]\n{text.strip()}",
    )
    parsed = _ask(_EXTRACT_SYSTEM, prompt, _T_EXTRACT)

    _log_reasoning("사장님 말 해석", parsed)

    target = parsed.get("target")
    target = target if target in _FILLABLE else ""
    wants_help = bool(parsed.get("wants_help"))

    fields = parsed.get("fields")
    if not isinstance(fields, dict):
        return {"fields": {}, "target": target, "wants_help": wants_help}

    cleaned: dict[str, str] = {}
    for field, value in fields.items():
        if field not in _FILLABLE or not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        # 그 칸의 기존 값도 근거로 친다. 규칙 7(덧붙이기)이 기존 값을 합쳐 내보내는데,
        # 사장님 문장만 근거로 삼으면 합쳐진 값이 통째로 버려진다.
        existing = sheet.value_of(char, field)
        source = f"{text} {existing}" if existing else text
        # 모델이 길게 늘여 쓴 경우를 막는다. 사장님이 한 줄 말했는데 세 줄이 돌아오면
        # 그건 요약이 아니라 창작이다. 덧붙이기를 허용하므로 기존 값 길이를 감안한다.
        if len(value) > len(source) + 40:
            continue
        # 지금 묻고 있는 칸이 아니면, 근거가 있어야 받는다.
        # 프롬프트로 "지어내지 마라"를 아무리 적어도 모델은 빈 칸을 채우려 든다 —
        # 실제로 "소금빵을 잘 구워요" 한마디에 성별과 이름까지 지어내는 걸 봤다.
        if field != asked_field and not _grounded(value, source):
            logger.info("근거 없는 칸 '%s'을(를) 버렸습니다", field)
            continue
        cleaned[field] = value

    # 대신 정해달라는 뜻이면 시트에 넣지 않는다.
    #
    # 예전에는 여기에 "몰라|알아서|아무거나|추천해…" 정규식이 있었다. 그건 **적어 둔 말만**
    # 걸러서, 적지 않은 표현("형이 골라줘", "판단해줘")은 그대로 통과했다. 목록을 늘릴수록
    # 목록 밖은 더 안 걸린다 — 말을 맞히는 방식이 애초에 틀렸다.
    # 지금은 모델이 reasoning 으로 뜻을 먼저 정리하고 wants_help 로 답하며, 그 판단만 쓴다.
    if wants_help and cleaned:
        logger.info("대신 정해달라는 뜻이라 읽어낸 값을 시트에 넣지 않습니다: %s", list(cleaned))
        cleaned = {}
    return {"fields": cleaned, "target": target, "wants_help": wants_help}


# 제안 값에 붙어 나오는 조언 어미. 프롬프트로 "명사구로 쓰라"고 해도 모델은 사장님에게
# 말을 건다 — 실제로 외형 칸에 "…귀여운 곰으로 해보세요." 가 그대로 적히는 걸 봤다.
# 시트에 적히는 건 값이지 말이 아니다.
#
# "입히면 좋겠어요"처럼 앞 낱말이 어미를 끌고 오는 꼴이라, `~면`으로 끝나는 앞말까지
# 같이 걷어낸다. 안 그러면 "흰 앞치마를 입히면"이 남아 여전히 문장이다.
_ADVICE_TAIL = re.compile(
    r"\s*(?:"
    r"(?:\S+(?:면|려면)\s+)?좋(?:겠어요|겠습니다|을\s*것\s*같아요|아요|습니다)"
    r"|(?:으로|로)?\s*해\s*보(?:세요|시면\s*좋\S*|는\s*게\s*좋\S*)"
    r"|어떨까요|어떠세요|어때요|어떻(?:겠어요|습니까)"
    r"|추천\s*(?:드려요|드립니다|해요|합니다)"
    r")\s*[.!?~…]*$"
)
# 값 끝의 서술 종결. "귀여운 곰이에요" → "귀여운 곰".
_COPULA_TAIL = re.compile(r"(?:이에요|예요|이예요|입니다|이야|이다)\s*[.!?~…]*$")
# 꼬리를 자른 뒤에 남는 부스러기.
_DANGLING_ADVERB = re.compile(r"\s+(?:잘|좀|더|많이|아주|매우)$")
_DANGLING_PARTICLE = re.compile(r"(?:을|를|은|는|으로|로)$")


def _as_value(text: str) -> str:
    """제안 문장에서 시트 칸에 적을 값만 남긴다."""
    value = (text or "").strip()
    trimmed = False
    for _ in range(2):  # "…로 해보시면 좋겠어요" 처럼 두 겹으로 붙는 경우가 있다
        cut = _ADVICE_TAIL.sub("", value).strip()
        if cut == value:
            break
        value, trimmed = cut, True
    cut = _COPULA_TAIL.sub("", value).strip()
    if cut != value:
        value, trimmed = cut, True
    if trimmed:
        # 조사 정리는 **잘라낸 값에만** 한다. 원래부터 명사구였던 값은 건드리지 않는다 —
        # "구웅이"의 '이'는 조사가 아니라 이름의 일부다. 그래서 조사 목록에도 이/가는 없다.
        value = _DANGLING_ADVERB.sub("", value).strip()
        value = _DANGLING_PARTICLE.sub("", value).strip()
    return value.rstrip(" .!?~,")


def _grounded(value: str, text: str) -> bool:
    """값이 사장님 문장에 실제로 뿌리를 두고 있는가.

    통째로 같기를 요구하면 너무 빡빡하다 — "소금빵을 잘 구워요"에서 능력을 뽑으면
    "소금빵 굽기"가 되는 게 자연스럽다. 그래서 두 글자 이상 겹치는 조각이 있으면
    근거가 있다고 본다. "남성"·"구름이"처럼 문장에 흔적조차 없는 말은 여기서 걸린다.

    **양쪽 다 띄어쓰기를 지운 뒤에 견준다.** 예전에는 원문만 지웠는데, 그러면 "세 살"
    처럼 값에 공백이 있는 순간 조각이 "세 "·" 살"이 되어 어디에도 안 걸린다. 실제로
    "세 살이고 이름은 꽃순이예요"에서 나이가 통째로 버려졌다(배포 서버 실측).
    """
    needle = (value or "").replace(" ", "")
    haystack = (text or "").replace(" ", "")
    return any(
        needle[i:i + 2] in haystack
        for i in range(max(len(needle) - 1, 1))
        if len(needle[i:i + 2]) == 2
    )


def propose_field(char, field: str, text: str, store=None) -> dict:
    """사장님이 "몰라, 알아서 해줘"라고 했을 때 그 칸에 넣을 값을 하나 제안한다.

    돌려주는 모양:
        {"value": "…", "basis": [{"label": "업종", "quote": "꽃집"}], "why": "…"}
    제안할 게 없으면 **빈 dict** — 그러면 호출부가 그냥 되묻는다. 인사나 잡담에 대고
    캐릭터 설정을 지어내기 시작하면 사장님이 정한 적 없는 캐릭터가 된다.

    여기서 나온 값은 `understand()`와 달리 **사장님 문장에 근거가 없다.** 그래서
    시트에 바로 넣지 않고 승인 카드로 올린다. 참고한 게 있으면 basis에 담겨 오고,
    없으면 빈 목록이다 — **근거가 없다고 제안을 막지 않는다.** 가게 정보는 참고
    자료이지 제안의 조건이 아니다. 캐릭터를 정하는 건 사장님이고, 여기는 사장님이
    "대신 정해달라"고 했을 때 하나 꺼내 보여주는 자리일 뿐이다.
    """
    from app.services import character_sheet as sheet

    if not available() or not field:
        return {}

    label = sheet.LABELS.get(field, "")
    prompt = _context(
        char, store,
        f"[지금 묻고 있는 칸]\n{label}({field})\n\n"
        f"[사장님이 방금 한 말]\n{(text or '').strip()}",
    )
    # 무엇을 제안할지는 **여기서도 프롬프트에서도 정하지 않는다.** 금지어로 소재를
    # 막는 것도, "가게 정보에서 끌어내야만 한다"고 못 박는 것도 똑같이 고정이다 —
    # 전자는 곰을 원하는 사장님이 곰을 못 받게 하고, 후자는 가게 정보가 비면 아무것도
    # 제안하지 못하게 한다. 가게 정보는 참고 자료일 뿐이다.
    # 코드가 보장하는 건 형식뿐이다: 명사구인가(_as_value), 한 문단을 넘지 않는가.
    parsed = _ask(_PROPOSE_SYSTEM, prompt, _T_PROPOSE)
    _log_reasoning("제안 판단", parsed)
    value = _proposal_from(parsed)
    # **길이로 버리지 않는다.** 예전에는 90자를 넘으면 통째로 버렸는데, 그러면 "알아서
    # 정해줘"라고 한 사장님에게 아무 제안도 못 준다. 길면 긴 대로 카드에 올리고, 보고
    # 정하는 건 사장님 몫이다 — 시트의 외형·아웃핏·설명·능력은 여러 줄 입력 칸이다.
    if not value:
        return {}
    return {"value": value, **evidence_from(parsed, char, store)}


def _proposal_from(parsed: dict) -> str:
    """제안 응답에서 시트에 적을 값만. 대신 정해달라는 뜻이 아니면 빈 문자열."""
    if parsed.get("intent") != "help":
        return ""
    value = parsed.get("proposal")
    if not isinstance(value, str):
        return ""
    # 프롬프트에 "명사구로 쓰라"고 적어도 모델은 사장님에게 말을 건다. 프롬프트는
    # 부탁이고 코드가 보장이다 — 조언 어미는 여기서 잘라낸다.
    return _as_value(value)


def evidence_from(parsed: dict, char, store) -> dict:
    """응답에서 근거(basis·why)만 추려 검증한다. 못 믿을 건 버린다.

    **인용한 말이 실제로 가게 정보나 시트에 있어야 한다.** 모델은 "업종: 꽃집"처럼
    그럴듯한 근거를 지어낼 수 있는데, 그러면 근거를 보여주는 게 오히려 사장님을
    속이는 일이 된다. 여기서 원문에 대고 맞춰 보고 안 맞으면 그 줄을 버린다.

    근거가 하나도 안 남아도 제안 자체는 살린다 — 가게 정보가 비어 있을 때는 근거로
    쓸 말이 없는 게 정상이다. 그때는 화면에 근거 칸이 안 보일 뿐이다.
    """
    haystack = f"{_store_summary(store)}\n{_sheet_summary(char)}"
    basis = []
    for row in (parsed.get("basis") or [])[:3]:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip()
        quote = str(row.get("quote", "")).strip()
        if not label or not quote:
            continue
        if quote not in haystack and not _grounded(quote, haystack):
            logger.info("근거로 적힌 말이 원문에 없어 버렸습니다: %s / %s", label, quote[:30])
            continue
        basis.append({"label": label, "quote": quote})

    why = parsed.get("why")
    why = why.strip() if isinstance(why, str) else ""
    # 길이로 버리지 않는다 — 버리면 왜 그렇게 정했는지가 통째로 사라진다.
    # 모델이 근거를 빠뜨렸으면 why에 나온 말을 배경에서 되짚어 본다. 형식을 매번 지키진
    # 않기 때문이다 — 그래도 근거 없는 카드보다는 확인된 근거를 보여주는 게 낫다.
    if not basis and why:
        basis = _infer_basis(why, char, store)
    return {"basis": basis, "why": why}


def reply(char, text: str, filled: dict[str, str], ask_field: str, store=None) -> str:
    """사장님 말에 **대답하고** 다음 칸을 물어보는 한 문단. 못 만들면 빈 문자열.

    이게 없으면 화면이 설문지가 된다. 실제로 사장님이
    "배불뚝이 아저씨 오너인데 캐릭터화하면 뭘 하면 좋을까"라고 물었는데,
    외형만 뜯어 적고 "무엇을 입고 있으면 좋을까요?"로 넘어가 버렸다. **질문에
    대답을 안 한 것이다.** 시트를 채우는 건 대화의 결과여야지 목적이 아니다.

    돌려주는 건 **말뿐이다.** 여기서 나온 문장이 시트에 적히는 일은 없다 —
    칸을 채우는 건 `understand()`와 `propose_field()`만 한다.
    """
    from app.services import character_sheet as sheet

    if not available() or not ask_field:
        return ""

    noted = ", ".join(
        f"{sheet.LABELS[f]} = {v}" for f, v in (filled or {}).items() if f in sheet.LABELS
    )
    prompt = _context(
        char, store,
        f"[방금 시트에 적은 것]\n{noted or '(없음)'}\n\n"
        f"[다음에 물어볼 칸]\n{sheet.LABELS.get(ask_field, '')}({ask_field})\n"
        f"그 칸의 기본 질문: {sheet.QUESTIONS.get(ask_field, '')}\n\n"
        f"[사장님이 방금 한 말]\n{(text or '').strip()}",
    )
    parsed = _ask(_REPLY_SYSTEM, prompt, _T_REPLY)
    _log_reasoning("대화 판단", parsed)
    value = parsed.get("reply")
    if not isinstance(value, str):
        return ""
    value = value.strip()
    # 너무 길면 대화가 아니라 설명문이다. 화면 한 칸에 들어가야 한다.
    # 길면 긴 대로 보여준다. 예전엔 400자를 넘으면 버리고 정해진 문장으로 떨어졌는데,
    # 그게 "무슨 말을 해도 같은 소리를 한다"로 보였다. 빈 응답만 거른다.
    return value


def suggest_keywords(char, limit: int = 5, store=None) -> dict:
    """퍼스널 키워드를 뽑는다.

    돌려주는 모양: {"keywords": [...], "basis": [...], "why": "…"}
    못 하면 **빈 dict** — 호출부가 정규식 추출로 되돌아간다.
    """
    if not available():
        return {}
    parsed = _ask(_KEYWORDS_SYSTEM, _context(char, store), _T_KEYWORDS)
    _log_reasoning("키워드 판단", parsed)
    words = parsed.get("keywords")
    if not isinstance(words, list):
        return {}
    picked = [w.strip() for w in words if isinstance(w, str) and w.strip()][:limit]
    if not picked:
        return {}
    return {"keywords": picked, **evidence_from(parsed, char, store)}


def detect_edit_target(char, text: str, store=None) -> dict:
    """다 찬 시트에서 사장님이 **무엇을 고치려는지** 읽어낸다.

    돌려주는 모양: {"intent": "edit"|"restart"|"regenerate"|"none",
                   "field": "<시트 키>", "value": "<새 값 또는 빈 문자열>"}

    이게 없으면 시트가 다 찬 뒤에는 대화가 죽는다. 실제로 "외형 다시 하고 싶어"라고
    해도 읽어낼 값이 없어 빈 dict가 돌아왔고, 라우터는 "고치고 싶은 칸을 시트에서
    눌러주세요"만 반복했다 — 대화로 만든 캐릭터를 대화로는 못 고쳤다.
    """
    from app.services import character_sheet as sheet

    empty = {"intent": "none", "field": "", "value": ""}
    if not available() or not (text or "").strip():
        return empty

    parsed = _ask(
        _EDIT_SYSTEM,
        _context(char, store, f"[사장님이 방금 한 말]\n{text.strip()}"),
        _T_INTENT,
    )
    _log_reasoning("칸 판단", parsed)
    intent = parsed.get("intent")
    if intent not in ("edit", "restart", "regenerate"):
        return empty
    if intent != "edit":
        return {"intent": intent, "field": "", "value": ""}

    field = parsed.get("field")
    if field not in sheet.ORDER and field != sheet.KEYWORDS_FIELD:
        return empty

    value = parsed.get("value")
    value = _as_value(value) if isinstance(value, str) else ""
    # 새 값은 사장님 문장에 근거가 있어야 한다. 고치겠다는 말만 했는데 모델이 값까지
    # 지어내면 그건 사장님이 정한 적 없는 수정이 된다.
    if value and not _grounded(value, text):
        logger.info("근거 없는 수정 값이라 값만 버리고 칸만 엽니다: %s", value[:40])
        value = ""
    return {"intent": "edit", "field": field, "value": value}
