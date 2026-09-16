"""마스코트 캐릭터 — ComfyUI '연습용' 워크플로우로 실제 이미지를 뽑는다.

생성은 전부 백그라운드다(app/services/jobs.py 참고). 요청은 즉시 돌아오고 칸이
status="generating"으로 생기며, 화면이 GET /api/character를 폴링해 채워진 그림을 받는다.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services import jobs
from app.services.chat_ai import (VIEW_HINTS, VIEW_LABELS, character_prompt,
                                  pending_candidates, pending_views)
from app.services.image_gen import eta_seconds, generate_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character", tags=["character"])


def _get(db: Session) -> models.Character:
    char = db.get(models.Character, 1)
    if not char:
        raise HTTPException(404, "character row missing")
    return char


def _fill_slots(field: str, indexes: list[int], prompt: str, count: int) -> None:
    """백그라운드 작업 본체 — 이미지를 뽑아 candidates/views의 해당 칸에 채운다.

    실패하면 status를 'failed'로 남긴다. 조용히 사라지면 사장님은 계속 기다리게 된다.
    """
    images = generate_images(prompt, count)

    def write(db: Session):
        char = db.get(models.Character, 1)
        if not char:
            return
        slots = list(getattr(char, field) or [])
        for slot_pos, index in enumerate(indexes):
            if not 0 <= index < len(slots):
                continue
            image = images[slot_pos] if slot_pos < len(images) else None
            slots[index] = {
                **slots[index],
                "image": image,
                "status": "done" if image else "failed",
            }
        setattr(char, field, slots)
        db.commit()

    jobs.with_session(write)


@router.get("", response_model=schemas.CharacterOut)
def get_character(db: Session = Depends(get_db)):
    char = _get(db)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.put("", response_model=schemas.CharacterOut)
def update_character(body: schemas.CharacterUpdate, db: Session = Depends(get_db)):
    char = _get(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(char, field, value)
    db.commit()
    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/chat", response_model=schemas.CharacterOut)
def chat(body: schemas.ChatIn, db: Session = Depends(get_db)):
    """사장님이 원하는 캐릭터를 말로 설명하면 그 설명으로 후보 3장을 뽑기 시작한다."""
    char = _get(db)
    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": body.text})

    # 사장님이 쓴 문장을 그대로 외형 설명으로 쓴다 — 지어낸 기본값을 넣지 않는다.
    char.look = body.text.strip()
    char.candidates = pending_candidates(3)
    char.selected_index = -1
    char.views = []
    messages.append({
        "role": "ai", "kind": "text",
        "text": f"말씀하신 느낌으로 3장 그려볼게요. 약 {eta_seconds(3)}초 걸려요 — 이 화면 그대로 두셔도 되고, 다른 걸 하고 오셔도 됩니다.",
    })
    messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    char.messages = messages
    db.commit()

    prompt = character_prompt(char)
    jobs.submit(_fill_slots, "candidates", [0, 1, 2], prompt, 3)

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/candidates", response_model=schemas.CharacterOut)
def gen_candidates(db: Session = Depends(get_db)):
    """후보 3장을 다시 뽑는다."""
    char = _get(db)
    if not (char.look or "").strip():
        raise HTTPException(400, "어떤 캐릭터를 원하는지 먼저 말해주세요")
    char.candidates = pending_candidates(3)
    char.selected_index = -1
    char.views = []
    messages = list(char.messages or [])
    messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    char.messages = messages
    db.commit()

    prompt = character_prompt(char)
    jobs.submit(_fill_slots, "candidates", [0, 1, 2], prompt, 3)

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/candidates/{index}/reroll", response_model=schemas.CharacterOut)
def reroll_candidate(index: int, db: Session = Depends(get_db)):
    """후보 한 칸만 다시 뽑는다."""
    char = _get(db)
    cands = list(char.candidates or [])
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    cands[index] = {**cands[index], "image": None, "status": "generating"}
    char.candidates = cands
    db.commit()

    prompt = character_prompt(char, f"variation {index + 1}")
    jobs.submit(_fill_slots, "candidates", [index], prompt, 1)

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/select/{index}", response_model=schemas.CharacterOut)
def select_candidate(index: int, db: Session = Depends(get_db)):
    """후보를 고르면 4방향을 뽑기 시작한다."""
    char = _get(db)
    cands = char.candidates or []
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    if cands[index].get("status") == "generating":
        raise HTTPException(400, "아직 그려지는 중이에요. 그림이 나온 뒤에 골라주세요")
    if not cands[index].get("image"):
        raise HTTPException(400, "이 후보는 그리기에 실패했어요. 다시 뽑은 뒤에 골라주세요")

    char.selected_index = index
    char.views = pending_views()
    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": f"{index + 1}번으로 할게요"})
    messages.append({
        "role": "ai", "kind": "text",
        "text": f"{index + 1}번으로 정했어요. 4방향으로 뽑아둘게요 — 약 {eta_seconds(4)}초 걸려요.",
    })
    messages.append({"role": "ai", "kind": "views", "ref": "views"})
    char.messages = messages
    db.commit()

    prompt = character_prompt(char)
    jobs.submit(_fill_slots, "views", [0, 1, 2, 3], prompt, 4)

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/views/{index}/reroll", response_model=schemas.CharacterOut)
def reroll_view(index: int, db: Session = Depends(get_db)):
    char = _get(db)
    views = list(char.views or [])
    if not 0 <= index < len(views):
        raise HTTPException(404, "view index out of range")
    label = views[index].get("label", VIEW_LABELS[0])
    views[index] = {**views[index], "image": None, "status": "generating"}
    char.views = views
    db.commit()

    prompt = character_prompt(char, VIEW_HINTS.get(label, "front view"))
    jobs.submit(_fill_slots, "views", [index], prompt, 1)

    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/load-previous", response_model=schemas.CharacterOut)
def load_previous(db: Session = Depends(get_db)):
    """전에 확정한 캐릭터를 다시 쓴다. 확정한 게 없으면 불러올 것도 없다."""
    char = _get(db)
    if not char.confirmed:
        raise HTTPException(400, "전에 만들어 확정한 캐릭터가 없어요. 새로 만들어주세요")
    messages = list(char.messages or [])
    messages.append({"role": "ai", "kind": "text", "text": "전에 확정한 캐릭터를 그대로 쓸게요."})
    messages.append({"role": "ai", "kind": "views", "ref": "views"})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())


@router.post("/confirm", response_model=schemas.CharacterOut)
def confirm_character(db: Session = Depends(get_db)):
    char = _get(db)
    if char.selected_index < 0:
        raise HTTPException(400, "후보를 먼저 선택해주세요")
    views = char.views or []
    if any(v.get("status") == "generating" for v in views):
        raise HTTPException(400, "4방향이 아직 그려지는 중이에요")
    char.confirmed = True
    db.commit()
    db.refresh(char)
    return schemas.character_out(char, queue_depth=jobs.queue_depth())
