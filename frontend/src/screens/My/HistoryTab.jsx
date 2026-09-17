import { useState } from 'react';
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
          <ConfirmDelete title={h.title} onDelete={() => actions.delHistoryItem(h.id)} />
        </div>
      ))}
    </>
  );
}

/** 지운 건 되돌릴 수 없다. 팝업으로 한 번 더 물어봐서 실수로 지우는 걸 막는다. */
function ConfirmDelete({ title, onDelete }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}
        style={{ height: 48, borderRadius: 10, border: 0, background: colors.softBg, color: colors.textSub, fontSize: 14, fontWeight: 700, padding: '0 14px', cursor: 'pointer', flex: 'none' }}>삭제</button>
      {open && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15,17,19,.42)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
        >
          <div style={{
            width: '100%', maxWidth: 340, background: '#fff', borderRadius: 18, padding: 22,
            display: 'flex', flexDirection: 'column', gap: 14, animation: 'pop .18s ease',
            boxShadow: '0 20px 50px rgba(0,0,0,.22)',
          }}>
            <span style={{ fontSize: 16, fontWeight: 700 }}>지울까요?</span>
            <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textSub }}>
              {title ? `“${title}”` : '이 보관함 항목'}을 삭제하면 되돌릴 수 없어요.
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => { setOpen(false); onDelete(); }}
                style={{ flex: 1, height: 46, borderRadius: 11, border: 0, background: colors.warnAccent, color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                지우기
              </button>
              <button onClick={() => setOpen(false)}
                style={{ flex: 'none', height: 46, padding: '0 16px', borderRadius: 11, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
