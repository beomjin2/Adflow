import { colors } from '../theme.js';
import { Label, TextInput, TextArea, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';
import { bgGradient } from '../theme.js';

const CATEGORIES = ['베이커리', '카페', '음식점', '소매점', '기타'];

export default function Store({ state, actions }) {
  const ro = state.storeReadOnly;
  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>업종</Label>
        <Select value={state.storeCategory} onChange={e => actions.set('storeCategory', e.target.value)} disabled={ro}>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </Select>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>대표 상품 이미지 — ＋로 계속 추가</Label>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {state.storeImages.map((im, i) => (
            <div key={i} style={{ width: 112, height: 88, borderRadius: 12, border: `1px solid ${colors.cardBorder}`, position: 'relative', overflow: 'hidden', background: bgGradient(im.hue), display: 'flex', alignItems: 'flex-end', padding: 7 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: colors.primarySoftText, background: 'rgba(255,255,255,.8)', borderRadius: 6, padding: '2px 6px' }}>{im.label}</span>
              <button onClick={() => actions.rerollStoreImage(i)} title="다시 생성" style={{ position: 'absolute', top: 6, right: 6, width: 24, height: 24, borderRadius: 8, border: 0, background: 'rgba(255,255,255,.92)', color: colors.text, fontSize: 13, cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,.12)' }}>↻</button>
            </div>
          ))}
          <button onClick={actions.addImage} disabled={ro} style={{ width: 112, height: 88, borderRadius: 12, border: `1.5px dashed ${colors.inputBorder}`, background: '#fff', color: colors.textSub, fontSize: 24, cursor: ro ? 'not-allowed' : 'pointer', opacity: ro ? .45 : 1 }}>＋</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Label>가게 주소</Label>
          <TextInput value={state.storeAddress} onChange={e => actions.set('storeAddress', e.target.value)} readOnly={ro} placeholder="주소 입력" />
        </div>
        <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Label>영업시간</Label>
          <TextInput value={state.storeHours} onChange={e => actions.set('storeHours', e.target.value)} readOnly={ro} placeholder="예) 10:00 – 21:00, 월 휴무" />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>가게 소개</Label>
        <TextArea value={state.storeDesc} onChange={e => actions.set('storeDesc', e.target.value)} readOnly={ro} placeholder="우리 가게를 한두 문장으로" />
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 4 }}>
        <SecondaryButton onClick={actions.editStore} style={{ minWidth: 120, height: 52 }}>수정</SecondaryButton>
        <PrimaryButton onClick={actions.saveStore} disabled={ro} style={{ minWidth: 150 }}>입력(저장)</PrimaryButton>
      </div>
    </div>
  );
}
