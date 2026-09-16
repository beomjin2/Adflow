import { colors } from '../theme.js';
import { Label, TextInput, TextArea, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SoftButton, SecondaryButton } from '../components/ui/Button.jsx';
import ChatPanel from '../components/ChatPanel.jsx';

const AGE_OPTIONS = Array.from({ length: 10 }, (_, i) => `${i + 1}살`);
const GENDER_OPTIONS = ['남성', '여성', '중성'];

function FieldLabel({ children }) {
  return <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{children}</span>;
}

export default function Character({ state, actions }) {
  return (
    <div style={{ padding: '18px 20px 20px', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch' }}>
      <div style={{ flex: '1 1 250px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Label>캐릭터 정보 (대화로 채워지며, 직접 수정하실 수도 있습니다)</Label>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <FieldLabel>이름</FieldLabel>
          <TextInput value={state.charName} onChange={e => actions.set('charName', e.target.value)} placeholder="이름" />
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <FieldLabel>나이</FieldLabel>
            <Select value={state.charAge} onChange={e => actions.set('charAge', e.target.value)}>
              <option value="">선택</option>
              {AGE_OPTIONS.map(a => <option key={a}>{a}</option>)}
            </Select>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <FieldLabel>성별</FieldLabel>
            <Select value={state.charGender} onChange={e => actions.set('charGender', e.target.value)}>
              <option value="">선택</option>
              {GENDER_OPTIONS.map(g => <option key={g}>{g}</option>)}
            </Select>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <FieldLabel>취미</FieldLabel>
          <TextInput value={state.charHobby} onChange={e => actions.set('charHobby', e.target.value)} placeholder="취미" />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <FieldLabel>외형</FieldLabel>
          <TextArea value={state.charLook} onChange={e => actions.set('charLook', e.target.value)} placeholder="외형" style={{ minHeight: 140 }} />
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
          <SecondaryButton onClick={actions.loadChar} style={{ flex: 1, height: 40, fontSize: 14 }}>불러오기</SecondaryButton>
          <SoftButton onClick={actions.genCandidates} style={{ flex: 1, height: 40, fontSize: 14, background: colors.primarySoft, color: colors.primarySoftText }}>후보 생성</SoftButton>
        </div>
        <div style={{ flex: 1 }} />
        <PrimaryButton onClick={actions.confirmChar} disabled={state.charSelected < 0}>캐릭터 확정</PrimaryButton>
      </div>

      <div style={{ flex: '2 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <Label>AI와 대화로 캐릭터 만들기</Label>
          <button onClick={actions.resetChar} style={{
            flex: 'none', border: 0, background: 'transparent', color: colors.textFaint,
            fontSize: 12, fontWeight: 700, cursor: 'pointer', textDecoration: 'underline', padding: 0,
          }}>초기화</button>
        </div>
        <ChatPanel
          messages={state.charMsgs}
          thinking={state.charThinking}
          input={state.charInput}
          onInputChange={(v) => actions.set('charInput', v)}
          onSend={actions.sendChar}
          cands={state.charCands}
          charSelected={state.charSelected}
          onSelectCand={actions.selectCand}
          onRerollCand={actions.rerollCand}
          pending={state.charPending}
          onConfirm={actions.confirmCharPending}
          onDecline={actions.declineCharPending}
        />
      </div>
    </div>
  );
}
