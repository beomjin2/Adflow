import { useState } from 'react';
import { colors, TAP } from '../theme.js';
import { Label, TextInput, TextArea } from '../components/ui/Field.jsx';
import { PrimaryButton, SoftButton } from '../components/ui/Button.jsx';
import ChatPanel from '../components/ChatPanel.jsx';
import { formatEta } from '../components/ImageSlot.jsx';

const EMPTY_HINT = `가게 마스코트를 만들어 드려요.
아래 시트를 대화로 하나씩 채워갑니다 — 외형부터 시작해요.

어떻게 생긴 캐릭터였으면 좋겠는지 편하게 말씀해주세요.`;

/** 시트 순서 = 대화 가이드 순서. 백엔드(services/character_sheet.py)의 ORDER와 같다.
 *  라벨은 백엔드가 준 걸 쓰고, 여기서는 칸 모양(한 줄/여러 줄)과 도움말만 정한다. */
const SHAPE = {
  look: { multiline: true, help: '그림은 이 칸으로 그려져요' },
  outfit: { multiline: true, help: '그림은 이 칸으로 그려져요' },
  desc: { multiline: true, help: '' },
  abilities: { multiline: true, help: '' },
  age: { multiline: false, help: '그림은 이 칸으로 그려져요' },
  gender: { multiline: false, help: '' },
  name: { multiline: false, help: '' },
  keywords: { multiline: false, help: '대화가 끝나면 자동으로 채워져요' },
};

/** 시트 값 ↔ 상태 키. mapCharacter가 만든 이름과 같아야 한다. */
const STATE_KEY = {
  look: 'charLook', outfit: 'charOutfit', desc: 'charDesc', abilities: 'charAbilities',
  age: 'charAge', gender: 'charGender', name: 'charName', keywords: 'charKeywords',
};

/** 접힌 칸 — 라벨과 값을 한 줄로. 누르면 펼쳐져 고칠 수 있다.
 *
 *  칸이 8개인데 전부 입력창으로 펼쳐두면 시트만 세로로 900px 가까이 된다.
 *  옆의 대화창보다 훨씬 길어져 둘의 비율이 무너진다. 사장님이 지금 볼 것은
 *  **묻고 있는 칸 하나**이고, 나머지는 "뭐라고 적었더라"를 확인하는 용도다. */
function CompactRow({ row, value, help, onOpen }) {
  const filled = !!String(value).trim();
  return (
    <button
      onClick={onOpen}
      title={filled ? String(value) : '아직 비어 있어요 — 눌러서 적을 수 있어요'}
      style={{
        display: 'flex', alignItems: 'baseline', gap: 8, width: '100%',
        padding: '7px 9px', borderRadius: 9, border: 0, cursor: 'pointer',
        background: 'transparent', textAlign: 'left', font: 'inherit',
      }}
    >
      <span style={{
        flex: 'none', width: 62, fontSize: 12, fontWeight: 700,
        color: filled ? colors.textSub : colors.textFaint,
      }}>{row.label}</span>
      <span style={{
        flex: 1, minWidth: 0, fontSize: 13.5, lineHeight: '20px',
        color: filled ? colors.text : colors.textFaint,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {filled ? value : (help || '비어 있음')}
      </span>
    </button>
  );
}

function Row({ row, state, actions, asking, open, onToggle }) {
  const shape = SHAPE[row.field] || { multiline: false, help: '' };
  const key = STATE_KEY[row.field];
  const value = state[key] ?? '';
  const Input = shape.multiline ? TextArea : TextInput;

  // 묻고 있는 칸은 항상 펼친다. 나머지는 사장님이 누를 때만.
  if (!asking && !open) {
    return <CompactRow row={row} value={value} help={shape.help} onOpen={onToggle} />;
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 5,
      padding: '9px 10px', borderRadius: 11,
      background: asking ? colors.onboardBg : colors.softBg,
      boxShadow: asking ? `inset 0 0 0 1.5px ${colors.onboardBorder}` : 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{row.label}</span>
        {asking && (
          <span style={{
            fontSize: 11, fontWeight: 700, color: colors.primarySoftText,
            background: colors.primarySoft, borderRadius: 999, padding: '2px 7px',
          }}>지금 묻는 칸</span>
        )}
        {shape.help && (
          <span style={{ fontSize: 11, color: colors.textFaint, marginLeft: 'auto' }}>{shape.help}</span>
        )}
        {!asking && (
          <button onClick={onToggle} style={{
            marginLeft: shape.help ? 8 : 'auto', border: 0, background: 'transparent',
            color: colors.textFaint, fontSize: 11.5, fontWeight: 700,
            cursor: 'pointer', padding: '2px 4px',
          }}>접기</button>
        )}
      </div>

      <Input
        value={value}
        onChange={(e) => actions.set(key, e.target.value)}
        onBlur={actions.saveCharSheet}
        aria-label={row.label}
        style={shape.multiline ? { minHeight: 56 } : undefined}
      />

      {!asking && (
        <button onClick={() => actions.focusCharField(row.field)} style={{
          alignSelf: 'flex-start', border: 0, background: 'transparent',
          color: colors.textFaint, fontSize: 12, fontWeight: 700,
          textDecoration: 'underline', cursor: 'pointer', padding: '2px 2px',
        }}>대화로 고치기</button>
      )}
    </div>
  );
}

export default function Character({ state, actions }) {
  const busy = state.charGenerating;
  const [confirmReset, setConfirmReset] = useState(false);
  // 손으로 펼친 칸 하나. 지금 묻는 칸은 이것과 별개로 언제나 펼쳐져 있다.
  const [openField, setOpenField] = useState('');

  const rows = state.charSheet || [];
  const missing = state.charMissing || [];
  const filledCount = rows.length - missing.length;
  const done = state.charSheetDone;

  return (
    <div style={{ padding: '18px 20px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {busy && (
        <div style={{
          background: colors.onboardBg, border: `1px solid ${colors.onboardBorder}`, borderRadius: 14,
          padding: '13px 16px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap'
        }}>
          <span style={{
            width: 18, height: 18, borderRadius: '50%', flex: 'none',
            border: `2.5px solid ${colors.cardBorder}`, borderTopColor: colors.primary,
            animation: 'spin .8s linear infinite'
          }} />
          <span style={{ fontSize: 14.5, fontWeight: 700 }}>그림을 그리고 있어요</span>
          <span style={{ fontSize: 13.5, color: colors.textSub, lineHeight: '20px' }}>
            {state.charEta > 0 ? `약 ${formatEta(state.charEta)}. ` : ''}
            다른 일을 보셔도 돼요 — 다 그리면 아래에 자동으로 나타나요.
          </span>
          {state.charQueue > 1 && (
            <span style={{ fontSize: 12.5, fontWeight: 700, color: colors.textFaint }}>
              대기 {state.charQueue}건
            </span>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch' }}>
        {/* ---------------- 캐릭터 시트 ---------------- */}
        <div style={{ flex: '1 1 280px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <Label>캐릭터 시트</Label>
            <span style={{
              fontSize: 12, fontWeight: 700, marginLeft: 'auto',
              color: done ? colors.primary : colors.textFaint,
            }}>
              {rows.length ? `${filledCount} / ${rows.length}칸` : ''}
            </span>
          </div>

          {/* 진행 막대 — 몇 칸 남았는지가 폰에서 한눈에 보여야 계속 답하게 된다. */}
          {rows.length > 0 && (
            <div style={{ height: 5, borderRadius: 3, background: colors.softBg, overflow: 'hidden' }}>
              <div style={{
                width: `${(filledCount / rows.length) * 100}%`, height: '100%',
                background: done ? colors.primary : colors.primarySoftText,
                transition: 'width .3s ease',
              }} />
            </div>
          )}

          {/* 접힌 칸은 한 줄, 펼친 칸만 입력창. 한 번에 하나만 펼쳐 시트 높이가
              대화창을 넘지 않게 한다. 그래도 넘치면 시트 안에서만 스크롤한다. */}
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 4,
            maxHeight: 380, overflowY: 'auto',
          }}>
            {rows.map((row) => (
              <Row
                key={row.field} row={row} state={state} actions={actions}
                asking={state.charEditing === row.field}
                open={openField === row.field}
                onToggle={() => setOpenField(openField === row.field ? '' : row.field)}
              />
            ))}
          </div>

          <div style={{ flex: 1, minHeight: 4 }} />

          {/* 시트가 다 차기 전에는 생성이 잠겨 있다. 무엇이 남았는지 버튼 밑에 적는다 —
              눌리지 않는 버튼만 두면 사장님은 고장으로 읽는다. */}
          <SoftButton
            onClick={actions.genCandidates}
            disabled={busy || !done}
            style={{
              height: 52, fontSize: 16,
              background: done ? colors.primarySoft : colors.softBg,
              color: done ? colors.primarySoftText : colors.textFaint,
              cursor: done && !busy ? 'pointer' : 'not-allowed',
            }}
          >
            {busy ? '그리는 중…' : state.charCands.length ? '다시 뽑기' : '그림 뽑기'}
          </SoftButton>

          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint }}>
            {done
              ? '시트가 다 찼어요. 한 장에 1분쯤 걸리고, 창을 닫아도 서버에서 계속 그립니다.'
              : `시트를 다 채우면 그림을 뽑을 수 있어요. 남은 칸: ${missing.join(', ') || '—'}`}
          </span>

          <PrimaryButton onClick={actions.confirmChar} disabled={state.charSelected < 0 || busy}>
            {state.charSelected < 0 ? '그림을 먼저 골라주세요' : '이 캐릭터로 확정'}
          </PrimaryButton>
        </div>

        {/* ---------------- 대화 ---------------- */}
        <div style={{ flex: '2 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <Label>대화로 시트 채우기</Label>
            {/* 되돌릴 수 없으니 한 번 더 묻는다 — 대화도 그림도 전부 사라진다. */}
            {confirmReset ? (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', flex: 'none' }}>
                <span style={{ fontSize: 12, color: colors.textSub }}>전부 지울까요?</span>
                <button onClick={() => { setConfirmReset(false); actions.resetChar(); }} style={{
                  height: 36, padding: '0 11px', borderRadius: 8, border: 0,
                  background: colors.warnAccent, color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer',
                }}>네</button>
                <button onClick={() => setConfirmReset(false)} style={{
                  height: 36, padding: '0 11px', borderRadius: 8, border: 0,
                  background: colors.softBg, color: colors.textSub, fontSize: 13, fontWeight: 700, cursor: 'pointer',
                }}>아니오</button>
              </div>
            ) : (
              <button onClick={() => setConfirmReset(true)} disabled={busy} style={{
                flex: 'none', border: 0, background: 'transparent',
                color: busy ? colors.cardBorder : colors.textFaint,
                fontSize: 12.5, fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer',
                textDecoration: 'underline', padding: '6px 2px',
              }}>처음부터 다시</button>
            )}
          </div>

          <ChatPanel
            messages={state.charMsgs}
            thinking={state.charThinking}
            emptyHint={EMPTY_HINT}
            placeholder={state.charEditing ? '여기에 답을 적어주세요' : '캐릭터에 대해 적어주세요'}
            input={state.charInput}
            onInputChange={(v) => actions.set('charInput', v)}
            onSend={actions.sendChar}
            cands={state.charCands}
            charSelected={state.charSelected}
            onSelectCand={actions.selectCand}
            onRerollCand={actions.rerollCand}
            pending={state.charPending}
            onConfirm={actions.acceptCharSuggestion}
            onDecline={actions.declineCharSuggestion}
            eta={state.charEta}
          />

          <button onClick={actions.loadChar} disabled={busy} style={{
            alignSelf: 'center', border: 0, background: 'transparent',
            color: busy ? colors.cardBorder : colors.textFaint,
            fontSize: 13, fontWeight: 700, height: TAP,
            textDecoration: 'underline', cursor: busy ? 'not-allowed' : 'pointer',
          }}>전에 만든 캐릭터 불러오기</button>
        </div>
      </div>
    </div>
  );
}
