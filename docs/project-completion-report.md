# 다독다독 프로젝트 개발 완료 검증 보고서

기준 감사: `PROJECT_AUDIT_2026-10-09.md`. 검증 날짜: 2026-10-09 (KST).

## 현재 재검증 안내

2026-10-09의 후속 검증에서 기존 미완료 세션 회귀와 추가 공개 인증/서버 quota·unique 경쟁 결함을 수정했다. 현재 부모 결합 실행은 backend139/frontend112/실제 HTTP Chromium33/native 세션9개 모두 PASS다. 수정 후 독립 frontend/backend 재리뷰도 PASS이며 부모가 현재 reviewed source hash 일치를 확인했다. 로컬 코드 검증은 완료했고 운영 출시·별도 승인 사항은 남아 있다. 최신 완료 여부·수정 내역·실제 로그·승인 경계는 `completion-reverification.md`를 따른다. 이번 요청에서는 commit/push나 운영 배포를 하지 않았다.

아래는 이전 작업 종료 시점의 기록이며, 진행 중/미완료·과거 테스트 수를 최신 상태로 해석하지 않는다. 기존 감사와 실패 기록은 역사적 증거로 보존한다.

## 1. 이전 작업 종료 시 판정 — 최종 게이트 진행 중

기존 HTML/CSS/Vanilla JavaScript + Django/DRF 프로젝트에서 아래 P0/P1/P2 구현과 회귀를 수행했다. 이전 지원환경 Chromium33개/npm75개 통과와 별개로 추가 독립 리뷰에서 세션 race4건과 year1 목표 오류1건을 재현해 승인 불가 판정을 받았다. year1을 수정해 backend 한정 독립 재리뷰는 PASS했다. 세션 race 수정 및 그 독립 재리뷰는 진행 중이며 아직 전체 완료·commit·push를 선언하지 않는다.

원본 DB·기존 사용자 데이터·기존 CSS·감사 보고서는 보존했다. 새 프로젝트 재구축, 프레임워크 전환, 실제 서비스 배포, 운영 DB 적용, 키 교체, Git history rewrite, 실메일·실네이버 요청은 하지 않았다.

프로젝트의 비추적 `.venv-dev`를 새로 구성하여 현재13개 pin을 설치했고 pip check/지원gate4개/전체backend123개를 통과했다. 실제 frontend75개도 이 새 환경의 URLconf 자동 발견으로 확인했다. 기존 `.venv-runtime`은 비교용으로 그대로 남겼다. 프론트 테스트 도구는 원래 node_modules를 보존하기 위해 격리 설치를 사용했으며 일반 새 checkout은 README의 npm ci로 재현한다.

## 2. P0 보안 수정

- 리뷰/댓글 수정·삭제의 서버 작성자 권한을 검사하고 타 사용자 변경을 거절한다. 프론트 버튼 숨김만으로 권한을 대신하지 않는다.
- 검색·도서·리뷰·댓글·닉네임·추천은 안전한 DOM 생성과 textContent로 표시한다. 위험 URL scheme, 제어문자, URL credentials를 거부하며 경로 segment를 인코딩한다.
- 공개 프로필/리뷰/댓글에서 이메일을 제거했다. 프로필 이미지는 읽기 전용 allowlist 값으로 응답하고 legacy 값은 저장 데이터 변경 없이 기본 이미지로 표시한다.
- Django/JWT/Naver 자격정보를 환경변수로 분리했다. 개발의 비추적 로컬 자격정보 파일은 보존하고 운영에서 읽지 않는다.
- 운영은 host/키를 명시하고 SMTP backend 외 console/file/dummy/locmem을 기동 시 거절한다. 복구 토큰·SMTP 자격정보 원문을 응답/오류 로그에 남기지 않는다.
- 로그인 URL 두 종류에서 같은 충돌 판정·정규화·identity throttle을 적용한다. 공개 검색/ISBN/추천은 같은 IP quota를 공유하고 위조 X-Forwarded-For로 우회되지 않는다.
- DB/node_modules/bytecode 등 320개는 Git index에서만 제거했다. 로컬 파일은 모두 존재하며 DB·키·가상환경·생성 파일 ignore 회귀를 추가했다.
- Django 5.2.18 / DRF 3.17.2 및 호환 보안 pin을 적용했다. app 13개는 설치 graph/fresh resolver와 전부 일치하며 PyPI·OSV audit의 알려진 advisory는 각각 0이다. frontend axios는 1.20.0으로 고정하고 현재 lock의 npm audit도 0이다.

## 3. P1 기능 및 연결 수정

- 가입·아이디/이메일 로그인·NFKC 정규화·중복/충돌 처리를 검증했다. 의도된 비밀번호 앞뒤 공백은 가입과 로그인에서 같은 값으로 유지한다.
- access/refresh 저장, 동시 401 single-flight 갱신, 한 번 재시도, refresh 실패 시 세션 정리, 중복 로그아웃 handler 제거를 구현했다.
- 로그아웃·비밀번호 변경·복구 성공에서 refresh 폐기를 확인했다. 계정 복구는 등록 여부를 노출하지 않는 응답, 만료·1회성 링크, 새 비밀번호 검증을 사용한다.
- 프로필 초기 조회 실패/조회 중 쓰기와 중복 저장을 차단한다. 리뷰 수정의 초기 조회 실패도 PUT을 차단하여 기존 이미지/평점을 덮지 않는다.
- Naver 공유 service를 사용해 검색 query/q 호환, query/display/start bounds, 정확한 ISBN10/13 checksum, timeout 및 안전한 502/504, 정상 빈 검색과 ISBN 미발견을 구분한다.
- 리뷰 CRUD·서재·좋아요·댓글 CRUD를 실제 API/회귀로 검증했다. 익명 상세의 false 좋아요가 로그인 사용자의 저장 상태를 덮지 않도록 인증 liked 조회로 확인한다.
- 외부 검색된 미등록 도서의 공개 리뷰 목록은 정상 200/[]이며 신규 저장 도서의 Naver link를 보존한다.
- 공통 API 주소/인증 helper, nullable 필드·0·빈 화면 처리, 기본 이미지 경로와 화면 링크를 정리했다.

## 4. P2 목표·추천

- 목표에 nullable year/month와 범위별 uniqueness를 추가했다. 기존 무기간 목표를 올해 목표로 변환하지 않고 원본 데이터/기존 API 응답 키를 보존했다.
- 연간·월간 기간 생성/수정/진행률과 서울 시간대 리뷰 created_at 기준 통계를 연결했다. 실제 완독일이나 재독 횟수를 추측하지 않는다. 연도 999의 0999 월별 키도 회귀로 검증했다.
- year1의 ORM UTC 범위 underflow로 조회500 및 생성후응답500이 발생하던 결함을 명시 서울 연도 추출 필터로 수정했다. 1~9999 계약을 축소하지 않았고 실제 year1 합성 기록도 집계한다. 활성 timezone이UTC여도 서울 경계와 일치하는 회귀를 추가했다.
- shared 요청 제한의 설정키를 `book`으로 맞추고 기존 `books`만 설정한 경우 fallback을 지원한다. `book` 명시값이 우선하며 기본60/min과 cross-endpoint 제한은 유지한다.
- 기존 공개 Naver 관련추천 API의 배열/키/query/isbn 호환성을 보존하며 현재 도서·ISBN alias 중복을 제외한다. metadata가 없으면 명시 query로 fallback한다.
- additive 인증 개인화 API를 추가했다. 높은 평점의 작가/출판사 선호, 미독 후보, 현재 도서 제외, community cold-start 및 stable 동률 순서를 사용하는 작은 결정적 규칙이다. 민감 사용자 정보를 응답하지 않는다.
- 로그인 상세의 같은 추천 grid에서 개인화를 우선하고 후보 없음/오류 시 공개 관련추천으로 fallback한다. 익명은 기존 공개 흐름이다.
- 최근 도서는 ISBN 중복 제거 후 최신 10권, 각 도서 최신 리뷰 5개를 가져온다. fixture에서 query 수 25→3을 확인했다.
- 실제 Chart.js 4.5.1을 정확 URL과 SHA384 SRI로 고정했다. 브라우저는 실제 Chart bytes로 검증하며 fake Chart를 쓰지 않는다.
- 실제 브라우저에서 발견한 목표 제목/설명 겹침과 모바일 화면 넘침을 작은 normal-flow 및 additive CSS 보정으로 해결했다. 기존 CSS14개를 그대로 유지하고 컨트롤을 숨기지 않는다. clean clone의 DB 부재와 TMPDIR도 지원하도록 E2E 실행기를 보완했다.

## 5. 실제 실행 결과 — 현재 확인된 범위

서로 다른 scope/시점의 테스트를 합산해 한 E2E 총수로 주장하지 않는다.

| 검사 | 실제 결과 | 범위/한계 |
|---|---|---|
| Django 5.2.18 전체 suite | 130/130 PASS | 새calendar5/rate설정2 회귀 포함, in-memory test DB, Naver mock/locmem |
| Django check | 오류 0 | 지원 runtime |
| migration drift | No changes detected | --check --dry-run; 원본 DB migrate 아님 |
| 실제 frontend JWT 계약 | 1/1 PASS | login→refresh→me→logout→blacklist |
| 지원 버전 gate | 4/4 PASS | 날짜 고정 지원/보안 floor |
| root tooling regression | 7/7 PASS | 실행기 경로/하드링크 거절 및 Git hygiene |
| Python AST | 이전85개 PASS | 새 회귀/세션 수정 종료 후 최종 재실행 필요 |
| Node --check | 이전22개 PASS | 세션 수정 종료 후 최종 재실행 필요 |
| 새 격리 frontend npm ci / DOM suite | 수정 전75/75 PASS | 기존검사가 race를 놓침. 세션 수정 종료 후 새 회귀포함 최종 재실행 필요 |
| pip check / fresh resolver | PASS | app 13개 전체 pin 일치 |
| pip-audit PyPI / OSV | 각각 app13/advisory0/skipped0 | 알려진 취약점 DB 범위 |
| npm audit | advisory0 | 현재 frontend lock |
| check --deploy --fail-level WARNING | 오류/경고0 | synthetic 키/host, SMTP backend import만; 실제 전달 없음 |
| scripts/dev.py 실제 기동 | API/정적 화면 HTTP200 | 별도 DB, 직접 띄운 서버 종료 및 포트 폐쇄 |
| 원 DB 복사본 migration | 기존/지원 runtime PASS | 원본 테이블·행·키·필드·legacy NULL 및 무결성 보존 |
| 지원 Django 실제 Chromium E2E | 세션 수정 전33/33 PASS | Django5.2.18/Chromium153.0.8010.12; API153/캡처28/미처리JS오류0, race수정 후 재실행 필요 |
| DB 없는 clean clone E2E | 33/33 PASS | 기존 Django5.1.5 runtime; 원본 DB 부재 유지, TMPDIR 준수 |
| backend 추가 독립 재리뷰 | PASS | 전체130/check/drift, 새독립7개와갱신독립13개PASS, backend 한정 승인 |
| helper/session 추가 독립 리뷰 | FAIL·수정 중 | B1~B4 수정 후 독립 재리뷰 필요 |

지원 업데이트 최초 120개 suite 통과 뒤 동시 신규 회귀 2개가 구현 전에 실행되어 122개 중 2개 실패한 적이 있다. 당시 requirements 적용을 보류했다. 신규 도서 리뷰 계약 수정 이후 안정 코드에서 지원 runtime 123개 전체를 다시 통과하여 pin을 적용했다. 과거 subset 통과를 최종 결합 통과로 대체하지 않았다.

브라우저 레이아웃 RED31/2 → 목표 제목 수정32/1 → 모바일 보정33/0을 실제 실행했다. 이후 지원 Django5.2.18에서 부모가 33개 전체를 다시 실행했다. 모바일 캡처14개의 document width가 모두390px이고 목표 설명·제목이 분리되며 댓글 입력/수정/삭제가 보이는 것을 실제 캡처로 확인했다. 미처리 JS 오류0은 의도된 인증거부/네트워크 차단의 console error까지0이라는 뜻이 아니다.

## 6. 데이터 및 파일 보존

- 원본 `backend/db.sqlite3` SHA256은 baseline과 동일하고 파일을 삭제하지 않았다.
- 원본 DB·감사·기존 CSS14개, 총 16개 보호 파일 hash 모두 일치했다. 모바일 보정은 별도 CSS를 추가하는 방식이며 기존 CSS 원본을 덮지 않는다.
- 추가 보호 baseline의 기존 node_modules150개까지 포함한166개 hash 모두 일치하고 node_modules 파일 집합도 그대로임을 부모가 재확인했다. 설치는 scratch 복사본/격리 가상환경에서만 수행했다.
- index-only 제거 320개 로컬 파일 모두 존재한다. ignore/untrack는 과거 Git blob을 삭제하는 작업이 아니다.
- 원본 DB mode=ro backup의 별도 복사본에만 migrate했다. 원본 모든 행/키/원래 field 값, legacy 목표 NULL 및 integrity/foreign-key checks를 검증했다. 민감 row 값은 출력하지 않았다.

## 7. 남은 승인·운영 검증 경계

현재 코드 완료 blocker: 탭간 logout/계정전환 후 지연refresh가 세션을 복원·혼합하고 A폼을B로저장하는 문제(B1), 늦은 로그인/me 성공의 수락과 이전 이메일 렌더링(B2), 이전 retry401이 새 세션을 삭제(B3), 이전 logout401이 새 계정refresh/폐기를 수행(B4). 원본을 공격하지 않은 합성 DOM/nativeChromium으로 재현했다. 해당 수정/회귀와 독립 재리뷰를 마치기 전 commit/push를 보류한다. year1 blocker는 새5회귀/전체130PASS 및 backend 독립재리뷰PASS로 해소했다. 과거 독립13probes 중 이전 throttle 버그가 존재해야 한다는 assertion1개만 원본에서 실패했으며, scratch에서 해당 기대값만 수정한13개와 별도새7개 모두 통과했다. 이를 원본13개가 그대로 통과한 것으로 보고하지 않는다.

1. 공개 원격 Git 과거 이력에 credential literal을 포함한 settings blob과 DB 변경 이력이 남아 있다. 현재 source/index에서 제거해도 과거 노출은 해소되지 않는다. 키 교체·기존 세션 처리·history 정리는 별도 승인이 필요하고 이번에 하지 않는다.
2. 승인된 Naver/SMTP 테스트 자격정보로 실제 외부 서비스 성공을 검증하지 않았다. Naver 상류만 mock이며 메일은 locmem이다. 정상 외부 서비스 연결이나 실제 전달 성공으로 보고하지 않는다.
3. 비밀번호 변경/재설정은 기존 refresh를 폐기하지만 이미 발급된 access는 최대 기존 1시간 수명 동안 유효할 수 있다. 즉시 access/session 전체 폐기는 별도 정책/호환성 검토 대상이다.
4. 운영 HTTPS, trusted proxy, shared cache/다중 worker rate limit, static/media 제공, 백업·monitoring·부하 검증과 배포는 별도다. 이번 quota는 기본 local cache 기반 best-effort 제한이다.
5. 기존 원본 DB에는 새 migration을 적용하지 않았다. 복사본 성공은 원본 적용 승인이 아니다. 일반 로컬 실행은 분리 DB와 새 requirements 환경을 사용한다.
6. 추천은 규칙 기반·테스트 fixture로 검증했다. 실사용 품질/개인화 효과를 측정한 AI 서비스가 아니다. 외부 글꼴 차단 상태의 캡처는 fallback font를 쓸 수 있고 전체 접근성/픽셀 감사를 대체하지 않는다.

## 8. 변경 파일 및 Git 게이트

주요 변경은 backend의 user/review/book/goal/recommendation/settings/requirements, frontend screen/scripts/package/tests, 새 안전 실행기/root tests, README/environment/API/dependency/결과 문서다. 최종 변경 파일 전체 목록은 결합 게이트 뒤 이 섹션에 확정한다.

현재 브랜치는 master, 원격은 nemanic3/dadokdadok이다. 커밋 전 HEAD와 마지막 확인 원격 master는 `f094c504664a2c152dd8b4b13ab473be3e7d5292`로 동일했다. 현재 원격은 공개이며 활성 Actions는 Dependency Graph만 관측했다. push 직전에 원격 변경 여부를 다시 확인한다.

모든 필수 테스트·독립 리뷰·민감정보 게이트가 통과하기 전 commit/push는 보류한다. 원격 충돌/새 commit이 있으면 자동 rebase/force push하지 않는다. 최종 commit hash/push readback/Git 상태는 실제 수행 후 최종 응답에 기록한다.

## 9. 재현과 증거

설치/실행/테스트 명령은 root README, 설정은 `docs/environment.md`, API는 `docs/api.md`, 지원 업데이트는 `docs/dependency-upgrade.md`를 따른다.

private evidence root: `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-finalization/`

- `supported-parent-results.json`, `supported-app-graph.json`, `supported-dev-runner-results.json`, `syntax-results.json`
- `parent-audit-pypi.json`, `parent-audit-osv.json`, `npm-audit-final.json`
- `dependency-upgrade/migration-preservation-results.json`, `selected-release-evidence.json`, `installation-report.json`
- `repository-safety.json`, `parent-preservation-snapshot.json`, `final-review.json` 및 한국어 독립 리뷰
- `browser/latest-run.json`에 기록된 실제 실행의 results/report/screenshots
- 지원환경 최종 Chromium: `browser/run-cc7864e5920149e983e0a10b9f873f13/results.json`, `supported-chromium-final.log`
- `frontend-final.log`, `npm-ci-final.log`, `npm-final-audit.log`, `layout-fixes/RESULTS_KO.md` 및 원본166개 hash baseline
- 실제 프로젝트 새 `.venv-dev` 재검증: `persistent-runtime-backend.log` (123개), `persistent-runtime-frontend.log` (75개)
- 추가 독립 FAIL 증거: `combined-backend-review/final-review.json`, `combined-helper-review/verdict.json` 및각한국어보고서/반례로그
- 새calendar/rate 회귀 RED/GREEN: `calendar-boundaries-RED-full.log`, `calendar-boundaries-GREEN.log`, `book-rate-config-RED.log`, `book-rate-config-GREEN.log`, `calendar-rate-full-backend-GREEN.log` (130개)
- backend 독립 재리뷰 PASS: `calendar-final-review/final-review.json`, `final-review.ko.md`, `backend-tests.log`, `calendar-probes.log` 및SQL/보존증거

scratch는 정리될 수 있으며 원본 DB 복사본·상세 로그를 Git에 추가하지 않는다. 저장소 문서의 요약과 다시 실행 가능한 테스트가 재현 기준이다.
