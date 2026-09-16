import { colors } from '../theme.js';
import { Label, TextInput, TextArea } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import ImageSlot from '../components/ImageSlot.jsx';

/** 어느 칸을 여러 줄로 보여줄지. Character.jsx의 SHAPE와 같은 기준이다. */
const MULTILINE = new Set(['look', 'outfit', 'desc', 'abilities']);
const STATE_KEY = {
  look: 'charLook', outfit: 'charOutfit', desc: 'charDesc', abilities: 'charAbilities',
  age: 'charAge', gender: 'charGender', name: 'charName', keywords: 'charKeywords',
};

export default function CharacterInfo({ state, actions }) {
  const ro = state.charInfoReadOnly;
  const rows = state.charSheet || [];
  // 확정된 캐릭터의 그림은 사장님이 고른 후보 그 장이다.
  const picked = state.charSelected >= 0 ? state.charCands[state.charSelected] : null;

  return (
    <div style={{ padding: 22, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
      <div style={{ flex: '1 1 260px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 9 }}>
        <Label>확정된 캐릭터</Label>
        {picked && picked.image ? (
          <ImageSlot slot={picked} size={240} />
        ) : (
          <div style={{
            border: `1px dashed ${colors.inputBorder}`, borderRadius: 14, padding: 28,
            textAlign: 'center', fontSize: 13.5, lineHeight: '21px', color: colors.textFaint
          }}>
            아직 고른 그림이 없어요.<br />‘다시 만들기’에서 그림을 뽑고 골라주세요.
          </div>
        )}
        {state.charName && (
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-.01em' }}>{state.charName}</span>
        )}
      </div>

      <div style={{ flex: '1 1 320px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Label>캐릭터 시트</Label>

        {rows.map((row) => {
          const key = STATE_KEY[row.field];
          const Input = MULTILINE.has(row.field) ? TextArea : TextInput;
          return (
            <div key={row.field} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{row.label}</span>
              <Input
                value={state[key] ?? ''}
                onChange={(e) => actions.set(key, e.target.value)}
                readOnly={ro}
                aria-label={row.label}
                style={MULTILINE.has(row.field) ? { minHeight: 56 } : undefined}
              />
            </div>
          );
        })}

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
