from pydantic_settings import BaseSettings

# 가게 대표 상품 이미지 최대 개수 — models.py(Store.max_images)와 store.py 라우트가 같이 참조한다.
STORE_MAX_IMAGES = 5


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    cors_origins: str = "http://localhost:5173"

    # ComfyUI 이미지 생성 서버 — 비워두면 캐릭터 이미지는 hue 그라디언트로 폴백한다.
    comfy_base_url: str = ""
    comfy_user: str = ""
    comfy_password: str = ""
    # app/services/workflows/ 밑의 파일명 (또는 절대경로). ComfyUI에서 Export(API format)한
    # 그래프를 그대로 이 파일에 덮어쓰면 워크플로우를 바꿀 수 있다 (image_gen.py가 positive/negative
    # 연결을 따라가 프롬프트를 자동으로 채워 넣는다).
    comfy_workflow_file: str = "character_default.json"
    comfy_timeout_seconds: int = 150

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
