# Adflow — 마스코트 네컷 광고 만들기

빵집 사장님이 **가게 → 캐릭터 → 광고 → 스토리 → 네컷 그림**을 순서대로 채우면
밈 템플릿을 입힌 4컷 만화 광고가 나온다.

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

## 4. 밈 추천 (트렌드 확인 화면)

트렌드 확인 화면은 크롤링해 둔 밈을 훑어보는 화면이지만, 활용 상황(카테고리) 하나를 고르면
그 안에서 GPT가 밈 하나를 대신 골라주는 기능도 있다.

```mermaid
flowchart LR
    U[사장님<br/>활용 상황 선택 + 오늘 알릴 내용선택] -->|POST| API["/api/trend/recommend"]
    API --> Q["같은 situation 밈만<br/>후보로 (memes 테이블)"]
    API --> CH[확정된 캐릭터 정보<br/>있으면]
    Q --> G[GPT]
    CH --> G
    G -->|"밈 하나 + 고른 이유"| API
    API --> R[결과 팝업]
    R --> A["이 밈으로 광고 만들기"]
    R --> L["리스트에서 그 밈만<br/>선택해두고 더 보기"]
```

- 후보는 크롤링 밈(`memes` 테이블) 중 고른 활용 상황(`situation`)과 같은 것만 넘긴다.
- 캐릭터가 확정돼 있으면 이름·외형·아웃핏·능력·키워드·설명을 같이 넘겨서, 그 캐릭터와 어울리는 밈을 고르게 한다.
- 결과는 밈 하나와 "왜 골랐는지" 한국어 1~2문장. 바로 광고를 만들 수도 있고, 팝업의 밈을 눌러 트렌드 리스트에서 그 밈만 선택해둔 채로 유래·활용예시를 더 살펴볼 수도 있다.
- 밈 데이터 자체(`memes` 테이블)는 앱과 분리된 오프라인 파이프라인(`crawling/`)이 만든다 — 크롤링 → 문장 임베딩으로 상황 분류

## 배포

CI/CD 파이프라인은 없다. `main`에 PR을 머지한 뒤 VM에 직접 들어가 스크립트 하나를 돌리고 서비스를 재시작한다.

```bash
브라우저에서 JupyterLab 접속 (http://35.237.89.149/) → 터미널 열기
bash /home/sprint05/part4_3team/deploy.sh          # main pull → 프론트 빌드 → backend/app 교체
sudo systemctl restart adflow-backend adflow-frontend
systemctl is-active adflow-backend adflow-frontend  # 둘 다 active여야 한다
```

- `deploy.sh`는 `backend/.env` · `app.db` · `uploads/` · `media/`는 절대 안 건드린다 — 지우면 복구가 안 되는 것들이라 배포 자동화 대상에서 일부러 뺐다.


## 참고 자료

- [DB 스키마 (Adflow ERD)](https://claude.ai/code/artifact/f5766efd-aa09-4bfc-881f-29c77c536ee1)
- [Adflow 아키텍처](https://claude.ai/artifact/7Zb39jAHm9HfeGXuTXXUd2)
