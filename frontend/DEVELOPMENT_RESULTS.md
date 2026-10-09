# 프론트엔드 개선 실행 결과 (2026-10-09, 초기 단계 기록)

이 문서는 초기 41개 DOM 회귀 검증 시점의 기록입니다. 이후 인증·추천·브라우저·보안 의존성 수정과 최신 결과는 `../docs/completion-reverification.md`를 참고하십시오. 이전 단계 기록은 `../docs/project-completion-report.md`에 보존했습니다. 당시 axios 유지·실 Chromium 미검증 설명을 현재 최종 상태로 해석하지 마십시오.

## 완료한 범위

- **P0:** 서재, 검색, 최근 도서, 도서별 리뷰, 추천, 댓글을 실제 DOM 생성 + `textContent`로 렌더링한다. 기존 카드/표지/본문 CSS class와 HTML 레이아웃을 보존했다. 사용자 콘텐츠를 `innerHTML`/inline 이벤트에 넣지 않는다. 표지·외부 링크는 HTTP(S) scheme만 허용하고 제어문자/credentials URL을 차단한다. 링크에 `noopener noreferrer`를 지정하고 ISBN/리뷰 ID URL segment와 query 값을 인코딩한다.
- **P1 인증:** `scripts/api.js`의 공통 주소/인증 처리, access+refresh 저장, 동시 401 single-flight 갱신, 한 번 재시도, 만료/refresh 실패 시 로컬 정리, auth/common 로그아웃 handler 중복 제거. 로그아웃의 access 만료 시에도 갱신 후 최신 refresh를 폐기하고 실패하면 기기 세션을 정리하면서 서버 폐기 미확인을 안내한다.
- **P1 화면/계약:** query/q 검색 중복 요청 제거(입력은 양쪽 호환, 서버에는 query만 전송), 빈 서재 객체/배열과 없는 버튼 DOM 처리, nullable 본문/평점/날짜/도서 메타데이터 및 좋아요 0 표시. 공개 조회에는 Bearer null이나 만료 토큰을 보내지 않는다. JSON 프로필 endpoint를 이미지 URL로 사용하지 않고 허용된 기본 프로필 파일에 매핑한다. 누락 로그인/프로필 이미지 링크를 교정하고 실패 표지는 존재하는 로고로 대체한다.
- **P1 기능:** 서버 `is_liked` 및 기존 `/api/review/liked/` 응답 호환. 본인 댓글에만 수정/삭제 버튼을 표시하고 PATCH/DELETE `/api/review/{id}/comments/`의 `comment_id`/`content` 계약에 연결, 변경 후 재조회한다. 비밀번호 변경은 기존 `/api/user/update_profile/`에 `password`와 `current_password`를 전송하고 성공 후 재로그인을 요구한다. 계정복구 요청과 uid/token/new_password 확인 폼은 `/api/user/reset-password/`에 연결한다. 복구 URL query는 DOM에 읽은 뒤 주소창에서 제거하고 referrer를 차단한다.
- **P2:** main 최근 도서의 서버 최신순과 stable ISBN dedup을 유지한다. 목표 0·목표 초과값을 보존하고 월별 차트를 구현했다. 목표404와 무관하게 월별 데이터를 별도 요청한다. 두 요청에 **Asia/Seoul 현재 연도**를 명시한다. 사용자/리뷰 응답 debug log를 제거했다.

## 실제 검증 결과

| 실행 | 결과 | 범위 |
|---|---|---|
| 저장소 `npm test` (격리 설치한 jsdom 지정) | **41/41 PASS** | 이 작업의 실제 HTML/JS DOM 회귀 35개 + 목표 담당자의 회귀 6개. 네트워크와 Chart는 fixture/stub |
| 신규 scratch 복사본 `npm ci --ignore-scripts --no-audit --no-fund && npm test` | **41/41 PASS** | 의존성/lockfile 재현. 원본 tracked node_modules는 설치/교체하지 않음 |
| `.venv-runtime/bin/python -B frontend/tests/verify_backend_contract.py` | **1/1 PASS**, Django check 오류0 | 실제 Django URLconf, APIClient, JWT 로그인→refresh→me→logout→blacklist. in-memory 테스트 DB와 합성 자격정보 사용 |
| `npm start` 후 정적 HTTP 요청 | **17/17 HTTP 200** | HTML 13개, api/security JS, 로고/기본 프로필 이미지 |
| `node --check` | **17/17 PASS** | 현재 모든 프론트 스크립트 문법 |
| `git diff --check -- frontend` | PASS | whitespace 검사 |
| 데이터/의존성/스타일 보존 | PASS | 원본 DB SHA-256 baseline 일치, 기존 runtime lock 버전 변화0, tracked node_modules/CSS diff0 |

**중요한 발견:** 초기 mock의 refresh 경로가 실제 root URLconf와 달랐다. canonical 경로는 **`/api/auth/token/refresh/`**다. 실제 Django 회귀를 추가하여 잘못된 경로의 HTTP404(기대400) RED를 확인하고 프론트 경로 수정 후 실제 토큰 갱신·폐기까지 GREEN을 확인했다. 별칭을 추가하거나 기존 백엔드 경로를 바꾸지 않았다.

## 파일과 실행 방법

- 신규: `scripts/security.js`, `scripts/api.js`, `tests/dom.test.cjs`, `tests/verify_backend_contract.py`, 이 결과 문서.
- 수정: `package.json`/`package-lock.json`, 화면 HTML 공통 script include 및 최소 링크/복구/현재 비밀번호 필드, 기존 페이지 JS 13개. `goals.js`와 `mypage.js`의 목표 로직은 목표 담당자가 변경했다. 이 작업은 해당 로직을 덮어쓰지 않았다.
- 신규 npm 의존성은 **devDependencies의 `jsdom: 26.1.0` 하나**다. 기존 axios 및 기존 runtime transitive 버전은 유지했다. npm 설치의 whatwg-encoding deprecation 경고는 dev 도구의 전이 의존성 경고이며 테스트 실패는 아니다.
- 일반 재현: `cd frontend && npm ci && npm test`. 원본 tracked node_modules 보존이 필요하면 frontend를 scratch로 복사하여 해당 복사본에서 실행한다.
- 정적 실행: `cd frontend && npm start`, `/screen/main.html` 열기. 기본 port5500/bind127.0.0.1.
- API 주소: page script 전에 `window.DADOK_API_BASE_URL` 또는 `<meta name="api-base-url" content="...">` 설정. 미설정 시 로컬 호스트는 개발 API port8000, 그 외는 same-origin을 사용한다.
- 실제 백엔드 계약 재현: 프로젝트 루트에서 `.venv-runtime/bin/python -B frontend/tests/verify_backend_contract.py`.

## RED→GREEN 로그

전체 로그 디렉터리: `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-development/frontend/`

- `P0-library-RED.log` / `P0-library-GREEN.log`
- `P0-screens-RED.log` / `P0-screens-GREEN.log`
- `P0-images-RED.log` / `P0-images-GREEN.log`
- `P1-auth-RED.log` / `P1-auth-GREEN.log`
- `P1-contracts-RED.log` / `P1-contracts-GREEN.log`
- `P1-actions-RED.log` / `P1-actions-GREEN.log`
- `P2-main-RED.log` / `P2-main-GREEN.log`
- 추가 RED: `P1-public-RED.log`, `P1-year-RED.log`, `P1-logout-expired-RED.log`, `P1-refresh-route-RED.log`, `P1-missing-refresh-RED.log`, `P1-null-display-RED.log`, `P1-null-date-RED.log`, `P1-main-timezone-RED.log`. 이후 최종 GREEN은 `final-node.log`/`fresh-npm-ci-test.log`에 보존했다.
- 실제 Django 경로: `P1-real-refresh-route-RED.log` / `P1-real-refresh-route-GREEN.log`.
- 정적/보존: `static-smoke.json`, `final-verification.json`.

## 검증 한계

jsdom 검증은 실제 DOM parser와 이벤트를 사용하는 자동 회귀이며, 실제 Chromium의 레이아웃/반응형/CDN Chart 렌더링 E2E는 아니다. 외부 네이버 성공, 실제 메일 전달, 운영 배포/TLS, 운영 키 교체는 검증하거나 실행하지 않았다. 이 작업의 실제 Django 테스트는 인증 경로 계약만 검증하며 전체 리뷰/복구/목표 서버 통합 결과는 각 백엔드 담당자의 테스트 및 부모 통합 검증과 구분해야 한다. 운영 키/원본 DB/외부 도서 API를 사용하지 않았다.
