import { colors, bgGradient } from '../theme.js';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

export default function Result({ state, actions }) {
  const resultHeadline = state.trendApplied ? '눈이 번쩍! 소금빵 갓 나왔습니다' : '오늘 아침 갓 구운 소금빵';
  const resultBody = `${state.storeCategory} · ${state.storeAddress || '연남동'} · ${state.storeHours || '11:00 – 22:00'}\n새벽에 반죽해 오븐에서 바로 꺼냈어요. ${state.charName || '마스코트'}가 기다릴게요.`;
  const resultTags = state.trendApplied ? `#${state.trendPick.replace(/ /g, '')} #소금빵 #연남동빵집` : '#소금빵 #연남동빵집 #갓구운빵';

  return (
    <div style={{ padding: 22, display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      <div style={{ flex: '1 1 340px', minWidth: 0, border: `1px solid ${colors.cardBorder}`, borderRadius: 18, overflow: 'hidden', background: '#fff' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, background: colors.cardBorder }}>
          {state.comicCuts.map(c => (
            <div key={c.n} style={{ position: 'relative', aspectRatio: '1/1', background: bgGradient(c.hue), display: 'flex', alignItems: 'flex-end', padding: 10 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.primarySoftText, background: 'rgba(255,255,255,.85)', borderRadius: 6, padding: '3px 8px' }}>{c.n}컷 · {c.short}</span>
              <button onClick={() => actions.rerollCut(c.n)} style={{ position: 'absolute', top: 8, right: 8, width: 26, height: 26, borderRadius: 8, border: 0, background: 'rgba(255,255,255,.94)', fontSize: 13, cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,.12)' }}>↻</button>
            </div>
          ))}
        </div>
      </div>
      <div style={{ flex: '1 1 280px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ background: colors.bg, borderRadius: 16, padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint, letterSpacing: .4 }}>광고 문구</span>
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -.3, lineHeight: '25px' }}>{resultHeadline}</span>
          <span style={{ fontSize: 13.5, lineHeight: '21px', color: colors.textSub, whiteSpace: 'pre-line' }}>{resultBody}</span>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: colors.primarySoftText }}>{resultTags}</span>
        </div>
        <SecondaryButton onClick={actions.backToSb} style={{ height: 48, fontSize: 15 }}>대화로 돌아가 수정</SecondaryButton>
        <PrimaryButton onClick={actions.confirmResult}>확정</PrimaryButton>
      </div>
    </div>
  );
}
