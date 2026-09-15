from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    cors_origins: str = "http://localhost:5173"

    # ComfyUI 이미지 생성 서버 — 비워두면 캐릭터 이미지는 hue 그라디언트로 폴백한다.
    comfy_base_url: str = ""
    comfy_user: str = ""
    comfy_password: str = ""
    comfy_unet_name: str = "anima-aesthetic-v1.1.safetensors"
    comfy_clip_name: str = "qwen_3_06b_base.safetensors"
    comfy_vae_name: str = "qwen_image_vae.safetensors"
    comfy_timeout_seconds: int = 150

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
