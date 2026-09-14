import { colors, bgGradient } from '../theme.js';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

export default function MyStore({ state, actions }) {
  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Info label="업종" value={state.storeCategory} />
        <Info label="가게 주소" value={state.storeAddress} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>대표 상품 이미지</span>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {state.storeImages.map((im, i) => (
            <div key={i} style={{ width: 104, height: 78, borderRadius: 12, border: `1px solid ${colors.cardBorder}`, background: bgGradient(im.hue) }} />
          ))}
        </div>
      </div>
      <Info label="영업시간" value={state.storeHours} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>가게 소개</span>
        <span style={{ fontSize: 14, lineHeight: '21px', color: colors.textSub }}>{state.storeDesc}</span>
      </div>
      <div style={{ display: 'flex', gap: 10, paddingTop: 4 }}>
        <PrimaryButton onClick={actions.editStoreFromMy} style={{ flex: 1, height: 48, fontSize: 15 }}>수정</PrimaryButton>
        <SecondaryButton onClick={actions.goHome} style={{ flex: 1, height: 48, fontSize: 15 }}>홈으로</SecondaryButton>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div style={{ flex: '1 1 220px', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 600 }}>{value}</span>
    </div>
  );
}
