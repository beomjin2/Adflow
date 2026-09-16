import { colors } from '../theme.js';
import { Label, TextInput, TextArea } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import ImageSlot, { formatEta } from '../components/ImageSlot.jsx';

export default function CharacterInfo({ state, actions }) {
  const ro = state.charInfoReadOnly;
  const views = state.charViews;
  const busy = state.charGenerating;

  return (
    <div style={{ padding: 22, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
      <div style={{ flex: '1 1 280px', display: 'flex', flexDirection: 'column', gap: 9 }}>
        <Label>확정된 캐릭터 — 4방향</Label>
        {views.length === 0 ? (
          <div style={{
            border: `1px dashed ${colors.inputBorder}`, borderRadius: 14, padding: 28,
            textAlign: 'center', fontSize: 13.5, lineHeight: '21px', color: colors.textFaint
          }}>
            아직 4방향 그림이 없어요.<br />‘다시 만들기’에서 그림을 뽑고 확정해주세요.
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {views.map((v, i) => (
                <ImageSlot key={i} slot={v} size={128} eta={state.charEta} onReroll={() => actions.rerollView(i)} />
              ))}
            </div>
            {busy && state.charEta > 0 && (
              <span style={{ fontSize: 12.5, color: colors.textSub }}>그리는 중 — 약 {formatEta(state.charEta)}</span>
            )}
          </>
        )}
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
          <PrimaryButton onClick={actions.toggleCharEdit} style={{ flex: '1 1 140px', height: 48, fontSize: 15 }}>
            {ro ? '수정하기' : '수정 완료'}
          </PrimaryButton>
          <SecondaryButton onClick={actions.goChar} style={{ flex: '1 1 140px', height: 48, fontSize: 15 }}>다시 만들기</SecondaryButton>
          <SoftButton onClick={actions.goHome} style={{ flex: '1 1 120px', height: 48, fontSize: 15 }}>홈으로</SoftButton>
        </div>
      </div>
    </div>
  );
}
