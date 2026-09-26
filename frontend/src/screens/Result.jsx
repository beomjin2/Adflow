import { useEffect, useState } from 'react';
import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import { buildAdText, adTextForClipboard, copyToClipboard, characterImage } from '../lib/adText.js';
import { downloadImages, downloadPoster } from '../lib/download.js';
import { StoryboardAPI } from '../api/client.js';
import ComicPanels from '../components/ComicPanels.jsx';

export default function Result({ state, actions }) {
  const { headline, lines, info, tags, caption, empty } = buildAdText(state);
  const charImg = characterImage(state);
  const hasImages = (state.comicCuts || []).some((c) => c.status === 'done');

  const copy = async () => {
    const text = adTextForClipboard(state);
    if (!text) { actions.toast('복사할 캡션이 없어요'); return; }
    const ok = await copyToClipboard(text);
    actions.toast(ok ? '캡션을 복사했어요' : '복사가 안 돼요 — 아래 캡션을 길게 눌러 직접 복사해주세요');
  };

  // 인스타 연결 상태 — 토큰이 없거나 만료면 버튼 자체를 안 보여준다(게시는 되돌릴 수 없다).
  const [ig, setIg] = useState(null);       // null=확인 중, {connected, username, reason}
  const [igAsk, setIgAsk] = useState(false); // 확인 창 열림
  const [igBusy, setIgBusy] = useState(false);
  const [igDone, setIgDone] = useState(null); // {permalink}

  useEffect(() => {
    let alive = true;
    StoryboardAPI.instagramStatus()
      .then((r) => { if (alive) setIg(r); })
      .catch(() => { if (alive) setIg({ connected: false, reason: '' }); });
    return () => { alive = false; };
  }, []);

  const publishInstagram = async () => {
    setIgBusy(true);
    try {
      const r = await StoryboardAPI.publishInstagram(adTextForClipboard(state) || caption || '');
      setIgDone(r);
      setIgAsk(false);
      actions.toast('인스타그램에 올렸어요');
    } catch (e) {
      actions.toast(String(e?.message || e) || '인스타그램에 올리지 못했어요');
    } finally {
      setIgBusy(false);
    }
  };
  const saveImages = async () => {
    // 말풍선까지 구운 완성본 한 장을 먼저 받는다 — 화면의 말풍선은 CSS 레이어라
    // 원본 넉 장을 그대로 받으면 대사가 통째로 사라진다.
    try {
      const { image } = await StoryboardAPI.poster();
      await downloadPoster(image, state.charName);
      actions.toast('말풍선까지 들어간 완성본을 받았어요');
      return;
    } catch (e) {
      // 합성이 안 되면(폰트 없음·파일 유실 등) 적어도 그림은 건지게 원본으로 되돌아간다.
      actions.toast('완성본을 못 만들어서 그림만 받을게요');
    }
    const ok = await downloadImages(state.comicCuts, state.charName);
    if (!ok) actions.toast('받을 그림이 없어요');
  };

  if (empty) {
    return (
      <div style={{ padding: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
        <span style={{ fontSize: 15, color: colors.textFaint, textAlign: 'center', lineHeight: '23px' }}>
          아직 정해진 내용이 없어요.<br />대화로 알리고 싶은 내용을 먼저 정해주세요.
        </span>
        <SecondaryButton onClick={actions.backToSb} style={{ minWidth: 200 }}>대화로 돌아가기</SecondaryButton>
      </div>
    );
  }

  return (
    <div style={{ padding: 22, display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      {/* 컷 구성 — 사장님이 정한 문장 그대로. 네컷 그림은 스토리보드에서 "네컷 그리기"를 눌렀을 때만 생긴다.
          카드 전체(그림+문장)에 최대 폭을 걸어 — 그림만 좁히면 카드는 넓고 그림만 좁은 비대칭이
          된다. 카드째로 좁혀야 안의 그림도 그 폭에 맞춰 같이 줄어든다. */}
      <div style={{ flex: '1 1 340px', maxWidth: 420, minWidth: 0, border: `1px solid ${colors.cardBorder}`, borderRadius: 18, background: '#fff', overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: `1px solid ${colors.cardBorder}`, display: 'flex', alignItems: 'center', gap: 10 }}>
          {charImg && (
            <img src={charImg} alt={state.charName || '가게 캐릭터'} style={{
              width: 44, height: 44, borderRadius: 11, objectFit: 'cover', flex: 'none',
              border: `1px solid ${colors.cardBorder}`,
            }} />
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <span style={{ fontSize: 14, fontWeight: 700 }}>{state.charName || '우리 가게'}</span>
            <span style={{ fontSize: 12, color: colors.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {state.adType || '광고'}{state.adConcept ? ` · ${state.adConcept}` : ''}
            </span>
          </div>
        </div>
        {(state.comicCuts || []).some((c) => c.status !== 'empty') && (
          <div style={{ padding: '12px 12px 0' }}>
            {/* 완성된 광고를 보는 화면이다 — 컷을 다시 그리려면 "대화로 돌아가 고치기"로
                가야 한다. 여기서 1컷씩 바꾸면 그 자리에서 문구와 그림이 어긋난다. */}
            <ComicPanels cuts={state.comicCuts || []} eta={state.sbEta} onReroll={actions.rerollCut} />
          </div>
        )}
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {state.plan.map((c) => (
            <div key={c.n} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{
                fontSize: 12, fontWeight: 800, color: colors.primarySoftText, background: colors.primarySoft,
                borderRadius: 7, padding: '4px 8px', flex: 'none',
              }}>{c.n}컷</span>
              <span style={{ fontSize: 15, lineHeight: '23px', color: colors.text }}>{c.line}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: '1 1 280px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ background: colors.bg, borderRadius: 16, padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint, letterSpacing: .4 }}>SNS 캡션</span>
          {caption ? (
            // GPT가 확정된 컷으로 새로 쓴 캡션 — 이모지·줄바꿈·해시태그가 이미 한 덩어리
            // 글로 들어 있어서, headline/lines/info/tags로 쪼개지 않고 그대로 보여준다.
            // 해시태그만 옛 문구 카드처럼 초록색으로 눈에 띄게 한다.
            <span style={{ fontSize: 15, lineHeight: '23px', color: colors.text, whiteSpace: 'pre-line' }}>
              {caption.split(/(\s+)/).map((part, i) => (
                /^#\S+$/.test(part)
                  ? <span key={i} style={{ color: colors.primarySoftText, fontWeight: 600 }}>{part}</span>
                  : part
              ))}
            </span>
          ) : (
            <>
              {headline && (
                <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: -.3, lineHeight: '27px' }}>{headline}</span>
              )}
              {lines.length > 1 && (
                <span style={{ fontSize: 15, lineHeight: '23px', color: colors.textSub, whiteSpace: 'pre-line' }}>
                  {lines.slice(1).join('\n')}
                </span>
              )}
              {info && <span style={{ fontSize: 14, lineHeight: '21px', color: colors.textSub }}>{info}</span>}
              {tags.length > 0 && (
                <span style={{ fontSize: 14, fontWeight: 600, color: colors.primarySoftText }}>{tags.join(' ')}</span>
              )}
            </>
          )}
          <span style={{ fontSize: 11.5, lineHeight: '16px', color: colors.textFaint }}>
            AI가 만든 내용이에요 — GPT도 실수할 수 있으니 올리기 전에 한 번 확인해주세요.
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <SoftButton onClick={copy} style={{ height: 48, fontSize: 15, flex: 1 }}>캡션 복사하기</SoftButton>
          {hasImages && (
            <SoftButton onClick={saveImages} style={{ height: 48, fontSize: 15, flex: 1 }}>이미지 저장</SoftButton>
          )}
        </div>
        {/* 인스타 게시 — 연결돼 있고 그림이 있을 때만. 누르면 바로 올라가지 않고 확인 창을 거친다. */}
        {hasImages && ig?.connected && !igDone && (
          <SoftButton onClick={() => setIgAsk(true)} style={{ height: 48, fontSize: 15 }}>
            인스타에 올리기
          </SoftButton>
        )}
        {/* 연결 전이면 안내 화면으로 보낸다 — 버튼만 숨기면 왜 없는지 알 수가 없다. */}
        {hasImages && ig && !ig.connected && (
          <SoftButton onClick={actions.goInstagram} style={{ height: 48, fontSize: 15 }}>
            인스타에 바로 올리려면 계정 연결하기
          </SoftButton>
        )}
        {igDone && (
          <a href={igDone.permalink || '#'} target="_blank" rel="noreferrer"
             style={{ fontSize: 14, fontWeight: 700, color: colors.primaryHover, textDecoration: 'none', padding: '4px 2px' }}>
            인스타그램에 올렸어요 — 게시물 보기 →
          </a>
        )}
        <SecondaryButton onClick={actions.backToSb} style={{ height: 52, fontSize: 16 }}>대화로 돌아가 고치기</SecondaryButton>
        {/* 보관함에서 옛 항목을 보는 중이면 이미 저장된 것이라 또 저장할 필요가 없다 — 중복 저장 방지. */}
        {!state.viewingHistory && (
          <PrimaryButton onClick={actions.download} disabled={state.savedThisAd}>
            {state.savedThisAd ? '보관함에 저장했어요' : '보관함에 저장'}
          </PrimaryButton>
        )}
        <SecondaryButton onClick={actions.goHome}>홈으로</SecondaryButton>
      </div>

      {/* 올리기 전 확인 — 게시는 인스타그램 앱에서만 지울 수 있어서, 한 번 더 묻는다. */}
      {igAsk && (
        <div onClick={() => !igBusy && setIgAsk(false)} style={{
          position: 'fixed', inset: 0, background: 'rgba(15,17,19,.66)', zIndex: 120,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          backdropFilter: 'blur(3px)', WebkitBackdropFilter: 'blur(3px)',
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: '100%', maxWidth: 380, background: '#fff', borderRadius: 18, padding: 22,
            display: 'flex', flexDirection: 'column', gap: 12, maxHeight: '82vh', overflowY: 'auto',
            boxShadow: '0 24px 60px rgba(0,0,0,.34)',
          }}>
            <span style={{ fontSize: 17, fontWeight: 800 }}>이 내용으로 올릴까요?</span>
            <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub }}>
              {ig?.username ? `@${ig.username} 계정에 바로 게시됩니다. ` : '연결된 계정에 바로 게시됩니다. '}
              올린 뒤에는 인스타그램 앱에서만 지울 수 있어요.
            </span>
            <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub, background: colors.softBg,
                           borderRadius: 10, padding: '10px 12px', whiteSpace: 'pre-line' }}>
              {adTextForClipboard(state) || caption || '(캡션 없음)'}
            </span>
            <PrimaryButton onClick={publishInstagram} disabled={igBusy} style={{ height: 46 }}>
              {igBusy ? '올리는 중이에요… (10초쯤 걸려요)' : '올리기'}
            </PrimaryButton>
            <SecondaryButton onClick={() => setIgAsk(false)} disabled={igBusy} style={{ height: 44 }}>취소</SecondaryButton>
          </div>
        </div>
      )}
    </div>
  );
}
