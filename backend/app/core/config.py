from pathlib import Path

from pydantic_settings import BaseSettings

# backend/ 디렉터리. media_dir 같은 상대경로의 기준점이다 — 프로세스의 CWD에 기대면
# systemd로 띄웠을 때와 셸에서 띄웠을 때 그림이 서로 다른 곳에 쌓이고,
# 쓰는 쪽과 내려주는 쪽이 갈라지면 파일은 생겼는데 404가 난다.
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    cors_origins: str = "http://localhost:5173"

    # ComfyUI 이미지 생성 서버. 비어 있으면 캐릭터 이미지는 만들어지지 않고
    # 해당 칸이 status="failed"로 남는다 — 가짜 그림으로 대신 채우지 않는다.
    comfy_base_url: str = ""
    comfy_user: str = ""
    comfy_password: str = ""
    # app/services/workflows/ 밑의 파일명 (또는 절대경로). ComfyUI에서 Export(API format)한
    # 그래프를 그대로 이 파일에 덮어쓰면 워크플로우를 바꿀 수 있다 (image_gen.py가 positive/negative
    # 연결을 따라가 프롬프트를 자동으로 채워 넣는다).
    comfy_workflow_file: str = "character_practice.json"
    comfy_timeout_seconds: int = 150

    # 생성된 캐릭터 PNG를 저장할 폴더. /api/media/<파일명>으로 서빙된다.
    media_dir: str = "media"

    # 키 하나를 두 군데서 쓴다 — 캐릭터 시트 대화(sheet_llm)와 Danbooru 태그
    # 조립(danbooru_tags). 둘 다 키가 없으면 각자 규칙 기반으로 폴백하므로
    # 비워둬도 서비스는 그대로 돈다. 키는 .env에만 두고 저장소에 넣지 않는다.
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # sheet_llm이 쓴다. danbooru_tags는 openai SDK를 쓰므로 base_url을 보지 않는다.
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: int = 20

    # deepghs/site_tags(HF, CC-BY-4.0)의 danbooru.donmai.us/tags.parquet 미러 경로.
    # backend/ 기준 상대경로(또는 절대경로) — GPT가 뽑은 태그 후보의 실존·게시물수를 검증한다.
    # 저장소에 없다(gitignore). 없으면 태그 검증을 건너뛰고 화이트리스트로 폴백한다.
    danbooru_tags_path: str = "data/danbooru_tags/danbooru.donmai.us/tags.parquet"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uploads_path(self) -> Path:
        """사장님이 올린 사진을 두는 절대경로. 없으면 만든다.

        media_path와 같은 이유로 절대경로다 — 쓰는 쪽(store 라우터)과 내려주는 쪽
        (main의 마운트)이 CWD에 따라 갈리면 업로드는 됐는데 404가 난다.
        """
        path = BACKEND_ROOT / "uploads" / "store"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def media_path(self) -> Path:
        """미디어 디렉터리의 절대경로. 없으면 만든다.

        쓰는 쪽(image_gen)과 내려주는 쪽(main의 마운트)이 반드시 이걸 같이 써야 한다.
        """
        path = Path(self.media_dir).expanduser()
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    class Config:
        env_file = ".env"


settings = Settings()
