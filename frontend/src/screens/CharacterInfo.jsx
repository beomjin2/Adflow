import { colors, bgGradient } from '../theme.js';
import { Label, TextInput, TextArea } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';

export default function CharacterInfo({ state, actions }) {
  const ro = state.charInfoReadOnly;
  const selected = state.charCands?.[state.charSelected];
  return (
    <div style={{ padding: 22, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
      <div style={{ flex: '1 1 280px', display: 'flex', flexDirection: 'column', gap: 9 }}>
        <Label>확정된 캐릭터</Label>
        <div style={{
          width: '100%', maxWidth: 320, aspectRatio: '1 / 1', borderRadius: 16, border: `1px solid ${colors.cardBorder}`,
          overflow: 'hidden', background: selected?.image ? undefined : bgGradient(selected?.hue ?? 0),
          backgroundImage: selected?.image ? `url(${selected.image})` : undefined,
          backgroundSize: 'cover', backgroundPosition: 'center', backgroundRepeat: 'no-repeat',
        }} />
      </div>
      <div style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <TextInput value={state.charName} onChange={e => actions.set('charName', e.target.value)} readOnly={ro} placeholder="이름" />
        <div style={{ display: 'flex', gap: 8 }}>
          <TextInput value={state.charAge} onChange={e => actions.set('charAge', e.target.value)} readOnly={ro} placeholder="나이" />
          <TextInput value={state.charGender} onChange={e => actions.set('charGender', e.target.value)} readOnly={ro} placeholder="성별" />
        </div>
        <TextInput value={state.charHobby} onChange={e => actions.set('charHobby', e.target.value)} readOnly={ro} placeholder="취미" />
        <TextArea value={state.charLook} onChange={e => actions.set('charLook', e.target.value)} readOnly={ro} placeholder="외형" />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 2 }}>
          <PrimaryButton onClick={actions.toggleCharEdit} style={{ flex: 1, height: 44, fontSize: 15 }}>
            {ro ? '수정 (수기 입력)' : '수정 완료'}
          </PrimaryButton>
          <SecondaryButton onClick={actions.goChar} style={{ flex: 1, height: 44, fontSize: 15 }}>다시 만들기</SecondaryButton>
          <SoftButton onClick={actions.goHome} style={{ flex: 1, height: 44, fontSize: 15 }}>홈으로</SoftButton>
        </div>
      </div>
    </div>
  );
}
