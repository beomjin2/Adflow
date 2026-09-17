from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import ad, character, history, meme, production, storyboard, store
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
app.include_router(meme.router)
app.include_router(production.router)
app.include_router(history.router)
