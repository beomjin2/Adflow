import { useState } from 'react';
import { colors } from '../../theme.js';

/** 마스코트 보관소.
 *
 *  왜 따로 두나. `character` 는 행 하나(id=1)로 "지금 쓰는 캐릭터"만 들고 있어서,
 *  새로 만들면 이전 것이 그대로 덮어써져 사라졌다. 확정할 때마다 여기 한 장씩
 *  쌓아 두고, 골라서 다시 쓰거나 그걸 바탕으로 고칠 수 있게 한다.
 *
 *  홍보물(보관함)과 나눠 둔 이유도 같다 — 만든 것과 만드는 재료는 다른 물건이다. */
export default function MascotTab({ state, actions }) {
  const [confirmId, setConfirmId] = useState(null);
  const items = state.mascots || [];

  if (!items.length) {
    return (
      <div style={{ padding: 28, textAlign: 'center', fontSize: 14, lineHeight: '22px', color: colors.textFaint }}>
        아직 보관한 마스코트가 없어요.<br />
        캐릭터를 만들고 ‘이 캐릭터로 확정’을 누르면 여기에 쌓여요.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span style={{ fontSize: 12.5, color: colors.textFaint, lineHeight: '19px' }}>
        확정할 때마다 한 장씩 쌓여요. 불러오면 지금 캐릭터가 되고, 그 상태에서 대화로 고칠 수 있어요 —
        보관소의 원본은 그대로 남습니다.
      </span>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 12 }}>
        {items.map((m) => {
          const using = state.charName && m.name === state.charName && state.charConfirmed;
          return (
            <div key={m.id} style={{
              border: `1.5px solid ${using ? colors.primary : colors.cardBorder}`,
              borderRadius: 14, background: '#fff', overflow: 'hidden',
              display: 'flex', flexDirection: 'column',
            }}>
              <div style={{ aspectRatio: '832 / 1216', background: colors.bg, position: 'relative' }}>
                {m.image ? (
                  <img src={m.image} alt={m.name || '마스코트'} style={{
                    width: '100%', height: '100%', objectFit: 'cover', display: 'block',
                  }} />
                ) : (
                  <div style={{
                    position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: 12.5, color: colors.textFaint,
                  }}>그림 없음</div>
                )}
                {using && (
                  <span style={{
                    position: 'absolute', left: 8, top: 8, background: colors.primary, color: '#fff',
                    borderRadius: 999, padding: '3px 9px', fontSize: 11, fontWeight: 800,
                  }}>지금 쓰는 중</span>
                )}
              </div>

              <div style={{ padding: 11, display: 'flex', flexDirection: 'column', gap: 7 }}>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: colors.text }}>
                  {m.name || '이름 없음'}
                </span>
                <span style={{ fontSize: 12, lineHeight: '17px', color: colors.textSub, minHeight: 34 }}>
                  {((m.sheet || {}).look || '').slice(0, 42) || '외형 없음'}
                </span>
                <span style={{ fontSize: 11, color: colors.textFaint }}>{m.created_at}</span>

                <button onClick={() => actions.useMascot(m.id)} style={{
                  height: 40, borderRadius: 10, border: 0, background: colors.primary, color: '#fff',
                  fontSize: 13.5, fontWeight: 700, cursor: 'pointer',
                }}>불러와서 쓰기</button>

                {/* 되돌릴 수 없으니 한 번 더 묻는다 — 캐릭터 초기화와 같은 모양이다. */}
                {confirmId === m.id ? (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => { setConfirmId(null); actions.deleteMascot(m.id); }} style={{
                      flex: 1, height: 34, borderRadius: 8, border: 0, background: colors.warnAccent,
                      color: '#fff', fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
                    }}>지울까요? 네</button>
                    <button onClick={() => setConfirmId(null)} style={{
                      flex: 'none', height: 34, padding: '0 11px', borderRadius: 8, border: 0,
                      background: colors.softBg, color: colors.textSub, fontSize: 12.5, fontWeight: 700,
                      cursor: 'pointer',
                    }}>아니오</button>
                  </div>
                ) : (
                  <button onClick={() => setConfirmId(m.id)} style={{
                    border: 0, background: 'transparent', color: colors.textFaint,
                    fontSize: 12, fontWeight: 700, cursor: 'pointer', textDecoration: 'underline',
                    padding: '2px', alignSelf: 'flex-start',
                  }}>지우기</button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
