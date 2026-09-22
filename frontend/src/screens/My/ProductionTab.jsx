import { useEffect, useState } from 'react';
import { colors } from '../../theme.js';
import { Select } from '../../components/ui/Field.jsx';
import { PrimaryButton } from '../../components/ui/Button.jsx';

const fieldStyle = {
  height: 48, borderRadius: 12, border: `1.5px solid ${colors.inputBorder}`,
  background: '#fff', color: colors.text, fontSize: 16, padding: '0 14px', width: '100%', minWidth: 0
};

// 한 번에 보여주는 날짜 그룹 수. "더보기"를 누를 때마다 이만큼 더 연다.
const DAYS_PAGE = 7;

export default function ProductionTab({ state, actions }) {
  // 리스트가 길어지면 지금 어떤 기록을 보고 있었는지 놓치기 쉽다 — 줄을 클릭하면 노란
  // 테두리로 표시해 둔다. 서버에 남기는 값이 아니라 화면에서만 쓰는 표시라 로컬 state.
  const [selectedId, setSelectedId] = useState(null);
  // 안쪽에 스크롤 박스를 두면 페이지 스크롤 안에 스크롤이 하나 더 생겨 오히려 쓰기
  // 불편하다(특히 모바일). 대신 날짜 그룹을 최근 것부터 일정 개수만 보여주고,
  // "더보기"를 눌러야 그 이전 날짜가 나오게 한다.
  const [visibleDays, setVisibleDays] = useState(DAYS_PAGE);
  // 날짜 카드는 기본적으로 "오늘이거나 매진 미입력이 남아있으면 펼침"을 매 렌더마다
  // 새로 계산한다 — 미입력 기록을 하나 채워도 같은 날짜에 다른 미입력이 남아있으면
  // 계속 펼쳐져 있어야 한다. 사장님이 직접 펼치거나 접은 날짜만 여기에 기록해서
  // 그 선택을 계산값보다 우선한다.
  const [manualOpen, setManualOpen] = useState({});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <span style={sectionTitle}>품목 — 자주 만드는 것들을 등록해두세요</span>
        <div style={{ border: `1px solid ${colors.cardBorder}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: colors.bg, borderBottom: `1px solid ${colors.cardBorder}`, padding: '9px 14px' }}>
            <span style={{ flex: '2 1 150px', ...thStyle }}>품목명</span>
            <span style={{ flex: '1 1 90px', ...thStyle }}>기록 수</span>
            <span style={{ flex: '1 1 110px', ...thStyle }}>최근 생산</span>
            <span style={{ width: 60, flex: 'none' }} />
          </div>
          {state.items.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', fontSize: 13.5, color: colors.textFaint }}>등록된 품목이 없어요. 아래에서 추가해주세요.</div>
          ) : state.items.map((n, i) => {
            const mine = state.prods.filter(p => p.name === n);
            const last = mine[0];
            return (
              <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 14px', background: '#fff', borderBottom: i < state.items.length - 1 ? '1px solid #F1F3F4' : 'none' }}>
                <ItemNameInput name={n} onRename={actions.renameItem} />
                <span style={{ flex: '1 1 90px', fontSize: 14, color: colors.textSub }}>{mine.length}건</span>
                <span style={{ flex: '1 1 110px', fontSize: 14, color: colors.textSub }}>{last ? `${last.date} ${last.time}` : '—'}</span>
                <ConfirmDelete onDelete={() => actions.delItem(n)} width={60} />
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input value={state.newItem} onChange={e => actions.set('newItem', e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) actions.addItem(); }}
            aria-label="새 품목 이름"
            placeholder="품목 이름을 적고 추가를 눌러주세요" style={{ ...fieldStyle, flex: '1 1 200px', width: 'auto' }} />
          <button onClick={actions.addItem} style={{ height: 48, padding: '0 18px', borderRadius: 12, border: 0, background: colors.primarySoft, color: colors.primarySoftText, fontSize: 15, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap', flex: 'none' }}>품목 추가</button>
        </div>
      </div>

      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <span style={sectionTitle}>오늘 만든 것 적기</span>
        <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
          <LabeledField label="품목" style={{ flex: '2 1 170px' }}>
            <Select value={state.draftItem} onChange={e => actions.set('draftItem', e.target.value)} placeholder="골라주세요" style={fieldStyle}>
              {state.items.map(i => <option key={i} value={i}>{i}</option>)}
            </Select>
          </LabeledField>
          <LabeledField label="수량(개)" style={{ flex: '1 1 110px' }}>
            <input value={state.draftQty} onChange={e => actions.set('draftQty', digitsOnly(e.target.value))}
              inputMode="numeric" aria-label="수량" placeholder="예) 60" style={fieldStyle} />
          </LabeledField>
          <LabeledField label="만든 날짜" style={{ flex: '1 1 150px' }}>
            <input type="date" value={state.draftDate} onChange={e => actions.set('draftDate', e.target.value)} aria-label="만든 날짜" style={fieldStyle} />
          </LabeledField>
          <LabeledField label="만든 시각" style={{ flex: '1 1 160px' }}>
            <TimeNowInput value={state.draftTime} onChange={v => actions.set('draftTime', v)} ariaLabel="만든 시각" />
          </LabeledField>
          <LabeledField label="매진 시각 (나중에 적어도 돼요)" style={{ flex: '1 1 160px' }}>
            <TimeNowInput value={state.draftSold} onChange={v => actions.set('draftSold', v)} ariaLabel="매진 시각" />
          </LabeledField>
        </div>
        <PrimaryButton onClick={actions.addProd} disabled={!state.draftItem} style={{ alignSelf: 'flex-start', minWidth: 160 }}>
          기록 저장
        </PrimaryButton>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '2px 2px 0', flexWrap: 'wrap' }}>
        <span style={sectionTitle}>지금까지 적은 기록</span>
      </div>
      {state.prods.length === 0 ? (
        <div style={{ border: `1px dashed ${colors.inputBorder}`, borderRadius: 16, padding: 32, textAlign: 'center', fontSize: 14, color: colors.textFaint, lineHeight: '22px' }}>
          아직 기록이 없어요.<br />위에서 적어주세요.
        </div>
      ) : (() => {
        const groups = groupByDate(state.prods);
        // 매진 시각 미입력이 있는 날짜는 며칠 전이든 상관없이 항상 보여준다 — "더보기"
        // 뒤에 숨으면 사장님이 챙겨야 할 걸 놓친다. 나머지(다 채워진 날짜)만 최근
        // visibleDays개까지만 먼저 보여주고 그 이후는 "더보기"로 넘긴다.
        const recentKeys = new Set(groups.slice(0, visibleDays).map(([k]) => k));
        const shown = groups.filter(([k, list]) => recentKeys.has(k) || list.some(p => !p.soldOut));
        const rest = groups.length - shown.length;
        return (
          <>
            {shown.map(([dateKey, list]) => {
              const missingCount = list.filter(p => !p.soldOut).length;
              // 오늘 것과, 매진 시각이 빠진 게 있는 날은 펼쳐서 눈에 띄게 둔다 — 그 밖의
              // 지난 기록은 접어서 한 줄만 차지하게 한다. 사장님이 직접 펼치거나 접었으면
              // (manualOpen) 그 선택을 그대로 따른다.
              const openByDefault = dateKey === todayKey() || missingCount > 0;
              const isOpen = Object.prototype.hasOwnProperty.call(manualOpen, dateKey)
                ? manualOpen[dateKey] : openByDefault;
              const toggle = () => setManualOpen((m) => ({ ...m, [dateKey]: !isOpen }));
              return (
                <div key={dateKey || '_none'}
                  style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, overflow: 'hidden' }}>
                  <div role="button" tabIndex={0} onClick={toggle}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
                    style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 15px', cursor: 'pointer', minHeight: 48, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 14.5, fontWeight: 700 }}>{dateLabel(dateKey)}</span>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: colors.textSub, background: colors.bg, borderRadius: 999, padding: '3px 9px' }}>{list.length}건</span>
                    {missingCount > 0 && (
                      <span style={{ fontSize: 12, fontWeight: 700, color: colors.warnText, background: colors.warnBg, border: `1px solid ${colors.warnBorder}`, borderRadius: 999, padding: '3px 9px' }}>
                        매진 시각 미입력 {missingCount}
                      </span>
                    )}
                    <span style={{ flex: 1 }} />
                    <span style={{ fontSize: 13, color: colors.textFaint, transition: 'transform .15s', transform: isOpen ? 'rotate(180deg)' : 'none' }}>⌄</span>
                  </div>
                  {isOpen && (
                    <div style={{ padding: '0 15px 13px', display: 'flex', flexDirection: 'column', gap: 11 }}>
                      {list.map(p => (
                        <RecordRow key={p.id} p={p} items={state.items} actions={actions}
                          selected={selectedId === p.id}
                          onSelect={() => setSelectedId(selectedId === p.id ? null : p.id)} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
            {rest > 0 && (
              <button type="button" onClick={() => setVisibleDays(v => v + DAYS_PAGE)}
                style={{ alignSelf: 'center', height: 44, padding: '0 20px', borderRadius: 12, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.textSub, fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                이전 기록 더보기 (남은 {rest}일)
              </button>
            )}
          </>
        );
      })()}
    </div>
  );
}

/** 오늘 날짜(YYYY-MM-DD). 그룹 펼침 기본값을 정할 때만 쓰는 화면 표시용 값이라,
 *  기록 저장에 쓰는 값(useAdMakerState의 today())과 달리 시간대 보정 없이 로컬 시각 그대로 쓴다. */
function todayKey() {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
}

/** 지금 시:분(HH:MM). "지금" 버튼이 시각 칸을 채울 때 쓴다. */
function nowHM() {
  const n = new Date();
  return `${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`;
}

/** 날짜 칸을 "오늘"/"어제"/"9월 18일 (금)"으로. 날짜가 비어 있으면 "날짜 없음". */
function dateLabel(dateKey) {
  if (!dateKey) return '날짜 없음';
  if (dateKey === todayKey()) return '오늘';
  const [y, m, d] = dateKey.split('-').map(Number);
  const date = new Date(y, (m || 1) - 1, d || 1);
  const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1);
  if (dateKey === `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`) {
    return '어제';
  }
  const days = ['일', '월', '화', '수', '목', '금', '토'];
  return `${m}월 ${d}일 (${days[date.getDay()]})`;
}

/** 날짜별로 묶어 최신 날짜가 위로 오게 정렬한다 — 날짜가 비어 있는 기록은 맨 뒤로. */
function groupByDate(prods) {
  const byDate = new Map();
  for (const p of prods) {
    const key = p.date || '';
    if (!byDate.has(key)) byDate.set(key, []);
    byDate.get(key).push(p);
  }
  const keys = [...byDate.keys()].sort((a, b) => {
    if (!a) return 1;
    if (!b) return -1;
    return b.localeCompare(a);
  });
  return keys.map((k) => [k, byDate.get(k)]);
}

/** 지나간 기록은 대부분 훑어보기만 한다 — 매번 5칸짜리 편집 폼을 펼쳐두면 하루에 몇
 *  건만 쌓여도 화면이 입력칸으로 빽빽해진다. 접혀 있을 땐 한 줄 요약만 보여주고,
 *  눌러야(선택 상태) 그때 고칠 수 있는 폼이 펼쳐진다. */
function RecordRow({ p, items, actions, selected, onSelect }) {
  const missing = !p.soldOut;
  const boxStyle = {
    background: missing ? colors.warnBg : '#fff',
    border: `${selected ? 2 : 1}px solid ${selected ? colors.warnAccent : (missing ? colors.warnBorder : colors.cardBorder)}`,
    borderRadius: 14,
  };

  if (!selected) {
    return (
      <div onClick={onSelect} role="button" tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(); } }}
        style={{ ...boxStyle, padding: '13px 15px', cursor: 'pointer' }}>
        <RecordSummary p={p} />
      </div>
    );
  }

  return (
    <div style={{ ...boxStyle, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 11 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '11px 13px', alignItems: 'start' }}>
        <RowField label="품목">
          <Select value={p.name} onChange={e => actions.patchProd(p.id, { name: e.target.value })} aria-label="품목" style={fieldStyle}>
            {/* 품목 목록에서 지워졌거나 이름이 바뀐 뒤에도 이 기록엔 옛 이름이 남아있을 수 있다 —
                목록에 없으면 지금 값을 옵션으로 하나 더 넣어서 "골랐는데 안 보이는" 상태를 막는다. */}
            {!items.includes(p.name) && p.name && <option value={p.name}>{p.name}</option>}
            {items.map(i => <option key={i} value={i}>{i}</option>)}
          </Select>
        </RowField>
        <RowField label="수량(개)">
          <DraftInput value={p.qty} onCommit={(v) => actions.patchProd(p.id, { qty: v })} sanitize={digitsOnly}
            inputMode="numeric" aria-label="수량(개)" style={fieldStyle} />
        </RowField>
        <RowField label="만든 날짜"><input type="date" value={p.date} onChange={e => actions.patchProd(p.id, { date: e.target.value })} aria-label="만든 날짜" style={fieldStyle} /></RowField>
        <RowField label="만든 시각">
          <TimeNowInput value={p.time} onChange={v => actions.patchProd(p.id, { time: v })} ariaLabel="만든 시각" />
        </RowField>
        <RowField label="매진 시각">
          <TimeNowInput value={p.soldOut} onChange={v => actions.setSoldOut(p.id, v)} ariaLabel="매진 시각"
            inputStyle={{ borderColor: missing ? '#E0BE74' : colors.inputBorder }} />
        </RowField>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
          <span style={fieldLabel}>상태</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 48 }}>
            <span style={{ fontSize: 12.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>{missing ? '매진 시각 미입력' : `매진 ${p.soldOut}`}</span>
            <span style={{ flex: 1 }} />
            <ConfirmDelete onDelete={() => actions.delProd(p.id)} width={64} />
          </div>
        </div>
      </div>
      <button type="button" onClick={onSelect}
        style={{ alignSelf: 'flex-end', height: 34, padding: '0 12px', borderRadius: 8, border: 0, background: colors.softBg, color: colors.textSub, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>
        접기 ▲
      </button>
    </div>
  );
}

/** 한 줄 요약 — 품목·수량·만든 시각과 매진 상태만. 날짜는 바깥 아코디언(날짜별 그룹)이
 *  이미 보여주고 있어서 여기선 반복하지 않는다. */
function RecordSummary({ p }) {
  const missing = !p.soldOut;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 14.5, fontWeight: 700 }}>{p.name || '이름 없음'}</span>
      {p.qty && <span style={{ fontSize: 13.5, color: colors.textSub }}>{p.qty}개</span>}
      <span style={{ fontSize: 13.5, color: colors.textSub }}>{p.time || '시각 없음'}</span>
      <span style={{ flex: 1 }} />
      {missing ? (
        <span style={{ fontSize: 12, fontWeight: 700, color: colors.warnText2, background: colors.warnBg, border: `1px solid ${colors.warnBorder}`, borderRadius: 999, padding: '3px 9px' }}>
          매진 시각 미입력
        </span>
      ) : (
        <span style={{ fontSize: 12, fontWeight: 700, color: colors.primary, background: colors.primarySoft, borderRadius: 999, padding: '3px 9px' }}>
          매진 {p.soldOut}
        </span>
      )}
    </div>
  );
}

/** 시각 칸 옆의 "지금" 버튼 — 매번 손으로 시:분을 고르지 않고 한 번에 채운다. */
function TimeNowInput({ value, onChange, ariaLabel, inputStyle }) {
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <input type="time" value={value} onChange={e => onChange(e.target.value)} aria-label={ariaLabel}
        style={{ ...fieldStyle, ...inputStyle, flex: 1, minWidth: 0 }} />
      <button type="button" onClick={() => onChange(nowHM())}
        style={{ flex: 'none', height: 48, padding: '0 12px', borderRadius: 12, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.textSub, fontSize: 13.5, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>
        지금
      </button>
    </div>
  );
}

/** 타이핑마다 서버에 이름 변경을 보내지 않는다 — 포커스를 벗어나거나 Enter를 눌렀을 때만
 *  커밋한다. 실패하면(중복 이름 등) 입력값을 그대로 두고 다시 고칠 수 있게 한다. */
function ItemNameInput({ name, onRename }) {
  const [draft, setDraft] = useState(name);

  const commit = async () => {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === name) { setDraft(name); return; }
    const ok = await onRename(name, trimmed);
    if (!ok) return;
  };

  return (
    <input
      value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) e.target.blur(); }}
      aria-label="품목명"
      style={{ flex: '2 1 150px', minWidth: 0, height: 42, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: colors.text, fontSize: 15, fontWeight: 600, padding: '0 8px' }}
    />
  );
}

/** 저장된 기록의 값(수량 등)을 고치는 칸 — 예전엔 타이핑마다 바로 서버로 쏘고, 서버가
 *  돌려준 값으로 이 입력의 value를 그 자리에서 덮어썼다. 그러면 응답이 느릴 때 한 글자
 *  더 치기 전에 이전 글자의 응답이 도착해 입력값이 중간에 예전 상태로 되돌아가는 버그가
 *  났다("60개"를 치는 중 "6"으로 되돌아가는 식). ItemNameInput과 같은 방식으로 로컬에서만
 *  타이핑을 받고, 포커스를 벗어나거나 Enter를 눌렀을 때만 커밋한다. */
function DraftInput({ value, onCommit, sanitize, style, ...props }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);

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

/** 수량 칸에서 숫자가 아닌 건 입력 자체가 안 되게(붙여넣기 포함) 그 자리에서 걸러낸다. */
function digitsOnly(value) {
  return value.replace(/[^0-9]/g, '');
}

/** 지운 건 되돌릴 수 없다. 한 번 더 누르게 해서 실수로 지우는 걸 막는다.
 *  브라우저 확인창(confirm) 대신 그 자리에서 물어본다 — 폰에서 확인창은 화면을 다 덮는다. */
function ConfirmDelete({ onDelete, width }) {
  const [armed, setArmed] = useState(false);
  if (armed) {
    return (
      <div style={{ display: 'flex', gap: 4, flex: 'none' }}>
        <button onClick={() => { setArmed(false); onDelete(); }}
          style={{ height: 40, borderRadius: 8, border: 0, background: colors.warnAccent, color: '#fff', fontSize: 13, fontWeight: 700, padding: '0 10px', cursor: 'pointer' }}>지울까요?</button>
        <button onClick={() => setArmed(false)} aria-label="취소"
          style={{ height: 40, width: 36, borderRadius: 8, border: 0, background: colors.softBg, color: colors.textSub, fontSize: 15, cursor: 'pointer' }}>×</button>
      </div>
    );
  }
  return (
    <button onClick={() => setArmed(true)}
      style={{ width, flex: 'none', height: 40, borderRadius: 8, border: 0, background: colors.softBg, color: colors.textSub, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>삭제</button>
  );
}

function LabeledField({ label, style, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, ...style }}>
      <span style={fieldLabel}>{label}</span>
      {children}
    </div>
  );
}

function RowField({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <span style={fieldLabel}>{label}</span>
      {children}
    </div>
  );
}

const sectionTitle = { fontSize: 14, fontWeight: 700, color: colors.textSub };
const thStyle = { fontSize: 12, fontWeight: 700, color: colors.textFaint };
const fieldLabel = { fontSize: 12, fontWeight: 700, color: colors.textFaint };
