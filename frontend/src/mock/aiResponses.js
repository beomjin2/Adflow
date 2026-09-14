// 지금은 모두 프론트엔드 mock (setTimeout + 랜덤). 나중에 FastAPI가 생기면
// 이 함수들의 내부만 실제 fetch 호출로 교체하면 된다. 시그니처는 유지할 것.
import { randomHue } from '../theme.js';

export const VIEW_LABELS = ['정면', '좌측면', '우측면', '뒷면'];

export const BASE_PLAN = [
  { n: 1, line: '캐릭터가 가게 문을 열며 손님에게 인사한다.', short: '인사' },
  { n: 2, line: '갓 구운 소금빵을 두 손으로 내밀며 소개한다.', short: '갓 구운 빵' },
  { n: 3, line: '한 입 베어 문 손님이 눈이 번쩍 뜨이는 리액션.', short: '리액션' },
  { n: 4, line: '가게 이름·위치·영업시간이 적힌 간판 컷으로 마무리.', short: '마무리' }
];

export const TRENDS = ['눈이 번쩍 챌린지', '소금빵 대유행', '퇴근길 빵 한 봉지', '사장님 브이로그'];

export const TREND_DETAIL = [
  {
    name: '눈이 번쩍 챌린지', delta: '+312%',
    summary: '한 입 먹고 과장되게 놀라는 리액션 밈. 베이커리·디저트 업종에서 가장 많이 쓰이고, 네컷만화 3컷째에 넣기 좋아요.',
    stats: [{ k: '게시물', v: '12.4만' }, { k: '평균 저장률', v: '8.1%' }, { k: '상승 주차', v: '2주째' }],
    links: [
      { title: '#눈이번쩍챌린지 인스타 릴스 모음', meta: '게시물 12.4만' },
      { title: '빵집 업종 활용 사례 10선', meta: '블로그' },
      { title: '따라 하기 쉬운 구도 3가지', meta: '가이드' }
    ]
  },
  {
    name: '소금빵 대유행', delta: '+186%',
    summary: '겉은 바삭, 속은 버터로 촉촉한 소금빵이 전방위로 확산 중. 갓 구운 시간대를 함께 알리면 반응이 좋아요.',
    stats: [{ k: '검색량', v: '7.8만' }, { k: '연관 품목', v: '소금빵·크루아상' }, { k: '상승 주차', v: '5주째' }],
    links: [
      { title: '소금빵 판매 상승 리포트', meta: '리포트' },
      { title: '#소금빵 인기 게시물', meta: '게시물 4.6만' },
      { title: '갓 구운 빵 사진 잘 찍는 법', meta: '가이드' }
    ]
  },
  {
    name: '퇴근길 빵 한 봉지', delta: '+94%',
    summary: '저녁 6–8시 마감 세일을 노리는 시간대 타깃 문구. 영업시간과 남은 수량을 강조하는 마지막 컷과 궁합이 좋아요.',
    stats: [{ k: '피크 시간', v: '18–20시' }, { k: '게시물', v: '2.9만' }, { k: '상승 주차', v: '3주째' }],
    links: [
      { title: '저녁 시간대 광고 성과 비교', meta: '리포트' },
      { title: '#퇴근길빵 태그 모음', meta: '게시물 2.9만' },
      { title: '야간 조명 사진 톤 맞추기', meta: '가이드' }
    ]
  },
  {
    name: '사장님 브이로그', delta: '+61%',
    summary: '사장이 직접 등장해 새벽 반죽·굽는 과정을 보여주는 형식. 마스코트 캐릭터를 사장 역할로 세우면 그대로 적용돼요.',
    stats: [{ k: '평균 조회', v: '1.2만' }, { k: '완주율', v: '54%' }, { k: '상승 주차', v: '1주째' }],
    links: [
      { title: '동네 가게 브이로그 인기 포맷', meta: '블로그' },
      { title: '#사장님브이로그 최신 게시물', meta: '게시물 1.7만' },
      { title: '캐릭터로 대체해 만든 사례', meta: '사례' }
    ]
  },
  {
    name: '가을 신메뉴', delta: '+38%',
    summary: '계절 한정 키워드. 밤·고구마 빵류와 잘 붙고 9–11월 내내 유지되어 오래 쓰기 좋아요.',
    stats: [{ k: '유지 기간', v: '9–11월' }, { k: '게시물', v: '9.3만' }, { k: '경쟁도', v: '높음' }],
    links: [
      { title: '가을 한정 메뉴 키워드 분석', meta: '리포트' },
      { title: '#가을신메뉴 인기 게시물', meta: '게시물 9.3만' },
      { title: '계절 컬러 팔레트 참고', meta: '가이드' }
    ]
  }
];

export function generateCandidates(count = 3) {
  return Array.from({ length: count }, (_, i) => ({ label: `후보${i + 1}`, hue: randomHue() }));
}

export function generateViews() {
  return VIEW_LABELS.map(label => ({ label, hue: randomHue() }));
}

export function itemFrom(text) {
  const t = text || '';
  const m = t.match(/([가-힣a-zA-Z0-9]+(?:빵|크루아상|캄파뉴|케이크|쿠키|타르트))/);
  return m ? m[1] : '신메뉴';
}

export function qtyFrom(text) {
  const m = (text || '').match(/(\d+)\s*개/);
  return m ? `${m[1]}개` : '';
}

const pad2 = n => String(n).padStart(2, '0');
export const isoDay = (dayOffset = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + dayOffset);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
};
export const fmtDay = (iso) => {
  const p = (iso || '').split('-');
  return p.length === 3 ? `${Number(p[1])}/${Number(p[2])}` : (iso || '');
};
export const nowHM = () => {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
};
export const dayFrom = (text) => {
  const t = text || '';
  if (/그저께|그제/.test(t)) return isoDay(-2);
  if (/어제/.test(t)) return isoDay(-1);
  const m = t.match(/(\d{1,2})\s*[/\-월.]\s*(\d{1,2})/);
  if (m) {
    const d = new Date();
    return `${d.getFullYear()}-${pad2(Number(m[1]))}-${pad2(Number(m[2]))}`;
  }
  return isoDay(0);
};
export const timeFrom = (text) => {
  const m = (text || '').match(/(\d{1,2})\s*(?::|시)\s*(\d{1,2})?/);
  if (!m) return nowHM();
  return `${pad2(Number(m[1]))}:${pad2(Number(m[2] || 0))}`;
};
