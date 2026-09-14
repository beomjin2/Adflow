import { colors, bgGradient, rerollButtonStyle } from '../../theme.js';

export function TextBubble({ role, text }) {
  const mine = role === 'me';
  return (
    <div style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
      <div style={mine
        ? { maxWidth: '80%', background: colors.chatMeBg, color: '#fff', borderRadius: '14px 14px 4px 14px', padding: '10px 14px', fontSize: 13.5, lineHeight: '20px', fontWeight: 500 }
        : { maxWidth: '86%', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: '14px 14px 14px 4px', padding: '10px 14px', fontSize: 13.5, lineHeight: '20px' }}>
        {text}
      </div>
    </div>
  );
}

export function CandidatesBubble({ items, selected, onSelect, onReroll }) {
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>후보가 나왔어요 — 하나 골라주세요</span>
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        {items.map((c, i) => (
          <div key={i} style={{ position: 'relative' }}>
            <button onClick={() => onSelect(i)} style={{
              width: 92, height: 92, borderRadius: 12, cursor: 'pointer',
              background: bgGradient(c.hue),
              border: selected === i ? `2.5px solid ${colors.primary}` : `1px solid ${colors.cardBorder}`,
              color: colors.primarySoftText, fontSize: 11.5, fontWeight: 700,
              display: 'flex', alignItems: 'flex-end', justifyContent: 'center', paddingBottom: 8
            }}>{c.label}</button>
            <button onClick={() => onReroll(i)} title="같은 설정으로 다시 생성" style={rerollButtonStyle}>↻</button>
          </div>
        ))}
      </div>
      <span style={hintStyle}>↻ 는 설정을 그대로 두고 그림만 다시 뽑아요. 고치고 싶은 점은 그냥 말해주세요.</span>
    </div>
  );
}

export function ViewsBubble({ items, onReroll }) {
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>4방향으로 뽑았어요</span>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {items.map((v, i) => (
          <div key={i} style={{ position: 'relative', width: 86, height: 86, borderRadius: 12, border: `1px solid ${colors.cardBorder}`, overflow: 'hidden', background: bgGradient(v.hue), display: 'flex', alignItems: 'flex-end', justifyContent: 'center', padding: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: colors.primarySoftText, background: 'rgba(255,255,255,.85)', borderRadius: 6, padding: '2px 6px' }}>{v.label}</span>
            <button onClick={() => onReroll(i)} style={rerollButtonStyle}>↻</button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PlanBubble({ items }) {
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>스토리보드 텍스트 결과</span>
      {items.map((c) => (
        <div key={c.n} style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
          <span style={cutTagStyle}>{c.n}컷</span>
          <span style={{ fontSize: 13, lineHeight: '19px', color: colors.text }}>{c.line}</span>
        </div>
      ))}
      <span style={hintStyle}>고치고 싶은 컷을 말해주세요 — 그 자리에서 바로 반영돼요.</span>
    </div>
  );
}

export function ComicBubble({ items, onOpen, onReroll }) {
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>네컷만화 결과 — 누르면 크게 보기</span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, width: 230 }}>
        {items.map((c) => (
          <div key={c.n} style={{ position: 'relative', height: 100, borderRadius: 10, overflow: 'hidden', border: `1px solid ${colors.cardBorder}`, background: bgGradient(c.hue) }}>
            <button onClick={onOpen} style={{ position: 'absolute', inset: 0, border: 0, background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'flex-end', padding: 6 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, color: colors.primarySoftText, background: 'rgba(255,255,255,.85)', borderRadius: 5, padding: '2px 5px' }}>{c.n}컷</span>
            </button>
            <button onClick={() => onReroll(c.n)} title="이 컷만 다시 생성" style={rerollButtonStyle}>↻</button>
          </div>
        ))}
      </div>
      <span style={hintStyle}>컷마다 ↻ 로 그 컷만 다시 뽑을 수 있어요.</span>
    </div>
  );
}

export function ProdBubble({ prod, onChange }) {
  if (!prod) return null;
  const missing = !prod.soldOut;
  const fieldStyle = { height: 38, borderRadius: 9, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 13.5, padding: '0 10px', minWidth: 0 };
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>생산 기록을 남겼어요 — 여기서 바로 고칠 수 있어요</span>
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        <Field label="품목"><input value={prod.name} onChange={e => onChange({ name: e.target.value })} style={{ ...fieldStyle, flex: '2 1 150px' }} /></Field>
        <Field label="수량"><input value={prod.qty} onChange={e => onChange({ qty: e.target.value })} placeholder="60개" style={{ ...fieldStyle, flex: '1 1 92px' }} /></Field>
        <Field label="생산 날짜"><input type="date" value={prod.date} onChange={e => onChange({ date: e.target.value })} style={{ ...fieldStyle, flex: '1 1 136px' }} /></Field>
        <Field label="생산 시각"><input type="time" value={prod.time} onChange={e => onChange({ time: e.target.value })} style={{ ...fieldStyle, flex: '1 1 104px' }} /></Field>
        <Field label="매진 시각"><input type="time" value={prod.soldOut} onChange={e => onChange({ soldOut: e.target.value })} style={{ ...fieldStyle, flex: '1 1 112px', borderColor: missing ? '#E0BE74' : colors.inputBorder }} /></Field>
      </div>
      <span style={{ fontSize: 11.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>
        {missing ? '매진 시각 미입력' : `매진 ${prod.soldOut} 기록됨`}
      </span>
    </div>
  );
}

export function ConfirmBubble({ pending, onConfirm, onDecline }) {
  if (!pending) return null;
  const open = pending.status === 'open';
  const title = pending.kind === 'comic' ? '네컷만화 변경 제안' : pending.kind === 'char' ? '캐릭터 변경 제안' : '스토리 변경 제안';
  return (
    <div style={{ maxWidth: '96%', background: '#fff', border: `1.5px solid ${colors.onboardBorder}`, borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .22s ease' }}>
      <span style={bubbleTitleStyle}>{title}</span>
      {(pending.diffs || []).map((d, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4, background: colors.bg, borderRadius: 10, padding: '9px 11px' }}>
          <span style={{ fontSize: 10.5, fontWeight: 800, color: colors.textFaint, letterSpacing: .3 }}>{d.label}</span>
          <span style={{ fontSize: 12, lineHeight: '17px', color: colors.textFaint, textDecoration: 'line-through' }}>{d.from}</span>
          <span style={{ fontSize: 12.5, lineHeight: '18px', color: colors.text, fontWeight: 600 }}>{d.to}</span>
        </div>
      ))}
      {open ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onConfirm} style={{ flex: 1, height: 42, borderRadius: 11, border: 0, background: colors.primary, color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', boxShadow: '0 5px 10px rgba(22,160,107,.28)' }}>확인 — 이대로 변경</button>
          <button onClick={onDecline} style={{ flex: 'none', height: 42, padding: '0 16px', borderRadius: 11, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 14, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>그대로 두기</button>
        </div>
      ) : (
        <span style={{ fontSize: 11.5, fontWeight: 700, color: pending.status === 'applied' ? colors.primary : colors.textFaint }}>
          {pending.status === 'applied' ? '확인 — 이 내용으로 반영했어요' : '변경하지 않았어요'}
        </span>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>{label}</span>
      {children}
    </div>
  );
}

const bubbleCardStyle = { maxWidth: '96%', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 9, animation: 'pop .22s ease' };
const bubbleTitleStyle = { fontSize: 13, fontWeight: 700 };
const hintStyle = { fontSize: 11.5, color: colors.textFaint };
const cutTagStyle = { fontSize: 11, fontWeight: 700, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 6, padding: '3px 7px', flex: 'none' };
