import { colors, bgGradient, rerollButtonStyle } from '../theme.js';
import { Label, TextInput, TextArea, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

const CATEGORIES = ['베이커리', '카페', '음식점', '소매점', '기타'];
const DAYS = ['월', '화', '수', '목', '금', '토', '일'];

export default function Store({ state, actions }) {
  const ro = state.storeReadOnly;
  const imageCount = state.storeImages.length;
  const maxImages = state.storeMaxImages;
  const atLimit = imageCount >= maxImages;

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (file) actions.uploadStoreImage(file);
    e.target.value = '';
  };

  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>업종</Label>
        <Select value={state.storeCategory} onChange={e => actions.set('storeCategory', e.target.value)} disabled={ro}>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </Select>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>대표 상품 이미지 (＋ 버튼으로 업로드)</Label>
        <span style={{ fontSize: 11.5, color: colors.textFaint }}>
          최대 {maxImages}장 · 장당 5MB 이하 · jpg · png · webp · {imageCount}/{maxImages}장
        </span>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {state.storeImages.map((im, i) => (
            <div key={i} style={{
              width: 112, height: 88, borderRadius: 12, border: `1px solid ${colors.cardBorder}`, position: 'relative', overflow: 'hidden',
              background: im.image ? undefined : bgGradient(im.hue),
              backgroundImage: im.image ? `url(${im.image})` : undefined,
              backgroundSize: 'cover', backgroundPosition: 'center', backgroundRepeat: 'no-repeat',
              display: 'flex', alignItems: 'flex-end', padding: 7
            }}>
              {!im.image && (
                <span style={{ fontSize: 11, fontWeight: 700, color: colors.primarySoftText, background: 'rgba(255,255,255,.8)', borderRadius: 6, padding: '2px 6px' }}>{im.label}</span>
              )}
              {!ro && (
                <button onClick={() => actions.deleteStoreImage(i)} title="삭제" style={rerollButtonStyle}>×</button>
              )}
            </div>
          ))}
          {!atLimit && (
            <label style={{
              width: 112, height: 88, borderRadius: 12, border: `1.5px dashed ${colors.inputBorder}`, background: '#fff', color: colors.textSub,
              fontSize: 24, cursor: ro ? 'not-allowed' : 'pointer', opacity: ro ? .45 : 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              ＋
              <input type="file" accept="image/jpeg,image/png,image/webp" disabled={ro} onChange={handleFile} style={{ display: 'none' }} />
            </label>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Label>가게 주소</Label>
          <TextInput value={state.storeAddress} onChange={e => actions.set('storeAddress', e.target.value)} readOnly={ro} placeholder="주소 입력" />
        </div>
        <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Label>영업시간</Label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TextInput type="time" value={state.storeOpenTime} onChange={e => actions.set('storeOpenTime', e.target.value)} readOnly={ro} disabled={ro} style={{ flex: 1 }} />
            <span style={{ color: colors.textFaint }}>–</span>
            <TextInput type="time" value={state.storeCloseTime} onChange={e => actions.set('storeCloseTime', e.target.value)} readOnly={ro} disabled={ro} style={{ flex: 1 }} />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>휴무일 (미선택 시 연중무휴)</Label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {DAYS.map(day => {
            const active = state.storeClosedDays.includes(day);
            return (
              <button
                key={day}
                type="button"
                disabled={ro}
                onClick={() => actions.toggleClosedDay(day)}
                style={{
                  width: 40, height: 40, borderRadius: 10, cursor: ro ? 'not-allowed' : 'pointer',
                  border: active ? `1.5px solid ${colors.primary}` : `1.5px solid ${colors.inputBorder}`,
                  background: active ? colors.primarySoft : '#fff',
                  color: active ? colors.primarySoftText : colors.text,
                  fontSize: 14, fontWeight: 700, opacity: ro ? .6 : 1,
                }}
              >{day}</button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>가게 소개</Label>
        <TextArea value={state.storeDesc} onChange={e => actions.set('storeDesc', e.target.value)} readOnly={ro} placeholder="예: 매일 아침 직접 구운 빵을 파는 동네 빵집이에요. 소금빵과 크루아상이 인기 메뉴예요." />
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 4 }}>
        <SecondaryButton onClick={actions.editStore} style={{ minWidth: 120, height: 52 }}>수정</SecondaryButton>
        <PrimaryButton onClick={actions.saveStore} disabled={ro} style={{ minWidth: 150 }}>입력(저장)</PrimaryButton>
      </div>
    </div>
  );
}
