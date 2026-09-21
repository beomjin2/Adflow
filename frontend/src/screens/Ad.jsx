import { colors } from '../theme.js';
import { Label, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

const AD_TYPES = ['인스타 게시물', '4컷만화'];
const AD_CONCEPTS = ['유쾌함', '감성', '정보형', '담백함'];

/** 느낌은 네 개뿐이라 목록을 펼쳐 보여준다. 선택지가 손가락 아래 다 보이면
 *  사장님은 무엇 중에서 고르는지 알고 고른다 — select는 열어봐야 안다. */
function Chip({ on, children, ...props }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      style={{
        height: 48, padding: '0 18px', borderRadius: 999, cursor: 'pointer',
        border: `1.5px solid ${on ? colors.primary : colors.inputBorder}`,
        background: on ? colors.primary : '#fff',
        color: on ? '#fff' : colors.textSub,
        fontSize: 15, fontWeight: 700, whiteSpace: 'nowrap',
      }}
      {...props}
    >{children}</button>
  );
}

function Row({ label, children }) {
  return (
    <>
      <span style={{ fontSize: 13.5, fontWeight: 700, color: colors.textFaint, paddingTop: 2 }}>{label}</span>
      <span style={{ fontSize: 15, lineHeight: '22px', color: colors.text, minWidth: 0 }}>{children}</span>
    </>
  );
}

export default function Ad({ state, actions }) {
  const ready = !!state.adType && !!state.adConcept;
  const trendMeme = state.trendItems.find((m) => m.id === state.trendSel);
  // 비어 있는 칸은 비었다고 쓴다. 이 목록은 광고 문구에 그대로 들어갈 재료라,
  // 무엇이 비었는지 여기서 보이지 않으면 사장님은 결과를 보고서야 안다.
  const none = <span style={{ color: colors.textFaint }}>아직 없음</span>;

  return (
    <div style={{ padding: 22, display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      <div style={{ flex: '1 1 360px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 22 }}>
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <Label>어떤 느낌으로 만들까요?</Label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {AD_CONCEPTS.map(c => (
              <Chip key={c} on={state.adConcept === c} onClick={() => actions.set('adConcept', c)}>{c}</Chip>
            ))}
          </div>
        </div>

        <PrimaryButton onClick={actions.applyAd} disabled={!ready}>
          {ready ? '다음 — 광고 내용 정하기' : '종류와 느낌을 골라주세요'}
        </PrimaryButton>

        <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint, textAlign: 'center' }}>
          다음 화면에서 대화로 컷 구성을 만듭니다. 여기서 고른 건 나중에도 바꿀 수 있어요.
        </span>
      </div>

      <aside style={{
        flex: '1 1 280px', minWidth: 0, background: colors.softBg, borderRadius: 16,
        padding: 18, display: 'flex', flexDirection: 'column', gap: 14,
      }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: colors.text }}>이 광고에 쓰일 내용</span>

        <div style={{ display: 'grid', gridTemplateColumns: '68px minmax(0, 1fr)', gap: '10px 14px', alignItems: 'start' }}>
          <Row label="가게">
            {state.storeCategory
              ? <><b>{state.storeCategory}</b>{state.storeAddress ? ` · ${state.storeAddress}` : ''}</>
              : none}
          </Row>
          <Row label="캐릭터">
            {state.charConfirmed
              ? <><b>{state.charName || '이름 없음'}</b>{state.charLook ? ` · ${state.charLook}` : ''}</>
              : none}
          </Row>
          <Row label="소개">{state.storeDesc || none}</Row>
          {trendMeme && <Row label="트렌드"><b>{trendMeme.name}</b></Row>}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <SecondaryButton onClick={actions.goStore} style={smallButton}>가게 정보 보기</SecondaryButton>
          <SecondaryButton onClick={actions.myChar} style={smallButton}>캐릭터 보기</SecondaryButton>
        </div>
      </aside>
    </div>
  );
}

const smallButton = { height: 40, padding: '0 14px', fontSize: 14, borderRadius: 10 };
