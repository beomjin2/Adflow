import { colors } from '../../theme.js';
import { Select } from '../../components/ui/Field.jsx';
import { PrimaryButton } from '../../components/ui/Button.jsx';

const fieldStyle = {
  height: 44, borderRadius: 12, border: `1.5px solid ${colors.inputBorder}`,
  background: '#fff', color: colors.text, fontSize: 14.5, padding: '0 14px', width: '100%', minWidth: 0
};

export default function ProductionTab({ state, actions }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>품목 — 생산 기록에 쓸 목록</span>
        <div style={{ border: `1px solid ${colors.cardBorder}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: colors.bg, borderBottom: `1px solid ${colors.cardBorder}`, padding: '9px 14px' }}>
            <span style={{ flex: '2 1 150px', fontSize: 11.5, fontWeight: 700, color: colors.textFaint }}>품목명</span>
            <span style={{ flex: '1 1 90px', fontSize: 11.5, fontWeight: 700, color: colors.textFaint }}>생산 건수</span>
            <span style={{ flex: '1 1 110px', fontSize: 11.5, fontWeight: 700, color: colors.textFaint }}>최근 생산</span>
            <span style={{ width: 52, flex: 'none' }} />
          </div>
          {state.items.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', fontSize: 12.5, color: colors.textFaint }}>등록된 품목이 없어요. 아래에서 추가해주세요.</div>
          ) : state.items.map((n, i) => {
            const mine = state.prods.filter(p => p.name === n);
            const last = mine[0];
            return (
              <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 14px', background: '#fff', borderBottom: i < state.items.length - 1 ? `1px solid #F1F3F4` : 'none' }}>
                <input value={n} onChange={e => actions.renameItem(n, e.target.value)} style={{ flex: '2 1 150px', minWidth: 0, height: 34, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: colors.text, fontSize: 13.5, fontWeight: 600, padding: '0 8px' }} />
                <span style={{ flex: '1 1 90px', fontSize: 13, color: colors.textSub }}>{mine.length}건</span>
                <span style={{ flex: '1 1 110px', fontSize: 13, color: colors.textSub }}>{last ? `${last.date} ${last.time}` : '—'}</span>
                <button onClick={() => actions.delItem(n)} title="품목 삭제" style={{ width: 52, flex: 'none', height: 30, borderRadius: 8, border: 0, background: colors.softBg, color: colors.textSub, fontSize: 11.5, fontWeight: 700, cursor: 'pointer' }}>삭제</button>
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input value={state.newItem} onChange={e => actions.set('newItem', e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') actions.addItem(); }}
            placeholder="품목 이름 — 예) 소금빵" style={fieldStyle} />
          <button onClick={actions.addItem} style={{ height: 44, padding: '0 18px', borderRadius: 12, border: 0, background: colors.primarySoft, color: colors.primarySoftText, fontSize: 14, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>품목 추가</button>
        </div>
      </div>

      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>생산 기록 추가</span>
        <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
          <LabeledField label="품목" style={{ flex: '2 1 170px' }}>
            <Select value={state.draftItem} onChange={e => actions.set('draftItem', e.target.value)}>
              {state.items.map(i => <option key={i}>{i}</option>)}
            </Select>
          </LabeledField>
          <LabeledField label="수량" style={{ flex: '1 1 96px' }}>
            <input value={state.draftQty} onChange={e => actions.set('draftQty', e.target.value)} placeholder="60개" style={fieldStyle} />
          </LabeledField>
          <LabeledField label="생산 날짜" style={{ flex: '1 1 142px' }}>
            <input type="date" value={state.draftDate} onChange={e => actions.set('draftDate', e.target.value)} style={fieldStyle} />
          </LabeledField>
          <LabeledField label="생산 시각" style={{ flex: '1 1 112px' }}>
            <input type="time" value={state.draftTime} onChange={e => actions.set('draftTime', e.target.value)} style={fieldStyle} />
          </LabeledField>
          <LabeledField label="매진 시각 (나중에 가능)" style={{ flex: '1 1 118px' }}>
            <input type="time" value={state.draftSold} onChange={e => actions.set('draftSold', e.target.value)} style={fieldStyle} />
          </LabeledField>
        </div>
        <PrimaryButton onClick={actions.addProd} style={{ alignSelf: 'flex-start', height: 48, minWidth: 150 }}>생산 기록 저장</PrimaryButton>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '2px 2px 0', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>생산 히스토리</span>
        <span style={{ fontSize: 11.5, color: colors.textFaint, lineHeight: '17px' }}>매진 시각이 빈 줄은 노란색으로 표시돼요 — 그 자리에서 입력하면 됩니다</span>
      </div>
      {state.prods.length === 0 ? (
        <div style={{ border: `1px dashed ${colors.inputBorder}`, borderRadius: 16, padding: 32, textAlign: 'center', fontSize: 13.5, color: colors.textFaint, lineHeight: '21px' }}>
          아직 생산 기록이 없어요.<br />위에서 추가하거나, 광고 생성 대화에서 말하면 자동으로 남아요.
        </div>
      ) : state.prods.map(p => {
        const missing = !p.soldOut;
        return (
          <div key={p.id} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '11px 13px', alignItems: 'start', background: missing ? colors.warnBg : '#fff', border: `1px solid ${missing ? colors.warnBorder : colors.cardBorder}`, borderRadius: 14, padding: '13px 15px' }}>
            <RowField label="품목"><input value={p.name} onChange={e => actions.patchProd(p.id, { name: e.target.value })} style={fieldStyle} /></RowField>
            <RowField label="수량"><input value={p.qty} onChange={e => actions.patchProd(p.id, { qty: e.target.value })} placeholder="60개" style={fieldStyle} /></RowField>
            <RowField label="생산 날짜"><input type="date" value={p.date} onChange={e => actions.patchProd(p.id, { date: e.target.value })} style={fieldStyle} /></RowField>
            <RowField label="생산 시각"><input type="time" value={p.time} onChange={e => actions.patchProd(p.id, { time: e.target.value })} style={fieldStyle} /></RowField>
            <RowField label="매진 시각"><input type="time" value={p.soldOut} onChange={e => actions.setSoldOut(p.id, e.target.value)} style={{ ...fieldStyle, borderColor: missing ? '#E0BE74' : colors.inputBorder }} /></RowField>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>상태</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 38 }}>
                <span style={{ fontSize: 11.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>{missing ? '매진 시각 미입력' : `매진 ${p.soldOut} 기록됨`}</span>
                <span style={{ flex: 1 }} />
                <button onClick={() => actions.delProd(p.id)} style={{ height: 28, borderRadius: 8, border: 0, background: colors.softBg, color: colors.textSub, fontSize: 11.5, fontWeight: 700, padding: '0 10px', cursor: 'pointer', flex: 'none' }}>삭제</button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LabeledField({ label, style, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, ...style }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>{label}</span>
      {children}
    </div>
  );
}

function RowField({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>{label}</span>
      {children}
    </div>
  );
}
