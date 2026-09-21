from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import ad, character, history, production, storyboard, store, trend
from app.core.config import BACKEND_ROOT, settings
from app.core.database import SessionLocal, init_db
from app.db.seed import ensure_rows
from app.services import jobs

app = FastAPI(
    title="AI 광고 만들기 API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 사장님이 올린 가게 사진과, 캐릭터 생성 결과 PNG. 둘 다 파일로 두고 URL로 넘긴다 —
# 응답 JSON에 base64로 실으면 폴링할 때마다 수 MB가 오간다(모바일에서 그대로 요금이다).
# 경로는 settings 쪽 절대경로를 쓴다. 상대경로("media")를 그대로 마운트하면 기준이
# 프로세스의 CWD가 되어, image_gen이 쓴 곳과 여기서 내려주는 곳이 갈릴 수 있다
# (systemd로 띄울 때와 셸에서 띄울 때가 다르다). 그러면 파일은 생겼는데 404가 난다.
settings.uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=BACKEND_ROOT / "uploads"), name="uploads")
app.mount("/api/media", StaticFiles(directory=settings.media_path), name="media")

# 트렌드 확인 화면의 밈 대표 이미지 — 외부 사이트 URL에 의존하지 않도록 크롤링 시점에
# 내려받아 둔 사본을 그대로 쓴다(원본이 이미지를 내리거나 핫링크를 막아도 안 깨진다).
# repo 루트의 crawling/images/를 직접 본다 — 배포 스크립트(deploy.sh)는 backend/app만
# 옮기고 crawling/은 안 건드리므로, 배포 뒤 매번 .src/crawling을 운영 디렉터리로
# 직접 옮겨줘야 이미지가 뜬다(USER_COMMANDS.md 참고). 경로 값(/api/meme-images/파일명)은
# import_memes.py가 crawling/memes_all.json을 읽어서 DB의 image 컬럼에 적어 둔다.
app.mount("/api/meme-images", StaticFiles(directory=BACKEND_ROOT.parent / "crawling" / "images"), name="meme-images")


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        ensure_rows(db)
        # 재시작 전에 돌던 생성 스레드는 죽었다. 그 칸들을 실패로 정리하지 않으면
        # 화면이 영원히 "그리는 중"으로 남는다.
        jobs.recover_interrupted(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(store.router)
app.include_router(character.router)
app.include_router(ad.router)
app.include_router(storyboard.router)
app.include_router(production.router)
app.include_router(history.router)
app.include_router(trend.router)
