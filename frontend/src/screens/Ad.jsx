import { colors } from '../theme.js';
import { Label, Select } from '../components/ui/Field.jsx';
import { PrimaryButton } from '../components/ui/Button.jsx';

const AD_TYPES = ['인스타 게시물', '4컷만화'];
const AD_CONCEPTS = ['유쾌함', '감성', '정보형', '담백함'];

export default function Ad({ state, actions }) {
  const ready = !!state.adType && !!state.adConcept;
  const trendMeme = state.trendItems.find((m) => m.id === state.trendSel);

  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>어디에 쓸 광고인가요?</Label>
        <Select
          value={state.adType}
          onChange={e => actions.set('adType', e.target.value)}
          placeholder="광고 종류를 골라주세요"
        >
          {AD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </Select>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>어떤 느낌으로 만들까요?</Label>
        <Select
          value={state.adConcept}
          onChange={e => actions.set('adConcept', e.target.value)}
          placeholder="컨셉을 골라주세요"
        >
          {AD_CONCEPTS.map(c => <option key={c} value={c}>{c}</option>)}
        </Select>
      </div>

      <div style={{ background: colors.softBg, borderRadius: 14, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, color: colors.textFaint }}>이 광고에 쓰일 내용</span>
        <span style={{ fontSize: 14, lineHeight: '21px', color: colors.textSub }}>
          가게 — <b style={{ color: colors.text }}>{state.storeCategory || '미입력'}</b>
          {state.storeAddress ? ` · ${state.storeAddress}` : ''}
        </span>
        <span style={{ fontSize: 14, lineHeight: '21px', color: colors.textSub }}>
          캐릭터 — <b style={{ color: colors.text }}>{state.charName || (state.charConfirmed ? '이름 없음' : '미확정')}</b>
        </span>
        {trendMeme && (
          <span style={{ fontSize: 14, lineHeight: '21px', color: colors.textSub }}>
            트렌드 — <b style={{ color: colors.text }}>{trendMeme.name}</b>
          </span>
        )}
      </div>

      <PrimaryButton onClick={actions.applyAd} disabled={!ready}>
        {ready ? '다음 — 광고 내용 정하기' : '종류와 느낌을 골라주세요'}
      </PrimaryButton>

      <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint }}>
        다음 화면에서 대화로 컷 구성을 만듭니다. 여기서 고른 건 나중에도 바꿀 수 있어요.
      </span>
    </div>
  );
}
