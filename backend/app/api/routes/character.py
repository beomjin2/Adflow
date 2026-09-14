from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.chat_ai import generate_candidates, generate_views
from app.services.image_gen import random_hue

router = APIRouter(prefix="/api/character", tags=["character"])


def _get(db: Session) -> models.Character:
    char = db.get(models.Character, 1)
    if not char:
        raise HTTPException(404, "character not seeded")
    return char


@router.get("", response_model=schemas.CharacterOut)
def get_character(db: Session = Depends(get_db)):
    return _get(db)


@router.put("", response_model=schemas.CharacterOut)
def update_character(body: schemas.CharacterUpdate, db: Session = Depends(get_db)):
    char = _get(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(char, field, value)
    db.commit()
    db.refresh(char)
    return char


@router.post("/chat", response_model=schemas.CharacterOut)
def chat(body: schemas.ChatIn, db: Session = Depends(get_db)):
    char = _get(db)
    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": body.text})

    if not char.candidates:
        char.name = char.name or "동글이"
        char.look = char.look or f"{body.text} 느낌으로 그려볼게요."
        char.candidates = generate_candidates(3)
        char.selected_index = -1
        messages.append({"role": "ai", "kind": "text", "text": "이름·외형을 채웠어요. 왼쪽에서 직접 고쳐도 돼요."})
        messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    else:
        messages.append({"role": "ai", "kind": "text", "text": "알겠어요, 반영해서 다시 뽑아볼게요."})

    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/candidates", response_model=schemas.CharacterOut)
def gen_candidates(db: Session = Depends(get_db)):
    char = _get(db)
    char.candidates = generate_candidates(3)
    char.selected_index = -1
    messages = list(char.messages or [])
    messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/candidates/{index}/reroll", response_model=schemas.CharacterOut)
def reroll_candidate(index: int, db: Session = Depends(get_db)):
    char = _get(db)
    cands = list(char.candidates or [])
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    cands[index] = {**cands[index], "hue": random_hue()}
    char.candidates = cands
    db.commit()
    db.refresh(char)
    return char


@router.post("/select/{index}", response_model=schemas.CharacterOut)
def select_candidate(index: int, db: Session = Depends(get_db)):
    char = _get(db)
    cands = char.candidates or []
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    char.selected_index = index
    char.views = generate_views()
    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": f"{index + 1}번으로 할게요"})
    messages.append({"role": "ai", "kind": "text", "text": f"{index + 1}번으로 정했어요. 4방향으로 뽑아둘게요 — 확정하면 광고에 계속 쓰여요."})
    messages.append({"role": "ai", "kind": "views", "ref": "views"})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/views/{index}/reroll", response_model=schemas.CharacterOut)
def reroll_view(index: int, db: Session = Depends(get_db)):
    char = _get(db)
    views = list(char.views or [])
    if not 0 <= index < len(views):
        raise HTTPException(404, "view index out of range")
    views[index] = {**views[index], "hue": random_hue()}
    char.views = views
    db.commit()
    db.refresh(char)
    return char


@router.post("/load-previous", response_model=schemas.CharacterOut)
def load_previous(db: Session = Depends(get_db)):
    char = _get(db)
    char.name, char.age, char.gender, char.hobby = "동글이", "3살", "남성", "빵 굽기"
    char.look = "앞치마를 두른 통통한 곰. 둥근 눈, 밀색 털, 밀가루 묻은 베이지 앞치마."
    if not char.candidates:
        char.candidates = generate_candidates(3)
    char.selected_index = 0
    char.views = generate_views()
    messages = list(char.messages or [])
    messages.append({"role": "ai", "kind": "text", "text": "지난번에 만든 캐릭터를 불러왔어요."})
    messages.append({"role": "ai", "kind": "views", "ref": "views"})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/confirm", response_model=schemas.CharacterOut)
def confirm_character(db: Session = Depends(get_db)):
    char = _get(db)
    if char.selected_index < 0:
        raise HTTPException(400, "후보를 먼저 선택해주세요")
    char.confirmed = True
    db.commit()
    db.refresh(char)
    return char
