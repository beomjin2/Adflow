from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db
from app.services.chat_ai import CHARACTER_INTRO_MESSAGE, character_prompt, generate_candidates, new_pid
from app.services.image_gen import generate_image, random_hue

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

    pending = dict(char.pending or {})
    pid = new_pid()

    if not char.name:
        new_name, new_age, new_gender, new_hobby = "동글이", "3살", "남성", "빵 굽기"
        new_look = f"{body.text} 느낌으로 그려볼게요."
        diffs = [
            {"label": "이름", "from": char.name or "비어 있음", "to": new_name},
            {"label": "나이 · 성별", "from": f"{char.age or '비어 있음'} · {char.gender or '비어 있음'}", "to": f"{new_age} · {new_gender}"},
            {"label": "취미", "from": char.hobby or "비어 있음", "to": new_hobby},
            {"label": "외형", "from": char.look or "비어 있음", "to": new_look},
        ]
        pending[pid] = {
            "kind": "char_intro", "diffs": diffs,
            "payload": {"name": new_name, "age": new_age, "gender": new_gender, "hobby": new_hobby, "look": new_look},
            "status": "open",
        }
    else:
        base_look = (char.look or "").strip().rstrip(".!? ")
        new_look = f"{base_look}. {body.text}" if base_look else body.text
        diffs = [{"label": "외형", "from": char.look or "비어 있음", "to": new_look}]
        pending[pid] = {"kind": "char_look", "diffs": diffs, "payload": {"look": new_look}, "status": "open"}

    char.pending = pending
    messages.append({"role": "ai", "kind": "confirm", "pid": pid})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/confirm/{pid}", response_model=schemas.CharacterOut)
def confirm_pending(pid: str, db: Session = Depends(get_db)):
    char = _get(db)
    pending = dict(char.pending or {})
    p = pending.get(pid)
    if not p or p.get("status") != "open":
        raise HTTPException(404, "pending not open")
    pending[pid] = {**p, "status": "applied"}
    messages = list(char.messages or [])
    payload = p.get("payload", {})
    if p["kind"] == "char_intro":
        char.name = payload.get("name", char.name)
        char.age = payload.get("age", char.age)
        char.gender = payload.get("gender", char.gender)
        char.hobby = payload.get("hobby", char.hobby)
        char.look = payload.get("look", char.look)
        char.candidates = generate_candidates(3)
        char.selected_index = -1
        messages.append({"role": "ai", "kind": "text", "text": "이름·외형을 채웠습니다. 왼쪽에서 직접 수정하실 수도 있습니다."})
        messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    elif p["kind"] == "char_look":
        char.look = payload.get("look", char.look)
        messages.append({"role": "ai", "kind": "text", "text": "외형에 반영했습니다. 새로 그리시려면 '후보 생성'을 눌러 주세요."})
    char.pending = pending
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/decline/{pid}", response_model=schemas.CharacterOut)
def decline_pending(pid: str, db: Session = Depends(get_db)):
    char = _get(db)
    pending = dict(char.pending or {})
    p = pending.get(pid)
    if not p or p.get("status") != "open":
        raise HTTPException(404, "pending not open")
    pending[pid] = {**p, "status": "declined"}
    messages = list(char.messages or [])
    messages.append({"role": "ai", "kind": "text", "text": "그대로 두겠습니다. 어떻게 바꾸면 좋을지 말씀해 주세요."})
    char.pending = pending
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
    cands = char.candidates or []
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    label = cands[index].get("label", f"후보{index + 1}")
    prompt = character_prompt(char, f"variation {index + 1}")

    image = generate_image(prompt)

    db.refresh(char)
    cands = list(char.candidates or [])
    if not 0 <= index < len(cands):
        raise HTTPException(404, "candidate index out of range")
    cands[index] = {"label": label, "hue": random_hue(), "image": image}
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
    messages = list(char.messages or [])
    messages.append({"role": "me", "kind": "text", "text": f"{index + 1}번으로 할게요"})
    messages.append({"role": "ai", "kind": "text", "text": f"{index + 1}번으로 정했습니다. 확정하면 광고에 계속 사용됩니다."})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/load-previous", response_model=schemas.CharacterOut)
def load_previous(db: Session = Depends(get_db)):
    char = _get(db)
    if not char.snapshot:
        raise HTTPException(404, "이전에 확정한 캐릭터가 없어요")
    snap = char.snapshot
    char.name = snap.get("name", "")
    char.age = snap.get("age", "")
    char.gender = snap.get("gender", "")
    char.hobby = snap.get("hobby", "")
    char.look = snap.get("look", "")
    char.candidates = snap.get("candidates", [])
    char.selected_index = snap.get("selected_index", -1)
    char.confirmed = False
    messages = list(char.messages or [])
    messages.append({"role": "ai", "kind": "text", "text": "이전에 확정했던 캐릭터를 불러왔습니다."})
    messages.append({"role": "ai", "kind": "cands", "ref": "cands"})
    char.messages = messages
    db.commit()
    db.refresh(char)
    return char


@router.post("/reset", response_model=schemas.CharacterOut)
def reset_character(db: Session = Depends(get_db)):
    char = _get(db)
    char.name, char.age, char.gender, char.hobby, char.look = "", "", "", "", ""
    char.confirmed = False
    char.candidates = []
    char.selected_index = -1
    char.pending = {}
    char.messages = [{"role": "ai", "kind": "text", "text": CHARACTER_INTRO_MESSAGE}]
    db.commit()
    db.refresh(char)
    return char


@router.post("/confirm", response_model=schemas.CharacterOut)
def confirm_character(db: Session = Depends(get_db)):
    char = _get(db)
    if char.selected_index < 0:
        raise HTTPException(400, "후보를 먼저 선택해주세요")
    char.confirmed = True
    char.snapshot = {
        "name": char.name, "age": char.age, "gender": char.gender, "hobby": char.hobby, "look": char.look,
        "candidates": char.candidates, "selected_index": char.selected_index,
    }
    db.commit()
    db.refresh(char)
    return char
