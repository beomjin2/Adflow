# Adflow

빵집 사장님이 마스코트 캐릭터를 만들고, 그 캐릭터로 광고(4컷 등)를 뽑는 서비스.
FastAPI 백엔드 + React/Vite 프론트엔드, 그림은 팀 VM의 ComfyUI(Anima 모델)가 그린다.

```
backend/   FastAPI. app/api/routes(엔드포인트) · app/services(생성·프롬프트·잡 워커) · app/services/workflows(ComfyUI 그래프)
frontend/  React + Vite. /frontend/ 경로로 서빙, /api 는 백엔드로 프록시
deploy/    VM 배포 스크립트와 사람이 직접 할 명령 (deploy/USER_COMMANDS.md)
```

## 로컬 실행

**백엔드**

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # Windows. macOS/Linux는 source .venv/bin/activate
pip install -r requirements.txt
pip install tzdata                                   # Windows만. chat_ai.py의 ZoneInfo("Asia/Seoul")에 필요
cp .env.example .env                                 # 값 채우기 (아래 "설정")
uvicorn app.main:app --host 127.0.0.1 --port 9010
```

`app.db`(SQLite)는 첫 기동 때 만들어진다. 모델 컬럼이 바뀐 뒤 옛 `app.db`가 남아 있으면
`no such column` 오류가 나므로 지우고 다시 띄운다(로컬 데이터는 테스트용이다).

**프론트엔드**

```bash
cd frontend
npm install
echo VITE_API_PROXY_TARGET=http://127.0.0.1:9010 > .env.local   # 로컬 백엔드로 프록시. 없으면 VM으로 간다
npm run dev                                                     # http://localhost:5173/frontend/
```

`CORS_ORIGINS`(백엔드 .env)에 프론트 주소가 들어 있어야 한다. 5173이 사용 중이면 Vite가
5174로 올라가니 그 주소도 추가한다.

## 설정 (backend/.env)

| 키 | 뜻 |
|---|---|
| `COMFY_BASE_URL` / `COMFY_USER` / `COMFY_PASSWORD` | VM ComfyUI(nginx Basic Auth 뒤). 비우면 그림이 안 만들어지고 칸이 `failed`로 남는다 |
| `COMFY_WORKFLOW_FILE` | `app/services/workflows/` 밑 그래프 파일. 기본 `character_practice.json` |
| `OPENAI_API_KEY` | 캐릭터 설명을 Danbooru 태그로 바꾸는 데 쓴다. 비우면 화이트리스트로 폴백(아래) |
| `OPENAI_MODEL` | 기본 `gpt-4o-mini` |
| `DANBOORU_TAGS_PATH` | 태그 검증용 parquet 경로. 기본 `data/danbooru_tags/danbooru.donmai.us/tags.parquet` (backend/ 기준) |
| `MEDIA_DIR` | 생성 PNG 저장 폴더. `/api/media/<파일명>`으로 서빙. 기본 `media` |

## 캐릭터 생성 흐름

채팅 또는 왼쪽 폼에 외형을 쓴다 → **후보 3장**(백그라운드 생성, 프론트가 3초마다 폴링)
→ 하나 선택 → 확정. (예전의 4방향 생성은 09-17에 뺐다 — 네컷은 고른 그림 1장을
IP-Adapter 참조로 써서 구도를 바꾸므로 4방향은 GPU만 쓰고 쓰이지 않았다. DB `views` 컬럼은 빈 채로 남는다.)
생성 요청은 즉시 돌아오고 칸의 `status`가 `generating → done | failed`로 바뀐다
(`app/services/jobs.py`). 그림은 파일로 저장되고 응답엔 URL만 실린다.

## 캐릭터 프롬프트 파이프라인 (한국어 설명 → Danbooru 태그)

### 왜

Anima는 Danbooru 태그로 학습된 모델이다. "통통한 하얀 토끼, 짝눈" 같은 한국어 문장을
그대로 넣으면 얼버무리거나 화풍이 흔들린다. 실존하지 않는 태그 조합을 넣으면 엉뚱한 그림이
나온다(예: `empty restaurant interior` → 교실). 그래서 **실제로 Danbooru에 존재하고
게시물 2,000장 이상인 태그만** 프롬프트에 넣는다.

### 흐름

```
char.look (한국어)
   │
   ▼  app/services/chat_ai.py  character_prompt(char, hint)
STYLE_TAGS  +  tags_for_look(look)  +  hint(후보 리롤 시 "variation N")
                     │
                     ▼  app/services/danbooru_tags.py
        ① GPT(gpt-4o-mini, temperature 0)가 태그 후보를 뽑는다
              시스템 프롬프트에 few-shot: chubby→plump, white rabbit→rabbit+white_fur,
              star mark→star_(symbol), bandage→bandaid, red scarf→scarf+red_scarf …
        ② danbooru_lookup.verify_tags(): parquet에 대고
              실존 여부 + post_count ≥ 2,000 인 것만 남긴다 (순서 유지, 중복 제거)
        ③ ①②가 빈 결과면 KEYWORD_TO_TAG 화이트리스트(30여 개 — 토끼 캐릭터 태그 12개만
              게시물수 확인됨, 나머지는 미검증. 사전에 없는 단어는 버린다)
        ④ 그래도 없으면 한국어 원문 그대로 (upstream 원래 동작)
```

예: `통통한 하얀 토끼, 짝눈(초록/보라), 빨간 줄무늬 목도리, 별무늬` →
`masterpiece, best quality, score_7, safe, solo, (chibi:1.3), full body, simple background, plump, rabbit, white_fur, heterochromia, scarf, star_(symbol)`

- `STYLE_TAGS`는 '연습용' 워크플로우와 함께 조정된 접두어라 그대로 둔다.
- 네컷의 구도는 스토리 제안(`meme_ai.py`)이 고른 `CAMERA_TAGS`(straight-on, close-up,
  from_side, from_below, from_above, wide_shot — 전부 실존 태그)를 컷마다 붙여 바꾼다.
  Danbooru엔 좌/우를 가르는 태그가 없다(좌우는 참조 이미지·시드에 맡긴다).

### 태그 검증용 parquet 준비

HuggingFace `deepghs/site_tags`(CC-BY-4.0) 중 Danbooru 부분(약 76MB, 159만 행)만 받는다.
`backend/data/`는 gitignore라 각자 받아야 한다.

```bash
cd backend
pip install huggingface_hub
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='deepghs/site_tags', repo_type='dataset', filename='danbooru.donmai.us/tags.parquet', local_dir='data/danbooru_tags')"
```

VM에는 `/home/spai1122/danbooru_tags/danbooru.donmai.us/tags.parquet`에 받아 두었다.
VM에서 돌릴 때는 `DANBOORU_TAGS_PATH`를 그 절대경로로 준다.

### 동작 확인

GPU 없이 프롬프트 조립만 확인한다(GPT는 호출됨).

```bash
cd backend
python -c "
from types import SimpleNamespace
from app.services import chat_ai
c = SimpleNamespace(look='통통한 하얀 토끼, 짝눈(초록/보라), 빨간 줄무늬 목도리, 별무늬', name='', age='', gender='', hobby='')
print(chat_ai.character_prompt(c))"
```

한국어 원문이 그대로 남아 있으면 GPT·화이트리스트 둘 다 실패한 것이다. 백엔드 로그에
`GPT 태그 생성 실패 — 화이트리스트로 폴백`이 찍히면 키·네트워크·`openai` 버전을 본다
(`openai`는 httpx 0.28+와 맞는 3.x를 쓴다. 1.54.x는 `proxies` 인자 오류로 깨진다).

### 알려진 한계 / 후속

- "짝눈(초록/보라)"처럼 **괄호 안 색은 태그로 잘 안 뽑힌다** → `heterochromia`만 남아 눈 색이 매번 달라진다. few-shot 보강 후보.
- `striped_scarf` / `red_scarf` 같은 수식 태그가 GPT 호출마다 들쭉날쭉하다.
- `STYLE_TAGS`에 `no humans`가 없어 동물 마스코트가 옷 입은 의인화로 흐를 때가 있다.
- `character_prompt()`는 요청 스레드에서 GPT를 부른다(호출당 1–2초, 후보 리롤마다). look이 바뀔 때만 태그를 계산해 두는 캐시가 후보.
- NSFW 명시 negative 목록은 넣지 않았다(negative는 '연습용'과 함께 조정됐다는 주석을 존중, 팀 확인 후).
- 왼쪽 폼의 값은 후보 생성·리롤 전에 서버로 보낸다(`useAdMakerState.js`의 `syncCharForm`).

조사·결정 기록: 프로젝트 저장소 `.claude/brainstorm/research/48-adflow-upstream-merge-2026-09-16.md`.

## 배포

`deploy/USER_COMMANDS.md`를 따른다.
