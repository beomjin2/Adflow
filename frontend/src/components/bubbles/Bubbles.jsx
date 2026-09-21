import { useEffect, useState } from 'react';
import { colors } from '../../theme.js';
import ImageSlot, { formatEta } from '../ImageSlot.jsx';
import Lightbox from '../Lightbox.jsx';


/** 말풍선. 모양은 styles.css 의 `.ad-msg` 가 정한다 — 개선안에서 캐릭터 대화와
 *  광고 대화가 같은 모양이라 두 화면이 이 한 클래스를 같이 쓴다. */
export function TextBubble({ role, text }) {
  return <div className={`ad-msg ${role === 'me' ? 'me' : 'ai'}`}>{text}</div>;
}

export function CandidatesBubble({ items, selected, onSelect, onReroll, eta = 0 }) {
  // 크게 보고 있는 후보의 번호. -1이면 팝업이 닫혀 있다.
  const [preview, setPreview] = useState(-1);

  const drawing = items.filter((c) => c.status === 'generating').length;
  const failed = items.filter((c) => c.status === 'failed').length;
  const done = items.filter((c) => c.status === 'done').length;

  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>
        {drawing > 0
          ? `그림을 그리고 있어요 — ${drawing}장 남았어요`
          : done > 0
            ? '후보가 나왔어요 — 눌러서 크게 보고 고르세요'
            : '아직 그림이 없어요'}
      </span>
      {drawing > 0 && eta > 0 && (
        <span style={hintStyle}>약 {formatEta(eta)}. 이 화면을 닫아도 계속 그려요.</span>
      )}
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        {items.map((c, i) => (
          <ImageSlot
            key={i} slot={c} size={96} eta={eta}
            selectable selected={selected === i}
            onClick={() => setPreview(i)} onReroll={() => onReroll(i)}
          />
        ))}
      </div>
      {failed > 0 && (
        <span style={{ ...hintStyle, color: colors.warnText }}>
          {failed}장은 그리지 못했어요. ↻ 를 누르면 그 자리만 다시 그려요.
        </span>
      )}
      {done > 0 && drawing === 0 && (
        <span style={hintStyle}>↻ 는 설정을 그대로 두고 그림만 다시 뽑아요. 고치고 싶은 점은 그냥 말해주세요.</span>
      )}

      {/* 그림을 누르면 여기서 크게 본다. 고르는 건 팝업 안의 '선택하기' 버튼이 한다 —
          누르는 것과 정하는 것은 다른 일이다. */}
      <Lightbox
        items={items} index={preview} selected={selected}
        onClose={() => setPreview(-1)} onMove={setPreview} onSelect={onSelect}
      />
    </div>
  );
}

/** 네컷 그림. 대화 안의 **한 장짜리 말풍선**이다 — 캐릭터 후보와 똑같이 작은 칸 몇 개로
 *  놓고, 크게 보려면 눌러서 본다. 대화창 폭을 통째로 먹는 큰 그림판을 끼워 넣으면
 *  그건 대화가 아니라 화면이 하나 더 열린 것이고, 스크롤도 그만큼 길어진다.
 *
 *  대사가 얹힌 큰 네컷은 결과 화면의 몫이다. */
export function ComicBubble({ cuts, eta = 0, onReroll }) {
  const [preview, setPreview] = useState(-1);
  const items = cuts || [];
  if (!items.length) return null;

  const drawing = items.filter((c) => c.status === 'generating').length;
  const failed = items.filter((c) => c.status === 'failed').length;
  const done = items.filter((c) => c.status === 'done' && c.image).length;

  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>
        {drawing > 0
          ? `네컷을 그리는 중 — ${drawing}컷 남았어요`
          : done > 0
            ? '네컷이 나왔어요 — 눌러서 크게 보세요'
            : '아직 그림이 없어요'}
      </span>
      {drawing > 0 && eta > 0 && (
        <span style={hintStyle}>약 {formatEta(eta)}. 이 화면을 닫아도 계속 그려요.</span>
      )}
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        {items.map((c, i) => (
          <ImageSlot
            key={c.n ?? i} slot={c} size={92} eta={eta}
            selectable onClick={() => setPreview(i)} onReroll={() => onReroll?.(c.n)}
          />
        ))}
      </div>
      {failed > 0 && (
        <span style={{ ...hintStyle, color: colors.warnText }}>
          {failed}컷은 그리지 못했어요. ↻ 를 누르면 그 자리만 다시 그려요.
        </span>
      )}
      {/* 네컷은 고르는 게 아니라 보는 것이라 onSelect를 주지 않는다. */}
      <Lightbox items={items} index={preview} selected={-1}
        onClose={() => setPreview(-1)} onMove={setPreview} />
    </div>
  );
}

export function PlanBubble({ items }) {
  if (!items.length) return null;
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>지금까지 정해진 컷</span>
      {items.map((c) => (
        <div key={c.n} style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
          <span style={cutTagStyle}>{c.n}컷</span>
          <span style={{ fontSize: 14, lineHeight: '21px', color: colors.text }}>{c.line}</span>
        </div>
      ))}
      <span style={hintStyle}>고치고 싶은 컷을 말해주세요 — 그 자리에서 바로 반영돼요.</span>
    </div>
  );
}

export function ProdBubble({ prod, onChange }) {
  if (!prod) return null;
  const missing = !prod.soldOut;
  const fieldStyle = { height: 42, borderRadius: 9, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 16, padding: '0 10px', minWidth: 0 };
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>생산 기록을 남겼어요 — 여기서 바로 고칠 수 있어요</span>
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        <Field label="품목"><DraftField value={prod.name} onCommit={v => onChange({ name: v })} style={{ ...fieldStyle, flex: '2 1 150px' }} /></Field>
        <Field label="수량(개)">
          <DraftField value={prod.qty} onCommit={v => onChange({ qty: v })} sanitize={v => v.replace(/[^0-9]/g, '')}
            inputMode="numeric" style={{ ...fieldStyle, flex: '1 1 92px' }} />
        </Field>
        <Field label="생산 날짜"><input type="date" value={prod.date} onChange={e => onChange({ date: e.target.value })} style={{ ...fieldStyle, flex: '1 1 150px' }} /></Field>
        <Field label="생산 시각"><input type="time" value={prod.time} onChange={e => onChange({ time: e.target.value })} style={{ ...fieldStyle, flex: '1 1 118px' }} /></Field>
        <Field label="매진 시각"><input type="time" value={prod.soldOut} onChange={e => onChange({ soldOut: e.target.value })} style={{ ...fieldStyle, flex: '1 1 118px', borderColor: missing ? '#E0BE74' : colors.inputBorder }} /></Field>
      </div>
      <span style={{ fontSize: 12.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>
        {missing ? '매진 시각을 적어두면 다음 광고 시간을 잡아드려요' : `매진 ${prod.soldOut} 기록됨`}
      </span>
    </div>
  );
}

/** 타이핑마다 바로 onChange(→서버 PATCH)를 쏘면, 응답이 느릴 때 뒤늦게 도착한 이전
 *  글자의 응답이 입력값을 예전 상태로 덮어써 타이핑이 씹히는 것처럼 보인다(품목·수량 둘
 *  다 겪던 문제 — My/ProductionTab.jsx의 DraftInput과 같은 원인·같은 해법). 로컬에서만
 *  타이핑을 받고, 포커스를 벗어나거나 Enter를 눌렀을 때만 커밋한다. */
function DraftField({ value, onCommit, sanitize, style, ...props }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  const commit = () => {
    if (draft === value) return;
    onCommit(draft);
  };

  return (
    <input
      value={draft}
      onChange={e => setDraft(sanitize ? sanitize(e.target.value) : e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) e.target.blur(); }}
      style={style}
      {...props}
    />
  );
}

// 제안 종류마다 제목과 버튼 문구가 다르다. 키워드는 AI가 먼저 정해서 내놓는 것이라
// '바꾸기'가 아니라 '이대로 할게요'가 맞는 말이다.
const CONFIRM_COPY = {
  keywords: { title: '퍼스널 키워드 제안', yes: '이 키워드로 할게요', no: '직접 적을게요' },
  field: { title: '캐릭터 시트 수정', yes: '이대로 바꾸기', no: '그대로 두기' },
  plan: { title: '스토리 변경 제안', yes: '이대로 바꾸기', no: '그대로 두기' },
};

export function ConfirmBubble({ pending, onConfirm, onDecline }) {
  if (!pending) return null;
  const open = pending.status === 'open';
  const { title, yes, no } = CONFIRM_COPY[pending.kind] || CONFIRM_COPY.plan;
  return (
    <div style={{ maxWidth: '96%', background: '#fff', border: `1.5px solid ${colors.onboardBorder}`, borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .22s ease' }}>
      <span style={bubbleTitleStyle}>{title}</span>
      {(pending.diffs || []).map((d, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4, background: colors.bg, borderRadius: 10, padding: '9px 11px' }}>
          <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.textFaint, letterSpacing: .3 }}>{d.label}</span>
          <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textFaint, textDecoration: 'line-through' }}>{d.from}</span>
          <span style={{ fontSize: 14, lineHeight: '20px', color: colors.text, fontWeight: 600 }}>{d.to}</span>
        </div>
      ))}
      {open ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={onConfirm} style={{ flex: '1 1 160px', height: 48, borderRadius: 11, border: 0, background: colors.primary, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', boxShadow: '0 5px 10px rgba(22,160,107,.28)' }}>{yes}</button>
          <button onClick={onDecline} style={{ flex: '0 1 auto', height: 48, padding: '0 18px', borderRadius: 11, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 15, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>{no}</button>
        </div>
      ) : (
        <span style={{ fontSize: 12.5, fontWeight: 700, color: pending.status === 'applied' ? colors.primary : colors.textFaint }}>
          {pending.status === 'applied' ? '이 내용으로 바꿨어요' : '바꾸지 않았어요'}
        </span>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{label}</span>
      {children}
    </div>
  );
}

const bubbleCardStyle = { maxWidth: '96%', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 9, animation: 'pop .22s ease' };
const bubbleTitleStyle = { fontSize: 14, fontWeight: 700 };
const hintStyle = { fontSize: 12.5, color: colors.textFaint, lineHeight: '18px' };
const cutTagStyle = { fontSize: 12, fontWeight: 700, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 6, padding: '3px 7px', flex: 'none' };
