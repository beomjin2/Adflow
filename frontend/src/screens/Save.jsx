import { colors, bgGradient } from '../theme.js';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

export default function Save({ state, actions }) {
  const resultHeadline = state.trendApplied ? '눈이 번쩍! 소금빵 갓 나왔습니다' : '오늘 아침 갓 구운 소금빵';
  const resultTags = state.trendApplied ? `#${state.trendPick.replace(/ /g, '')} #소금빵 #연남동빵집` : '#소금빵 #연남동빵집 #갓구운빵';

  return (
    <div style={{ padding: '26px 22px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
      <div style={{ width: 300, maxWidth: '100%', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, background: colors.cardBorder }}>
          {state.comicCuts.map(c => (
            <div key={c.n} style={{ aspectRatio: '1/1', background: bgGradient(c.hue) }} />
          ))}
        </div>
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 5, background: '#fff' }}>
          <span style={{ fontSize: 14, fontWeight: 700 }}>{resultHeadline}</span>
          <span style={{ fontSize: 12, color: colors.textSub, lineHeight: '18px' }}>{resultTags}</span>
        </div>
      </div>
      <span style={{ fontSize: 13.5, color: colors.textSub, textAlign: 'center', maxWidth: 420, lineHeight: '20px' }}>
        이미지 4컷과 광고 문구가 함께 저장돼요. 인스타에 올릴 땐 문구를 그대로 붙여 넣으면 됩니다.
      </span>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', width: 340, maxWidth: '100%' }}>
        <PrimaryButton onClick={actions.download} style={{ flex: 1 }}>다운로드</PrimaryButton>
        <SecondaryButton onClick={actions.goHome} style={{ flex: 1 }}>홈으로</SecondaryButton>
      </div>
    </div>
  );
}
