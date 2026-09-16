import { useState } from 'react';
import { colors, rerollButtonStyle } from '../theme.js';
import { Label, TextInput, TextArea, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

const CATEGORIES = ['베이커리', '카페', '음식점', '소매점', '기타'];
const DAYS = ['월', '화', '수', '목', '금', '토', '일'];
/** 휴대폰 사진은 10MB를 넘기도 한다. 올리다 실패하기 전에 미리 막고 이유를 말해준다. */
const MAX_MB = 10;

export default function Store({ state, actions }) {
  const ro = state.storeReadOnly;
  const imageCount = state.storeImages.length;
  const maxImages = state.storeMaxImages;
  const atLimit = imageCount >= maxImages;
  const [uploading, setUploading] = useState(false);

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      actions.toast('사진 파일만 올릴 수 있어요');
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      actions.toast(`사진이 너무 커요 (${MAX_MB}MB까지)`);
      return;
    }
    setUploading(true);
    try { await actions.uploadStoreImage(file); } finally { setUploading(false); }
  };

  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>업종</Label>
        <Select
          value={state.storeCategory}
          onChange={e => actions.set('storeCategory', e.target.value)}
          disabled={ro}
          placeholder="업종을 골라주세요"
        >
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </Select>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>대표 상품 사진 — ＋를 눌러 올려주세요</Label>
        <span style={{ fontSize: 11.5, color: colors.textFaint }}>
          최대 {maxImages}장 · 장당 5MB 이하 · jpg · png · webp · {imageCount}/{maxImages}장
        </span>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {state.storeImages.map((im, i) => (
            <div key={i} style={{
              width: 116, height: 92, borderRadius: 12, border: `1px solid ${colors.cardBorder}`,
              position: 'relative', overflow: 'hidden', background: colors.bg, flex: 'none',
            }}>
              {im.image ? (
                <img src={im.image} alt={im.label || '가게 사진'} loading="lazy"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
              ) : (
                <span style={{
                  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 11.5, color: colors.textFaint, padding: 8, textAlign: 'center',
                }}>{im.label || '사진 없음'}</span>
              )}
              {!ro && (
                <button onClick={() => actions.deleteStoreImage(i)} title="이 사진 지우기" aria-label="사진 지우기" style={rerollButtonStyle}>×</button>
              )}
            </div>
          ))}
          {!atLimit && (
            <label style={{
              width: 116, height: 92, borderRadius: 12, border: `1.5px dashed ${colors.inputBorder}`,
              background: '#fff', color: colors.textSub, flex: 'none',
              fontSize: 13, fontWeight: 600, cursor: ro || uploading ? 'not-allowed' : 'pointer',
              opacity: ro || uploading ? .45 : 1,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2,
            }}>
              <span style={{ fontSize: 22 }}>{uploading ? '…' : '＋'}</span>
              <span>{uploading ? '올리는 중' : '사진 추가'}</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" disabled={ro || uploading} onChange={handleFile} style={{ display: 'none' }} />
            </label>
          )}
        </div>
        {state.storeImages.length === 0 && (
          <span style={{ fontSize: 12.5, color: colors.textFaint, lineHeight: '19px' }}>
            잘 나온 상품 사진이 있으면 광고 만들 때 같이 써요. 없어도 다음으로 넘어갈 수 있어요.
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Label>가게 주소</Label>
          <TextInput value={state.storeAddress} onChange={e => actions.set('storeAddress', e.target.value)} readOnly={ro} placeholder="예) 서울 마포구 ○○로 12" />
        </div>
        <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Label>영업시간</Label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TextInput type="time" value={state.storeOpenTime} onChange={e => actions.set('storeOpenTime', e.target.value)} readOnly={ro} disabled={ro} aria-label="여는 시각" style={{ flex: 1 }} />
            <span style={{ color: colors.textFaint }}>–</span>
            <TextInput type="time" value={state.storeCloseTime} onChange={e => actions.set('storeCloseTime', e.target.value)} readOnly={ro} disabled={ro} aria-label="닫는 시각" style={{ flex: 1 }} />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>쉬는 날 — 쉬는 요일을 눌러주세요 (없으면 그냥 두세요)</Label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {DAYS.map(day => {
            const active = state.storeClosedDays.includes(day);
            return (
              <button
                key={day}
                type="button"
                disabled={ro}
                aria-pressed={active}
                onClick={() => actions.toggleClosedDay(day)}
                style={{
                  width: 48, height: 48, borderRadius: 10, cursor: ro ? 'not-allowed' : 'pointer',
                  border: active ? `1.5px solid ${colors.primary}` : `1.5px solid ${colors.inputBorder}`,
                  background: active ? colors.primarySoft : '#fff',
                  color: active ? colors.primarySoftText : colors.text,
                  fontSize: 16, fontWeight: 700, opacity: ro ? .6 : 1,
                }}
              >{day}</button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>가게 소개</Label>
        <TextArea value={state.storeDesc} onChange={e => actions.set('storeDesc', e.target.value)} readOnly={ro} placeholder="우리 가게를 한두 문장으로 — 광고 문구를 만들 때 그대로 씁니다" />
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap', paddingTop: 4 }}>
        {ro && (
          <SecondaryButton onClick={actions.editStore} style={{ minWidth: 120, flex: '0 1 auto' }}>수정</SecondaryButton>
        )}
        {!ro && (
          <PrimaryButton onClick={actions.saveStore} style={{ minWidth: 150, flex: '0 1 auto' }}>저장</PrimaryButton>
        )}
      </div>
    </div>
  );
}
