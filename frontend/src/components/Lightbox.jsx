import { useEffect } from 'react';
import { colors } from '../theme.js';
import { PrimaryButton, SoftButton } from './ui/Button.jsx';

/** 후보 그림을 크게 보는 팝업.
 *
 *  후보 칸은 96px이라 눈매나 앞치마 무늬 같은 걸 보고 고를 수가 없다. 그렇다고 칸을
 *  키우면 대화창을 다 먹는다. 그래서 평소엔 작게 두고, 누르면 여기서 크게 본다.
 *
 *  **고르는 건 그림이 아니라 '선택하기' 버튼이 한다.** 예전에는 그림을 누르는 순간
 *  선택됐다 — 크게 보려고 눌렀을 뿐인데 골라져 버리니, 무엇을 하려는 건지 화면이
 *  알 수가 없었다. 누르는 것(= 보기)과 정하는 것(= 선택)을 갈라 둔다.
 */
export default function Lightbox({ items, index, selected, onClose, onMove, onSelect }) {
  const slot = index >= 0 ? items[index] : null;

  // 볼 수 있는 건 다 그려진 그림뿐이다. 그리는 중인 칸으로는 넘어가지 않는다.
  const viewable = items
    .map((c, i) => (c?.status === 'done' && c?.image ? i : -1))
    .filter((i) => i >= 0);
  const at = viewable.indexOf(index);

  useEffect(() => {
    if (!slot) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft' && at > 0) onMove(viewable[at - 1]);
      else if (e.key === 'ArrowRight' && at >= 0 && at < viewable.length - 1) onMove(viewable[at + 1]);
    };
    window.addEventListener('keydown', onKey);
    // 팝업이 떠 있는 동안 뒤 화면이 같이 스크롤되면 어디를 보고 있는지 놓친다.
    const had = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = had;
    };
  }, [slot, at, viewable, onClose, onMove]);

  if (!slot) return null;

  const isSelected = selected === index;
  const arrow = {
    width: 40, height: 40, borderRadius: 999, border: 0, flex: 'none',
    background: 'rgba(255,255,255,.92)', color: colors.text,
    fontSize: 18, cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,.2)',
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="후보 그림 크게 보기"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 80,
        background: 'rgba(16,20,24,.72)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 18, gap: 10,
      }}
    >
      {/* 배경을 누르면 닫히므로, 안쪽 클릭은 여기서 멈춘다. */}
      <div onClick={(e) => e.stopPropagation()} style={{
        display: 'flex', alignItems: 'center', gap: 10, maxWidth: '100%',
      }}>
        {viewable.length > 1 && (
          <button onClick={() => onMove(viewable[at - 1])} disabled={at <= 0}
            title="이전 후보" style={{ ...arrow, visibility: at > 0 ? 'visible' : 'hidden' }}>‹</button>
        )}

        <div style={{
          background: '#fff', borderRadius: 16, overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          maxWidth: 'min(92vw, 520px)', boxShadow: '0 10px 40px rgba(0,0,0,.3)',
        }}>
          <img
            src={slot.image}
            alt={slot.label || '후보 그림'}
            style={{ display: 'block', width: '100%', maxHeight: '64vh', objectFit: 'contain', background: colors.softBg }}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '13px 15px 15px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span style={{ fontSize: 15, fontWeight: 700 }}>{slot.label || '후보'}</span>
              {isSelected && (
                <span style={{
                  fontSize: 11.5, fontWeight: 800, color: '#fff',
                  background: colors.primary, borderRadius: 999, padding: '2px 9px',
                }}>선택함</span>
              )}
              {viewable.length > 1 && (
                <span style={{ fontSize: 12, color: colors.textFaint, marginLeft: 'auto' }}>
                  {at + 1} / {viewable.length}
                </span>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <PrimaryButton
                onClick={() => { onSelect(index); onClose(); }}
                disabled={isSelected}
                style={{ flex: '1 1 auto', height: 48, fontSize: 15.5 }}
              >
                {isSelected ? '이미 고른 그림이에요' : '선택하기'}
              </PrimaryButton>
              <SoftButton onClick={onClose} style={{ flex: '0 0 92px', height: 48, fontSize: 15 }}>
                닫기
              </SoftButton>
            </div>
          </div>
        </div>

        {viewable.length > 1 && (
          <button onClick={() => onMove(viewable[at + 1])} disabled={at >= viewable.length - 1}
            title="다음 후보" style={{ ...arrow, visibility: at < viewable.length - 1 ? 'visible' : 'hidden' }}>›</button>
        )}
      </div>
    </div>
  );
}
