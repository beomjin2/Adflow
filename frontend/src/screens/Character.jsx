import { useState } from 'react';
import { colors } from '../theme.js';
import { Label, TextInput, TextArea, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SoftButton, SecondaryButton } from '../components/ui/Button.jsx';
import ChatPanel from '../components/ChatPanel.jsx';
import { formatEta } from '../components/ImageSlot.jsx';

const EMPTY_HINT = `가게 마스코트를 만들어 드려요.
어떤 캐릭터였으면 좋겠는지 편하게 말씀해주세요.

예) 우리 가게 빵을 굽는 곰 캐릭터였으면 좋겠어요
예) 앞치마 두른 젊은 사장님 캐릭터로 해주세요`;

// 폰으로 쓰는 화면이라 고를 수 있는 건 고르게 한다. 직접 칠 일이 줄수록 끝까지 간다.
const AGE_OPTIONS = ['어린이', '청소년', '20대', '30대', '40대', '50대 이상'];
const GENDER_OPTIONS = ['남성', '여성', '중성'];

function FieldLabel({ children }) {
  return <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{children}</span>;
}

export default function Character({ state, actions }) {
  const busy = state.charGenerating;
  const hasCands = state.charCands.length > 0;
  const [confirmReset, setConfirmReset] = useState(false);

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
        <div style={{ flex: '1 1 250px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Label>캐릭터 정보 — 대화로 채워지고, 직접 고칠 수도 있어요</Label>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <FieldLabel>이름</FieldLabel>
            <TextInput value={state.charName} onChange={e => actions.set('charName', e.target.value)} placeholder="예) 구름이" />
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <FieldLabel>나이대</FieldLabel>
              <Select value={state.charAge} onChange={e => actions.set('charAge', e.target.value)} placeholder="선택">
                {AGE_OPTIONS.map(a => <option key={a} value={a}>{a}</option>)}
              </Select>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <FieldLabel>성별</FieldLabel>
              <Select value={state.charGender} onChange={e => actions.set('charGender', e.target.value)} placeholder="선택">
                {GENDER_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
              </Select>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <FieldLabel>취미</FieldLabel>
            <TextInput value={state.charHobby} onChange={e => actions.set('charHobby', e.target.value)} placeholder="예) 빵 굽기" />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
            <FieldLabel>외형 — 그림은 이 설명대로 그려집니다</FieldLabel>
            <TextArea value={state.charLook} onChange={e => actions.set('charLook', e.target.value)}
              placeholder="예) 하얀 앞치마를 두른 통통한 곰" style={{ flex: 1, minHeight: 110 }} />
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
            <SecondaryButton onClick={actions.loadChar} disabled={busy} style={{ flex: 1, height: 46, fontSize: 15 }}>
              전에 만든 캐릭터
            </SecondaryButton>
            <SoftButton onClick={actions.genCandidates} disabled={busy} style={{ flex: 1, height: 46, fontSize: 15, background: colors.primarySoft, color: colors.primarySoftText }}>
              {busy ? '그리는 중…' : hasCands ? '다시 뽑기' : '그림 뽑기'}
            </SoftButton>
          </div>

          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint }}>
            그림 한 장에 1분쯤 걸려요. 창을 닫아도 서버에서 계속 그립니다.
          </span>

          <div style={{ flex: 1 }} />
          <PrimaryButton onClick={actions.confirmChar} disabled={state.charSelected < 0 || busy}>
            {state.charSelected < 0 ? '그림을 먼저 골라주세요' : '이 캐릭터로 확정'}
          </PrimaryButton>
        </div>

        <div style={{ flex: '2 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <Label>AI와 대화로 캐릭터 만들기</Label>
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
            placeholder="어떤 캐릭터가 좋을지 적어주세요"
            input={state.charInput}
            onInputChange={(v) => actions.set('charInput', v)}
            onSend={actions.sendChar}
            cands={state.charCands}
            charSelected={state.charSelected}
            onSelectCand={actions.selectCand}
            onRerollCand={actions.rerollCand}
            views={state.charViews}
            onRerollView={actions.rerollView}
            eta={state.charEta}
          />
        </div>
      </div>
    </div>
  );
}
