import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

export default function MyStore({ state, actions }) {
  // 입력 화면에서 '없으면 그냥 두세요'라고 안내한 칸이라, 비어 있으면 쉬는 날이 없다는 뜻이다.
  const closedDaysText = state.storeClosedDays?.length
    ? state.storeClosedDays.join(', ') + ' 휴무'
    : '쉬는 날 없음';
  // 영업시간은 둘 다 있을 때만 만든다. 한쪽만 있는 걸 "09:00 – "처럼 보여주면 저장된 줄 안다.
  const hoursText = state.storeOpenTime && state.storeCloseTime
    ? `${state.storeOpenTime} – ${state.storeCloseTime}`
    : '';

  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Info label="업종" value={state.storeCategory} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={labelStyle}>대표 상품 사진</span>
        {state.storeImages.length === 0 ? (
          <span style={{ fontSize: 13.5, color: colors.textFaint }}>올린 사진이 없어요</span>
        ) : (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {state.storeImages.map((im, i) => (
              <div key={i} style={{
                width: 108, height: 82, borderRadius: 12, border: `1px solid ${colors.cardBorder}`,
                overflow: 'hidden', background: colors.bg, flex: 'none',
              }}>
                {im.image && (
                  <img src={im.image} alt={im.label || '가게 사진'} loading="lazy"
                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Info label="가게 주소" value={state.storeAddress} />
        <Info label="영업시간" value={hoursText} />
        <Info label="쉬는 날" value={closedDaysText} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={labelStyle}>가게 소개</span>
        <span style={{ fontSize: 15, lineHeight: '23px', color: state.storeDesc ? colors.textSub : colors.textFaint }}>
          {state.storeDesc || '아직 안 적으셨어요'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', paddingTop: 4 }}>
        <PrimaryButton onClick={actions.editStoreFromMy} style={{ flex: '1 1 150px', height: 52, fontSize: 16 }}>수정</PrimaryButton>
        <SecondaryButton onClick={actions.goHome} style={{ flex: '1 1 150px', height: 52, fontSize: 16 }}>홈으로</SecondaryButton>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div style={{ flex: '1 1 220px', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={labelStyle}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 600, color: value ? colors.text : colors.textFaint }}>
        {value || '아직 안 적으셨어요'}
      </span>
    </div>
  );
}

const labelStyle = { fontSize: 13, fontWeight: 700, color: colors.textFaint };
