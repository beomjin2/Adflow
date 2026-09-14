import { colors } from '../theme.js';
import { Label, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';

const AD_TYPES = ['인스타 게시물', '포스터', '메뉴판'];
const AD_CONCEPTS = ['유쾌함', '감성', '정보형', '담백함'];

export default function Ad({ state, actions }) {
  const trendYesDisabled = state.adType === '메뉴판';
  const trendHint = trendYesDisabled
    ? "메뉴판은 트렌드를 붙이기 어려워 '예'가 꺼져 있어요."
    : '요즘 뜨는 밈을 얹으면 반응이 빨라요.';

  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 16, position: 'relative' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>광고 종류 선택</Label>
        <Select value={state.adType} onChange={e => actions.set('adType', e.target.value)}>
          {AD_TYPES.map(t => <option key={t}>{t}</option>)}
        </Select>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <Label>광고 컨셉 (설정)</Label>
        <Select value={state.adConcept} onChange={e => actions.set('adConcept', e.target.value)}>
          {AD_CONCEPTS.map(c => <option key={c}>{c}</option>)}
        </Select>
      </div>
      <div style={{ background: colors.softBg, borderRadius: 14, padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
        <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>
          사용될 캐릭터 — <b style={{ color: colors.text }}>{state.charName || '미확정'}</b> · 가게 — <b style={{ color: colors.text }}>{state.storeCategory}</b>
        </span>
      </div>
      <PrimaryButton onClick={actions.applyAd}>적용</PrimaryButton>

      {state.trendPopup && (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(18,22,26,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div style={{ width: 360, maxWidth: '100%', background: '#fff', borderRadius: 18, padding: 20, display: 'flex', flexDirection: 'column', gap: 12, boxShadow: '0 18px 40px rgba(18,22,26,.22)', animation: 'pop .18s ease' }}>
            <span style={{ fontSize: 17, fontWeight: 700, textAlign: 'center', letterSpacing: -.3 }}>트렌드를 적용할까요?</span>
            <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub, textAlign: 'center' }}>{trendHint}</span>
            <div style={{ display: 'flex', gap: 9 }}>
              <SecondaryButton onClick={actions.trendNo} style={{ flex: 1, height: 48 }}>아니오</SecondaryButton>
              <PrimaryButton onClick={actions.trendYes} disabled={trendYesDisabled} style={{ flex: 1, height: 48, fontSize: 15 }}>예</PrimaryButton>
            </div>
            <SoftButton onClick={actions.goTrendFromAd} style={{ height: 44, fontSize: 14 }}>요즘 트렌드가 뭔데? — 트렌드 확인</SoftButton>
          </div>
        </div>
      )}
    </div>
  );
}
