"""연출 — 대사 GPT(story_llm)가 낸 컷(line·action)을 받아 컷마다 **그림 슬롯**을 채운다.

대사 GPT 는 건드리지 않는다(지연). 그 뒤에 이 단계를 끼워, 팀장 슬롯 시트의 컷 층
(shot.size·angle·count·position · gaze · 표정·동작·장소·소품·빛)을 GPT(mini)가 채운다.
이게 있어야 컷마다 크기·각도·위치가 달라진다 — 없으면 접두어 full body 때문에 전부 가운데 전신(09-21 실측 20/20).
슬롯 → 태그 변환은 chat_ai.comic_prompt_slots, 위치는 image_gen.POSITION_CROP 이 맡는다.
GPT 를 못 쓰면 None — 호출부가 옛 경로(comic_prompt)로 간다.
"""
from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

SHOT_SIZE_CHOICES = ("아주작게", "작게", "보통", "크게", "아주크게")
SHOT_ANGLE_CHOICES = ("정면", "위에서", "아래에서", "옆에서", "뒤에서")
SHOT_COUNT_CHOICES = ("혼자", "여럿")
SHOT_POSITION_CHOICES = ("왼쪽", "가운데", "오른쪽")
GAZE_CHOICES = ("정면", "옆", "아래", "상대", "눈감음")

# 광고 느낌별 연출 힌트 — 대사 쪽 레시피가 아니라 그림 쪽만(빛·표정 폭·소품).
CONCEPT_HINTS = {
    "유쾌함": "표정은 크게(놀람·활짝·멍함), 3컷은 shot.size 를 1·2컷과 반대로 잡아 대비를 만든다.",
    "감성": "light 를 네 컷 다 채운다(새벽 어스름 → 아침 햇살 → 낮 → 노을). 표정은 미소·눈 감음처럼 잔잔하게.",
    "정보형": "shot.size 는 보통·크게 위주로 빵이 잘 보이게, props 에 실제 빵 이름. 표정은 차분한 미소 하나.",
    "담백함": "props 는 하나(그중 하나는 빵), light 는 비운다. 표정은 무표정·옅은 미소 둘만.",
}

_DIRECT_PROMPT = (
    "당신은 네컷 만화의 **연출**이다. 작가가 쓴 대사(lines)와 컷 상황(beats)을 받아 컷마다 그림 슬롯을 채운다. 대사는 바꾸지 않는다.\n\n"
    "컷마다 아래 칸을 채운다. shot 과 gaze 는 반드시 주어진 선택지 중 하나만 쓴다.\n"
    f"  shot.size      {' | '.join(SHOT_SIZE_CHOICES)}  (캐릭터가 화면에서 얼마나 크게)\n"
    f"  shot.angle     {' | '.join(SHOT_ANGLE_CHOICES)}\n"
    f"  shot.count     {' | '.join(SHOT_COUNT_CHOICES)}\n"
    f"  shot.position  {' | '.join(SHOT_POSITION_CHOICES)}  (캐릭터를 어느 쪽에 두고 반대쪽을 비우나)\n"
    f"  gaze           {' | '.join(GAZE_CHOICES)}  (시선 — 정면은 카메라를 본다)\n"
    "  expression     표정 — 짧은 한국어 구\n  pose           동작 — 짧은 한국어 구\n  place          장소 — 한 단어\n"
    "  props          소품 — 단어 배열\n  light          빛 — 한 단어 또는 빈 문자열\n\n"
    "만화 구도의 기본 — 예시가 보여주는 대로:\n"
    "  · 대사가 있는 컷은 캐릭터를 **왼쪽이나 오른쪽**에 두고 반대쪽을 비운다(말풍선 자리). 가운데는 대사 없는 컷이나 여럿 컷에만.\n"
    "  · 정면(angle)은 네 컷 중 최대 두 컷, 카메라를 보는 시선(gaze 정면)은 최대 한 컷. 나머지는 옆·아래·상대(손님이나 빵)를 본다.\n"
    "  · size 는 네 컷이 서로 다르게. beats 에 '멀리서·줄·거리'가 있으면 아주작게, 표정 하나에 거는 컷은 아주크게.\n"
    "  · 마지막 컷은 그림이 따로 정해져 있다(가게 앞 전경) — 슬롯은 채우되 place 는 '가게 앞'.\n\n"
    "예시 — 분식집, lines [\"마흔 줄은... 좀 무리 아닐까\", \"반만 팔려도 낮잠 잘 수 있어\", \"어... 줄이 왜 저기까지\", \"...그게 되네. 낮잠은 내일\"]:\n"
    "{\"cuts\": [\n"
    " {\"n\": 1, \"shot\": {\"size\": \"크게\", \"angle\": \"옆에서\", \"count\": \"혼자\", \"position\": \"왼쪽\"}, \"gaze\": \"아래\", "
    "\"expression\": \"걱정, 땀\", \"pose\": \"움츠리기\", \"place\": \"주방\", \"props\": [\"김밥\", \"접시\"], \"light\": \"\"},\n"
    " {\"n\": 2, \"shot\": {\"size\": \"보통\", \"angle\": \"위에서\", \"count\": \"혼자\", \"position\": \"오른쪽\"}, \"gaze\": \"옆\", "
    "\"expression\": \"긴장\", \"pose\": \"접시 놓기\", \"place\": \"가게 안\", \"props\": [\"김밥\", \"진열대\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 3, \"shot\": {\"size\": \"아주작게\", \"angle\": \"정면\", \"count\": \"여럿\", \"position\": \"가운데\"}, \"gaze\": \"상대\", "
    "\"expression\": \"멍함\", \"pose\": \"빈 접시 들기\", \"place\": \"가게 앞\", \"props\": [\"고양이 손님\", \"강아지 손님\", \"빈 접시\"], \"light\": \"아침 햇살\"},\n"
    " {\"n\": 4, \"shot\": {\"size\": \"아주작게\", \"angle\": \"정면\", \"count\": \"혼자\", \"position\": \"오른쪽\"}, \"gaze\": \"정면\", "
    "\"expression\": \"멍한 미소\", \"pose\": \"손 흔들기\", \"place\": \"가게 앞\", \"props\": [\"입간판\"], \"light\": \"\"}]}\n\n"
    "예시는 다른 업종이다 — 형식과 구도 원칙만 가져온다. JSON 하나만 출력한다."
)


def _pick(val, choices, default):
    v = str(val or "").strip()
    return v if v in choices else default


def direct(lines: list[str], beats: list[str], concept: str = "") -> list[dict] | None:
    """컷별 대사·상황 → 슬롯 목록. GPT 를 못 쓰면 None."""
    if not settings.openai_api_key or not lines:
        return None
    from app.services import trace
    hint = CONCEPT_HINTS.get((concept or "").strip(), "")
    user = (f"[광고 느낌] {concept or '(없음)'}" + (f"\n연출 힌트: {hint}" if hint else "") +
            f"\n\n[대본]\n{json.dumps({'lines': lines, 'beats': beats}, ensure_ascii=False, indent=1)}")
    try:
        with trace.timer() as t:
            resp = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
                model=settings.openai_model, temperature=0.3, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": _DIRECT_PROMPT}, {"role": "user", "content": user}],
            )
        raw = resp.choices[0].message.content or "{}"
        trace.step("그림 지시 (연출)", who=settings.openai_model, temperature=0.3, sec=t.sec, system=_DIRECT_PROMPT, sent=user, output_raw=raw)
        data = json.loads(raw)
    except Exception:
        logger.exception("연출 GPT 실패 — 옛 경로로 갑니다")
        return None
    raw_cuts = list(data.get("cuts") or [])
    out = []
    for i in range(len(lines)):
        c = raw_cuts[i] if i < len(raw_cuts) and isinstance(raw_cuts[i], dict) else {}
        shot = c.get("shot") if isinstance(c.get("shot"), dict) else {}
        props = c.get("props") or []
        out.append({
            "shot": {
                "size": _pick(shot.get("size"), SHOT_SIZE_CHOICES, "작게"),
                "angle": _pick(shot.get("angle"), SHOT_ANGLE_CHOICES, "정면"),
                "count": _pick(shot.get("count"), SHOT_COUNT_CHOICES, "혼자"),
                # 대사 있는 컷의 기본은 홀수 오른쪽·짝수 왼쪽(말풍선 반대편)
                "position": _pick(shot.get("position"), SHOT_POSITION_CHOICES, "오른쪽" if i % 2 == 0 else "왼쪽"),
            },
            "gaze": _pick(c.get("gaze"), GAZE_CHOICES, "옆"),
            "expression": str(c.get("expression") or "").strip(),
            "pose": str(c.get("pose") or "").strip(),
            "place": str(c.get("place") or "").strip(),
            "props": [str(p) for p in props] if isinstance(props, list) else [str(props)],
            "light": str(c.get("light") or "").strip(),
        })
    return out
