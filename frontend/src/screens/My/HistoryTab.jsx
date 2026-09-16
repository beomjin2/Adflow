import { colors } from '../../theme.js';

export default function HistoryTab({ state, actions }) {
  if (state.history.length === 0) {
    return (
      <div style={{ border: `1px dashed ${colors.inputBorder}`, borderRadius: 16, padding: 36, textAlign: 'center', fontSize: 14, color: colors.textFaint, lineHeight: '22px' }}>
        아직 보관한 광고가 없어요.<br />홈에서 광고를 만들고 ‘보관함에 저장’을 눌러보세요.
      </div>
    );
  }
  return (
    <>
      {state.history.map(h => (
        <div key={h.id} style={{ display: 'flex', gap: 12, alignItems: 'center', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: 12, flexWrap: 'wrap' }}>
          {/* 저장한 건 문구다. 없는 이미지를 색깔 타일로 흉내 내지 않고 첫 컷 문장을 보여준다. */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>{h.title}</span>
            <span style={{ fontSize: 13, color: colors.textFaint }}>{h.meta}</span>
            {h.cuts?.[0]?.line && (
              <span style={{
                fontSize: 13.5, color: colors.textSub, lineHeight: '20px',
                overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box',
                WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
              }}>{h.cuts[0].line}</span>
            )}
          </div>
          <button onClick={() => actions.openHistoryItem(h)} style={{ height: 48, borderRadius: 10, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', fontSize: 15, fontWeight: 700, padding: '0 18px', cursor: 'pointer', flex: 'none' }}>열기</button>
        </div>
      ))}
    </>
  );
}
