# 인스타그램 연결 안내 화면 그림

`InstagramSetup.jsx` 의 단계마다 이 폴더의 png 를 순서대로 보여준다.
파일 이름이 곧 붙는 자리다(`shots: [{ f: 's3a_addall' }]` → `s3a_addall.png`).
파일이 없으면 그 자리만 조용히 비고, 안내 문구는 그대로 나온다.

2026-09-27 새 계정(adflow.bakery)으로 처음부터 끝까지 다시 밟으며 찍었다.
빨간 네모는 눌러야 할 곳이다.

| 파일 | 화면 |
|---|---|
| s1a0_home | 인스타 로그인 직후 홈 — 더 보기 → 설정 🔴 |
| s1a_settings | 인스타 설정 — 계정 유형 및 도구 🔴 |
| s1b0_convert | 계정 유형 및 도구 — 프로페셔널 계정으로 전환 🔴 |
| s1b_business | 크리에이터 / 비즈니스 중 비즈니스 |
| s1c_category | 카테고리 선택 |
| s1d0_confirm | 전환하시겠어요? → 계속하기 🔴 |
| s1d_done | "이제 Instagram Business 계정을 사용할 수 있습니다" |
| s2a_myapps | 내 앱 → 앱 만들기 |
| s2b_appname | 앱 상세 정보(앱 이름·연락처) |
| s2c_filter | 이용 사례 — 왼쪽 "콘텐츠 관리" 필터 |
| s2d_usecase | "Instagram에서 메시지 및 콘텐츠 관리" 선택 |
| s2e_portfolio | 비즈니스 포트폴리오(없어도 됨) |
| s2f_req | 요구 사항 → 다음 🔴 |
| s2g_overview | 개요 — 입력값 확인 (이메일 모자이크) |
| s2h_create | 개요 아래 — 앱 만들기 🔴 (이메일 모자이크) |
| s2i_password | 페이스북 비밀번호 재확인 → 제출 🔴 (이름·이메일 모자이크) |
| s2j_dashboard | 앱 대시보드 — 생성 완료 |
| s3a_addall | Add all required permissions 버튼 🔴 |
| s3b_publish | instagram_business_content_publish 추가 🔴 |
| s3c_error | "문제가 발생했습니다" 오류 |
| s3d_ready | 상태가 "테스트 준비 완료" |
| s4a_tester | Instagram 테스터 — 드롭다운 프로필 선택 🔴 |
| s4b_accept | 인스타 앱 및 웹사이트 → 테스터 초대 수락 🔴 |
| s5a_gentoken | 액세스 토큰 설정 — 계정 옆 "토큰 생성" |
| s5b_consent | 권한 동의 화면 → 허용 🔴 |
| s5c_token | 토큰 생성됨 — 이해합니다 체크 → 복사 🔴 |

## 다시 찍을 때
- 브라우저 창 전체로 찍는다(주소창이 보여야 사장님이 어디인지 안다).
- 윈도우 작업 표시줄은 잘라낸다. 가로 1200px 로 줄여 저장한다.
- **개인정보는 모자이크한다.** 앱 연락처 이메일, 페이스북 계정 이름처럼 화면에 남는 값들.
- **토큰·앱 시크릿 코드가 보이는 컷은 넣지 않는다.** s5c 는 "이해합니다" 체크 전이라
  토큰이 점으로 가려진 상태다.
