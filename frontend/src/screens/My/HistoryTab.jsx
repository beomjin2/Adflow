import { colors, bgGradient } from '../../theme.js';

export default function HistoryTab({ state, actions }) {
  if (state.history.length === 0) {
    return (
      <div style={{ border: `1px dashed ${colors.inputBorder}`, borderRadius: 16, padding: 36, textAlign: 'center', fontSize: 13.5, color: colors.textFaint, lineHeight: '21px' }}>
        아직 저장한 광고가 없어요.<br />홈에서 광고를 만들어 보세요.
      </div>
    );
  }
  return (
    <>
      {state.history.map(h => (
        <div key={h.id} style={{ display: 'flex', gap: 12, alignItems: 'center', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: 12 }}>
          <div style={{ width: 56, height: 56, borderRadius: 10, flex: 'none', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, overflow: 'hidden', background: colors.cardBorder }}>
            {h.cuts.map((c, i) => <div key={i} style={{ background: bgGradient(c.hue) }} />)}
          </div>
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span style={{ fontSize: 14, fontWeight: 700 }}>{h.title}</span>
            <span style={{ fontSize: 12, color: colors.textFaint }}>{h.meta}</span>
          </div>
          <button onClick={() => actions.openHistoryItem(h)} style={{ height: 40, borderRadius: 10, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', fontSize: 14, fontWeight: 700, padding: '0 14px', cursor: 'pointer' }}>열기</button>
        </div>
      ))}
    </>
  );
}
