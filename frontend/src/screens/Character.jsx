import { colors } from '../theme.js';
import { Label, TextInput, TextArea } from '../components/ui/Field.jsx';
import { PrimaryButton, SoftButton, SecondaryButton } from '../components/ui/Button.jsx';
import ChatPanel from '../components/ChatPanel.jsx';

export default function Character({ state, actions }) {
  return (
    <div style={{ padding: '18px 20px 20px', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch' }}>
      <div style={{ flex: '1 1 250px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Label>캐릭터 정보 — 대화로 채워지고, 직접 고칠 수도 있어요</Label>
        <TextInput value={state.charName} onChange={e => actions.set('charName', e.target.value)} placeholder="이름" />
        <div style={{ display: 'flex', gap: 8 }}>
          <TextInput value={state.charAge} onChange={e => actions.set('charAge', e.target.value)} placeholder="나이" />
          <TextInput value={state.charGender} onChange={e => actions.set('charGender', e.target.value)} placeholder="성별" />
        </div>
        <TextInput value={state.charHobby} onChange={e => actions.set('charHobby', e.target.value)} placeholder="취미" />
        <TextArea value={state.charLook} onChange={e => actions.set('charLook', e.target.value)} placeholder="외형" style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
          <SecondaryButton onClick={actions.loadChar} style={{ flex: 1, height: 40, fontSize: 14 }}>불러오기</SecondaryButton>
          <SoftButton onClick={actions.genCandidates} style={{ flex: 1, height: 40, fontSize: 14, background: colors.primarySoft, color: colors.primarySoftText }}>후보 생성</SoftButton>
        </div>
        <div style={{ flex: 1 }} />
        <PrimaryButton onClick={actions.confirmChar} disabled={state.charSelected < 0}>캐릭터 확정</PrimaryButton>
      </div>

      <div style={{ flex: '2 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Label>AI와 대화로 캐릭터 만들기</Label>
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
          views={state.charViews}
          onRerollView={actions.rerollView}
        />
      </div>
    </div>
  );
}
