import { useEffect, useRef } from 'react';
import { colors, inputStyle } from '../theme.js';
import { TextBubble, CandidatesBubble, ViewsBubble, PlanBubble, ComicBubble, ProdBubble, ConfirmBubble } from './bubbles/Bubbles.jsx';

export default function ChatPanel({
  messages, thinking, thinkingLabel = '생각하는 중…',
  input, onInputChange, onSend,
  cands, charSelected, onSelectCand, onRerollCand,
  views, onRerollView,
  plan, comicCuts, onOpenComic, onRerollCut,
  prods, onPatchProd,
  pending, onConfirm, onDecline,
  height = 430
}) {
  const listRef = useRef(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

  const prodById = (id) => (prods || []).find(p => p.id === id);

  return (
    <div style={{ flex: '1 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div ref={listRef} style={{
        flex: 1, minHeight: height, background: colors.bg, border: `1px solid ${colors.cardBorder}`,
        borderRadius: 16, padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
        overflowY: 'auto', maxHeight: height + 90
      }}>
        {messages.map((m, i) => {
          if (m.kind === 'text') return <TextBubble key={i} role={m.role} text={m.text} />;
          if (m.kind === 'cands') return (
            <CandidatesBubble key={i} items={cands || []} selected={charSelected}
              onSelect={onSelectCand} onReroll={onRerollCand} />
          );
          if (m.kind === 'views') return <ViewsBubble key={i} items={views || []} onReroll={onRerollView} />;
          if (m.kind === 'plan') return <PlanBubble key={i} items={(plan || []).map(c => ({ n: c.n, line: c.line }))} />;
          if (m.kind === 'comic') return (
            <ComicBubble key={i} items={comicCuts || []} onOpen={onOpenComic} onReroll={onRerollCut} />
          );
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
            borderRadius: 14, padding: '10px 14px', fontSize: 13.5, color: colors.textFaint,
            animation: 'shimmer 1.1s infinite'
          }}>{thinkingLabel}</div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input} onChange={e => onInputChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onSend(); }}
          placeholder="메시지 입력…"
          style={{ ...inputStyle, flex: 1, minWidth: 0 }}
        />
        <button onClick={onSend} style={{
          flex: 'none', whiteSpace: 'nowrap', height: 44, padding: '0 22px', borderRadius: 12,
          border: 0, background: colors.primary, color: '#fff', fontSize: 15, fontWeight: 700,
          cursor: 'pointer', boxShadow: '0 6px 12px rgba(22,160,107,.32)'
        }}>전송</button>
      </div>
    </div>
  );
}
