import { useEffect, useState } from 'react';
import { colors } from '../theme.js';
import { formatEta } from './ImageSlot.jsx';

/** 컷 한 장 + 말풍선. 말풍선은 배경 담당 기록의 네컷처럼 위쪽 귀퉁이에 내용만큼만 작게 —
 *  홀수 컷 왼쪽 위, 짝수 컷 오른쪽 위. 그림을 가리지 않는 게 우선이라 폭은 최대 72%. */
function Bubble({ cut, big = false }) {
  const left = cut.n % 2 === 1;
  const border = big ? '2px solid #222' : '1.5px solid #222';
  return (
    <div style={{ position: 'absolute', top: '3%', [left ? 'left' : 'right']: '4%', maxWidth: '72%', pointerEvents: 'none' }}>
      <div style={{
        background: '#fff', color: '#111', border, borderRadius: big ? 14 : 10,
        padding: big ? '8px 14px' : '5px 10px', fontSize: big ? 'clamp(14px, 2vw, 20px)' : 'clamp(11px, 1.6vw, 15px)',
        lineHeight: 1.35, fontWeight: 700, wordBreak: 'keep-all', boxShadow: '0 1px 2px rgba(0,0,0,.15)',
      }}>{cut.line}</div>
      <div style={{
        width: big ? 14 : 10, height: big ? 14 : 10, background: '#fff', borderLeft: border, borderBottom: border,
        transform: 'rotate(-45deg)', marginTop: big ? -8 : -6, marginLeft: left ? 16 : 'auto', marginRight: left ? 0 : 16,
      }} />
    </div>
  );
}

/** 네컷 2×2. 그림은 832×1216 비율 그대로. 더블클릭(모바일은 길게 두 번 탭 대신 한 번 탭)하면
 *  컷 하나를 화면 가득 크게 본다 — 작은 미리보기에서도 대사와 그림을 확인할 수 있게. */
export default function ComicPanels({ cuts, eta = 0, onReroll, bubbles = true, gap = 10 }) {
  const [zoom, setZoom] = useState(null); // 크게 보는 컷 번호

  useEffect(() => {
    if (zoom == null) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setZoom(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoom]);

  const zoomed = zoom != null ? cuts.find((c) => c.n === zoom) : null;

  return (
    <>
      {/* 인스타 게시물(1컷)은 한 칸짜리라 2열 그리드를 그대로 쓰면 오른쪽 절반이 빈 채로
          남는다 — 컷 수만큼만 열을 잡는다(최대 2열, 4컷만화는 기존처럼 2×2). */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(cuts.length, 2) || 1}, minmax(0, 1fr))`, gap }}>
        {cuts.map((c) => {
          const done = c.status === 'done' && !!c.image;
          return (
            <div key={c.n}
              onDoubleClick={() => { if (done) setZoom(c.n); }}
              title={done ? '더블클릭하면 크게 봐요' : undefined}
              style={{
                position: 'relative', aspectRatio: '832 / 1216', borderRadius: 10, overflow: 'hidden',
                border: `2px solid ${done ? '#2A2A2A' : colors.cardBorder}`, background: colors.bg,
                cursor: done ? 'zoom-in' : 'default', userSelect: 'none',
              }}>
              {done ? (
                <img src={c.image} alt={`${c.n}컷`} draggable={false}
                  style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
              ) : (
                <div style={{
                  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  padding: 8, textAlign: 'center', fontSize: 12.5, lineHeight: '18px',
                  color: c.status === 'failed' ? colors.warnText : colors.textFaint,
                  background: c.status === 'failed' ? colors.warnBg : colors.bg,
                }}>
                  {c.status === 'generating'
                    ? `그리는 중…${eta > 0 ? ` 약 ${formatEta(eta)}` : ''}`
                    : c.status === 'failed' ? '그리지 못했어요 — ↻로 다시' : `${c.n}컷`}
                </div>
              )}

              {bubbles && done && c.line && <Bubble cut={c} />}

              {onReroll && c.status !== 'generating' && (
                <button onClick={(e) => { e.stopPropagation(); onReroll(c.n); }} onDoubleClick={(e) => e.stopPropagation()}
                  title="같은 설정으로 다시 그리기" style={{
                    position: 'absolute', right: 6, bottom: 6, width: 30, height: 30, borderRadius: 999, border: 0,
                    background: 'rgba(255,255,255,.95)', color: '#222', fontSize: 15, fontWeight: 700, cursor: 'pointer',
                    boxShadow: '0 1px 3px rgba(0,0,0,.25)',
                  }}>↻</button>
              )}
            </div>
          );
        })}
      </div>

      {zoomed && (
        <div onClick={() => setZoom(null)} role="dialog" aria-label={`${zoomed.n}컷 크게 보기`} style={{
          position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.78)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, cursor: 'zoom-out',
        }}>
          <div style={{
            position: 'relative', height: 'min(92vh, calc((100vw - 48px) * 1216 / 832))', aspectRatio: '832 / 1216',
            borderRadius: 14, overflow: 'hidden', border: '3px solid #222', background: '#fff', boxShadow: '0 20px 60px rgba(0,0,0,.5)',
          }}>
            <img src={zoomed.image} alt={`${zoomed.n}컷`} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
            {zoomed.line && <Bubble cut={zoomed} big />}
            <span style={{
              position: 'absolute', left: 10, bottom: 10, background: 'rgba(0,0,0,.6)', color: '#fff',
              borderRadius: 8, padding: '3px 9px', fontSize: 12.5, fontWeight: 700,
            }}>{zoomed.n} / {cuts.length} · 닫기: 클릭 또는 Esc</span>
          </div>
        </div>
      )}
    </>
  );
}
