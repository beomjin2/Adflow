import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import ad, character, history, production, storyboard, store
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.db.seed import ensure_rows

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
os.makedirs("uploads/store", exist_ok=True)
os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/api/media", StaticFiles(directory=settings.media_dir), name="media")


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        ensure_rows(db)
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
