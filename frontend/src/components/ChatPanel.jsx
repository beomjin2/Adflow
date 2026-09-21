import { useEffect, useRef } from 'react';
import { colors, inputStyle, TAP } from '../theme.js';
import { TextBubble, CandidatesBubble, ComicBubble, PlanBubble, ProdBubble, ConfirmBubble } from './bubbles/Bubbles.jsx';

export default function ChatPanel({
  messages, thinking, thinkingLabel = '생각하는 중…',
  input, onInputChange, onSend,
  placeholder = '메시지 입력…',
  emptyHint = '',
  cands, charSelected, onSelectCand, onRerollCand,
  eta = 0,
  plan,
  comic, comicEta = 0, onRerollCut,
  prods, onPatchProd,
  pending, onConfirm, onDecline,
  title = '',
  height = 430
}) {
  const listRef = useRef(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking, cands, plan, comic]);

  const prodById = (id) => (prods || []).find(p => p.id === id);
  const empty = !messages.length && !thinking;
  // 제목을 주면 대화창 자체가 카드가 된다 — 머리글·대화·입력칸이 한 덩어리로 보인다.
  // 제목이 없으면 예전 모양 그대로다(캐릭터 화면이 그렇게 쓴다).
  const card = !!title;

  return (
    <div style={{
      flex: '1 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: card ? 0 : 8,
      ...(card ? {
        background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 20,
        boxShadow: '0 2px 6px rgba(20,28,36,.05)', overflow: 'hidden'
      } : null)
    }}>
      {card && (
        <div style={{ padding: '18px 20px 0' }}>
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.3px', color: colors.text }}>{title}</span>
        </div>
      )}

      <div ref={listRef} style={{
        flex: 1, minHeight: height, display: 'flex', flexDirection: 'column', gap: 10,
        overflowY: 'auto', maxHeight: height + 90,
        ...(card
          ? { padding: 20 }
          : { background: colors.bg, border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: 14 })
      }}>
        {/* 빈 대화창에 인사말을 미리 저장해두지 않는다. 안내는 화면이 하고, 기록은 사장님이 만든다. */}
        {empty && emptyHint && (
          <div style={{
            margin: 'auto', maxWidth: 340, textAlign: 'center', fontSize: 14,
            lineHeight: '22px', color: colors.textFaint, whiteSpace: 'pre-line'
          }}>{emptyHint}</div>
        )}

        {messages.map((m, i) => {
          if (m.kind === 'text') return <TextBubble key={i} role={m.role} text={m.text} />;
          if (m.kind === 'cands') return (
            <CandidatesBubble key={i} items={cands || []} selected={charSelected} eta={eta}
              onSelect={onSelectCand} onReroll={onRerollCand} />
          );
          if (m.kind === 'comic') return (
            <ComicBubble key={i} cuts={comic || []} eta={comicEta} onReroll={onRerollCut} />
          );
          if (m.kind === 'plan') return <PlanBubble key={i} items={(plan || []).map(c => ({ n: c.n, line: c.line }))} />;
          if (m.kind === 'prod') return (
            <ProdBubble key={i} prod={prodById(m.prodId)} onChange={(patch) => onPatchProd(m.prodId, patch)} />
          );
          if (m.kind === 'confirm') return (
            <ConfirmBubble key={i} pending={(pending || {})[m.pid]}
              onConfirm={() => onConfirm(m.pid)} onDecline={() => onDecline(m.pid)} />
          );
          return null;
        })}
        {thinking && (
          <div style={{
            alignSelf: 'flex-start', background: '#fff', border: `1px solid ${colors.cardBorder}`,
            borderRadius: 14, padding: '10px 14px', fontSize: 14, color: colors.textFaint,
            animation: 'shimmer 1.1s infinite'
          }}>{thinkingLabel}</div>
        )}
      </div>

      <div style={{
        display: 'flex', gap: 8,
        ...(card ? { padding: '14px 16px', borderTop: `1px solid ${colors.cardBorder}` } : null)
      }}>
        <input
          value={input} onChange={e => onInputChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) onSend(); }}
          placeholder={placeholder}
          aria-label="메시지 입력"
          style={{ ...inputStyle, flex: 1, minWidth: 0 }}
        />
        <button onClick={onSend} disabled={!input.trim()} style={{
          flex: 'none', whiteSpace: 'nowrap', height: TAP, padding: '0 22px', borderRadius: 12,
          border: 0, background: input.trim() ? colors.primary : colors.cardBorder,
          color: '#fff', fontSize: 16, fontWeight: 700,
          cursor: input.trim() ? 'pointer' : 'not-allowed',
          boxShadow: input.trim() ? '0 6px 12px rgba(22,160,107,.32)' : 'none'
        }}>전송</button>
      </div>
    </div>
  );
}
