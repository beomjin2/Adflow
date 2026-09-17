# Adflow — 마스코트 네컷 광고 만들기

빵집 사장님이 **가게 → 캐릭터 → 광고 → 스토리 → 네컷 그림**을 순서대로 채우면
밈 템플릿을 입힌 4컷 만화 광고가 나온다. 아래 그림 세 장이 전부다.

## 1. 전체 흐름 (화면 순서)

```mermaid
flowchart LR
    S[가게 정보<br/>업종·주소·소개·사진] --> C
    subgraph C[캐릭터]
        direction TB
        C1[대화로 시트 7칸 채우기<br/>외형→아웃핏→설명→능력→나이→성별→이름] --> C2[퍼스널 키워드 자동 제안]
        C2 --> C3[그림 뽑기 · 후보 3장<br/>ComfyUI 백그라운드]
        C3 --> C4[한 장 고르기 → 확정]
    end
    C --> A[광고 종류·컨셉]
    A --> SB
    subgraph SB[스토리보드]
        direction TB
        B1[오늘 생산 기록 대화<br/>품목·수량·시각] --> B2[밈 카드 고르기]
        B2 --> B3[GPT 스토리 제안<br/>4컷 대사·행동·구도] --> B4[승인]
        B4 --> B5[네컷 그리기<br/>확정 캐릭터를 참조로 컷마다 생성]
    end
    SB --> R[결과<br/>2×2 만화 + 말풍선 + 올릴 문구 → 저장]
```

- 앞 단계가 안 끝나면 다음 단계 버튼이 잠긴다 (시트 미완 → 그림 못 뽑음, 캐릭터 미확정 → 네컷 못 그림).
- 그림 생성은 전부 백그라운드다. 요청은 바로 돌아오고 화면이 3초마다 상태를 받아 채운다.

## 2. 한국어 설명 → 그림 프롬프트

Anima는 Danbooru 태그로 학습된 모델이라 한국어 문장을 그대로 넣으면 얼버무린다.
그래서 **GPT가 태그 후보를 만들고, Danbooru 실제 태그 사전(parquet)으로 검증**한 것만 쓴다.

```mermaid
flowchart LR
    IN["시트 5칸<br/>외형·아웃핏·설명·나이·이름<br/>(또는 컷 문장)"] --> GPT["GPT<br/>Danbooru 태그 후보 생성<br/>gpt-4o-mini · temperature 0"]
    GPT --> V{"parquet 검증<br/>실존 태그이고<br/>post_count ≥ 2,000?"}
    V -- 통과 --> OK[검증된 태그]
    V -- 탈락 --> DROP[버림]
    OK --> P["프롬프트<br/>STYLE_TAGS + 캐릭터 태그<br/>(+ 장면 태그 + 구도 태그)"]
    P --> ANIMA[ComfyUI · Anima]
```

- 캐릭터 후보: `STYLE_TAGS + 캐릭터 태그` → `character_practice.json`
- 네컷 한 컷: `COMIC_STYLE_TAGS + 캐릭터 태그 + 장면 태그 + 구도 태그` → `comic_ipadapter_turbo.json`
  (확정한 그림 한 장을 IP-Adapter 참조로 넣어 캐릭터를 유지한다)
- 태그 사전: HuggingFace `deepghs/site_tags`의 `danbooru.donmai.us/tags.parquet` (`backend/data/danbooru_tags/`, git에 안 올림)

## 3. 네컷이 그려지는 순서

```mermaid
sequenceDiagram
    participant U as 화면
    participant API as FastAPI
    participant J as 작업 큐<br/>(GPU 1개씩)
    participant G as GPT
    participant CF as ComfyUI (VM)

    U->>API: POST /api/storyboard/propose (밈 카드)
    API->>G: 가게·상품·캐릭터 + 밈 템플릿 → 4컷 스토리
    G-->>API: 컷별 대사·행동·구도
    API-->>U: 제안 카드 (승인 / 거절)
    U->>API: POST /api/storyboard/comic
    API->>CF: 확정 캐릭터 그림 업로드 (참조)
    loop 컷 1 → 4
        API->>G: 행동 문장 → 장면 태그 후보
        API->>J: 프롬프트 + 참조 이미지
        J->>CF: 생성 (Turbo 12 step)
        CF-->>J: PNG
        J-->>API: media/ 저장 · 컷 status = done
    end
    loop 3초마다
        U->>API: GET /api/storyboard
        API-->>U: 컷 상태 · 남은 시간
    end
```

## 실행

```bash
# backend  (.env: DATABASE_URL, COMFY_BASE_URL, COMFY_USER/PASSWORD, OPENAI_API_KEY)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 9010
# frontend (.env.local: VITE_API_PROXY_TARGET=http://127.0.0.1:9010)
cd frontend && npm install && npm run dev
```
