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
  onSuggest,
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
    <div
      className={card ? 'ad-card ad-chat' : undefined}
      style={card ? undefined : { flex: '1 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      {card && (
        <div className="ad-chat-h">
          <h3>{title}</h3>
          <span className="ad-grow" />
          {onSuggest && (
            <button className="ad-btn tint sm" onClick={onSuggest} disabled={thinking}>
              ✨ 스토리 제안받기
            </button>
          )}
        </div>
      )}

      <div
        ref={listRef}
        className={card ? 'log' : undefined}
        style={card ? undefined : {
          flex: 1, minHeight: height, display: 'flex', flexDirection: 'column', gap: 10,
          overflowY: 'auto', maxHeight: height + 90,
          background: colors.bg, border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: 14
        }}
      >
        {/* 빈 대화창에 인사말을 미리 저장해두지 않는다. 안내는 화면이 하고, 기록은 사장님이 만든다. */}
        {empty && emptyHint && (
          card
            ? <div className="ad-chat-empty">{emptyHint}</div>
            : <div style={{
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

      <div className={card ? 'in' : undefined} style={card ? undefined : { display: 'flex', gap: 8 }}>
        <input
          value={input} onChange={e => onInputChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) onSend(); }}
          placeholder={placeholder}
          aria-label="메시지 입력"
          className={card ? 'ad-input' : undefined}
          style={card ? undefined : { ...inputStyle, flex: 1, minWidth: 0 }}
        />
        {card ? (
          <button className="ad-btn pri" onClick={onSend} disabled={!input.trim()} style={{ height: TAP, padding: '0 22px', flex: 'none' }}>
            전송
          </button>
        ) : (
          <button onClick={onSend} disabled={!input.trim()} style={{
            flex: 'none', whiteSpace: 'nowrap', height: TAP, padding: '0 22px', borderRadius: 12,
            border: 0, background: input.trim() ? colors.primary : colors.cardBorder,
            color: '#fff', fontSize: 16, fontWeight: 700,
            cursor: input.trim() ? 'pointer' : 'not-allowed',
            boxShadow: input.trim() ? '0 6px 12px rgba(22,160,107,.32)' : 'none'
          }}>전송</button>
        )}
      </div>
    </div>
  );
}
