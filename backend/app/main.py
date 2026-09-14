from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ad, character, history, production, storyboard, store, trend
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.db.seed import seed_if_empty

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


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(store.router)
app.include_router(character.router)
app.include_router(ad.router)
app.include_router(trend.router)
app.include_router(storyboard.router)
app.include_router(production.router)
app.include_router(history.router)
