# 검증된 변경의 커밋 범위와 기존 작업 구분

기준일: 2026-10-09. 기준 HEAD: `f094c504664a2c152dd8b4b13ab473be3e7d5292`, 브랜치: `master`, 원격: `origin` (`nemanic3/dadokdadok`).

## 범위 판정

- 이전 재검증 시작 전에 존재한 관련 미커밋 작업87개, 그 재검증에서 수정15개/신규4개인19개를 구분했다. 합계106개 소스·설정·테스트·문서가 검증된 기능의 재현 범위다.
- 마지막19개만 커밋하면 공통 SafeDOM/API, permission/profile/security/throttle, HTML 연결, 목표 migration, dependency pin 및 전체 회귀가 빠진다. 독립 범위 감사에서 기존87개는 관련 의존 작업 또는 보존된 감사/재현 문서이며 무관한 소스 변경은 발견하지 않았다.
- 이번 커밋·출시 준비 요청에서 새로 추가한 파일은 이 문서와 `release-runbook.md`, `release-environment.example`3개다. README에는 문서 안내와 API base 보안 설명 정정을 추가했고, 기존 `docs/environment.md`도 동일한 보안 설명을 정정했다. 독립 문서 리뷰에서 API base와 frontend origin의 구분 및 운영 media alias 누락을 발견해 소스 변경 없이 바로잡았다. 과거 테스트가 이 신규 문서를 검증했다고 주장하지 않는다.
- 기존 index의 추적 해제320개는 DB1개·node_modules150개·bytecode169개다. 로컬 파일 삭제가 아니라 새 Git tree에서만 제외한다. 이는 repository safety 회귀에 필요한 기존 관련 작업이다.
- 커밋은 저장소 위생(기존 추적 해제와 `.gitignore`)과 검증된 플랫폼 완성/출시 준비로 나눈다. 실행 코드와 필수 테스트/설정/문서는 서로 빠뜨리지 않고 같은 완성 commit에 담는다.

## 보안과 보존

실제 자격정보 파일·`.env`·원본 DB bytes·로그·node_modules·venv·bytecode를 새 blob으로 추가하지 않는다. `.env.example`과 `release-environment.example`은 비밀값이 없는 변수 참고 템플릿으로만 포함한다. migration 파일 추가는 원본 DB 적용이 아니다.

비추적 개발 credential과 기존 HEAD의 credential-named literal은 메모리에서 후보 파일과 비교하고 값은 출력/로그로 남기지 않았다. 알려진 token/private-key/URL-credential 패턴과 literal 위치를 검사했다. 유일한 URL-credential 발견은 예약 example.test URL을 거절하는 기존 DOM 회귀 fixture로, 정확한 fingerprint에 한해 제외한다. 테스트의 합성 password/key, HTML input attribute, serializer/recovery field 이름과 문서의 placeholder를 실제 비밀값과 구분한다. 이 검사는 전 세계의 모든 비밀정보 패턴 부재를 보장하지 않는다.

원본 DB·기존 CSS·node_modules 등 보호167개 SHA256이 기존 기록과 일치한다. 기존 작업을 stash/reset/삭제/자동 되돌리기 하지 않는다. 기존 감사 `PROJECT_AUDIT_2026-10-09.md`와 원칙은 현재 bytes로 보존한다. 추적 해제는 과거 Git 이력의 노출을 제거하지 않는다. 키 교체·Git 이력 정리·운영 배포·원본 migration은 이번 요청에서 실행하지 않는다.

## 검증 기준

실행 코드의 SHA256은 baseline 및 수정 후 frontend18/backend25 reviewed manifest와 일치한다(겹치는4개를 제외하면39개). 문서 정리 외 설명되지 않는 실행 drift는 없으며 기존139 backend/112 frontend/33 HTTP Chromium/9 native 결과는 재사용할 수 있다. 마지막19개만 또는 일부 의존성이 누락된 tree에는 이 결과를 적용하지 않는다.

최종 candidate는 승인 경로만 담은 별도 index/tree로 만들고 clean snapshot에 export한다. exact blob hash·추가/삭제 경로·sensitive artifact 부재·`git diff --cached --check`를 확인한다. clean snapshot의 fresh frontend `npm ci`, Django 전체/contract/root/dependency 검증과 HTTP/native 실행 결과를 확인한 뒤 커밋한다. 원본 index/DB/node_modules를 테스트 환경으로 복제하지 않는다. 새 운영 템플릿은 합성 키/host, 메모리 DB 설정에서 `check --deploy`를 실행하고 빈 키 거절도 확인한다. 실제 메일이나 Naver 호출은 하지 않는다.

### exact candidate 재실행 결과

승인 경로109개 추가/수정과 기존320개 추적 해제로 만든 tree를 scratch clean snapshot에 export했다. source/blob hash와 cached whitespace 검사를 통과했고, fresh Python venv에 requirements13개를 설치하고 frontend `npm ci`를 수행했다. 이어 다음 결과를 실제로 확인했다.

| 검사 | 결과 |
|---|---|
| Django 전체 | 139/139 PASS |
| frontend | 112/112 PASS, fail/cancelled/skipped0 |
| Django check / migration drift / pip check | PASS / No changes detected / PASS |
| root / 날짜 고정 dependency / 실제 JWT 계약 | 7/7, 4/4, 1/1 PASS |
| 실제 Django HTTP Chromium | 33/33 PASS, blocked0 |
| native 세션 Chromium | 9/9 PASS |
| 운영 환경 template synthetic check / 빈 key negative | PASS / 기동 거절 확인 |
| 원본 DB 없는 candidate / 원본 보호167개 | DB 부재 유지 / SHA256 변화0 |

HTTP smoke의 goal/comment 모바일 캡처에서 제목/댓글 컨트롤 겹침·잘림은 관찰되지 않았다. 좁은 차트의 가독성은 별도 UX 평가 대상으로 유지한다. mock Naver·locmem·합성 fetch의 한계는 기존 보고서와 동일하다. 실행 후 변경은 이 결과 요약 등 문서뿐이며 최종 source hash와 새 문서 blob은 커밋 직전에 다시 확인한다.

기존/새 실행 결과와 최종 commit·원격 readback 근거는 private evidence `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-commit-release/`에 저장한다. 이 scratch 경로는 Git 대상이 아니다. 최종 hash/푸시 결과는 사용자 완료 보고로 제공한다. 출시 우선순위·승인·입력은 `release-runbook.md`를 따른다.

## A. 재검증 시작 전 기존 관련 작업87개

- `.env.example`
- `.gitignore`
- `DEVELOPMENT_PRINCIPLES.md`
- `PROJECT_AUDIT_2026-10-09.md`
- `backend/book/identifiers.py`
- `backend/book/parameters.py`
- `backend/book/serializers.py`
- `backend/book/services.py`
- `backend/book/test_throttle.py`
- `backend/book/tests.py`
- `backend/book/throttles.py`
- `backend/book/views.py`
- `backend/dadokdadok/settings.py`
- `backend/dadokdadok/test_media.py`
- `backend/dadokdadok/test_settings.py`
- `backend/dadokdadok/urls.py`
- `backend/goal/README.md`
- `backend/goal/migrations/0003_explicit_nullable_period.py`
- `backend/goal/migrations/0004_scoped_uniqueness.py`
- `backend/goal/models.py`
- `backend/goal/periods.py`
- `backend/goal/serializers.py`
- `backend/goal/signals.py`
- `backend/goal/statistics.py`
- `backend/goal/test_calendar_boundaries.py`
- `backend/goal/tests.py`
- `backend/goal/views.py`
- `backend/recommendation/README.md`
- `backend/recommendation/services.py`
- `backend/recommendation/tests.py`
- `backend/recommendation/throttles.py`
- `backend/recommendation/urls.py`
- `backend/recommendation/views.py`
- `backend/requirements.txt`
- `backend/review/migrations/0003_align_review_model_state.py`
- `backend/review/permissions.py`
- `backend/review/test_book_contract.py`
- `backend/review/tests.py`
- `backend/review/urls.py`
- `backend/user/profile_images.py`
- `backend/user/recovery.py`
- `backend/user/security.py`
- `backend/user/tests.py`
- `backend/user/throttles.py`
- `backend/user/urls.py`
- `backend/user/views.py`
- `docs/environment.md`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/screen/book-detail.html`
- `frontend/screen/find-account.html`
- `frontend/screen/goals.html`
- `frontend/screen/index.html`
- `frontend/screen/library.html`
- `frontend/screen/main.html`
- `frontend/screen/mypage.html`
- `frontend/screen/mypage_edit.html`
- `frontend/screen/register.html`
- `frontend/screen/review-detail.html`
- `frontend/screen/review-write.html`
- `frontend/screen/search.html`
- `frontend/screen/welcome.html`
- `frontend/scripts/auth.js`
- `frontend/scripts/book-detail.js`
- `frontend/scripts/common.js`
- `frontend/scripts/goals.js`
- `frontend/scripts/library.js`
- `frontend/scripts/login.js`
- `frontend/scripts/main.js`
- `frontend/scripts/mypage.js`
- `frontend/scripts/mypage_edit.js`
- `frontend/scripts/review-detail.js`
- `frontend/scripts/review-write.js`
- `frontend/scripts/search.js`
- `frontend/scripts/security.js`
- `frontend/scripts/welcome.js`
- `frontend/styles/layout-fixes.css`
- `frontend/tests/layout.test.cjs`
- `frontend/tests/recommendations.test.cjs`
- `frontend/tests/review-regressions.test.cjs`
- `frontend/tests/session-races.test.cjs`
- `frontend/tests/verify_backend_contract.py`
- `scripts/dev.py`
- `tests/browser_smoke.py`
- `tests/test_dev.py`
- `tests/test_repository.py`
- `tests/verify_supported_dependencies.py`

## B. 마지막 재검증의19개

- `README.md`
- `backend/review/serializers.py`
- `backend/review/test_import_races.py`
- `backend/review/views.py`
- `backend/user/API_CONTRACT.md`
- `backend/user/serializers.py`
- `backend/user/test_signup_races.py`
- `docs/api.md`
- `docs/completion-reverification.md`
- `docs/dependency-upgrade.md`
- `docs/project-completion-report.md`
- `frontend/DEVELOPMENT_RESULTS.md`
- `frontend/scripts/api.js`
- `frontend/scripts/find-account.js`
- `frontend/scripts/register.js`
- `frontend/tests/dom.test.cjs`
- `frontend/tests/goals.test.cjs`
- `frontend/tests/native_session_races.py`
- `frontend/tests/public-auth-regressions.test.cjs`

## C. 이번 출시 문서 신규3개

- `docs/commit-scope.md`
- `docs/release-runbook.md`
- `docs/release-environment.example`

README는 B의 기존 파일에 문서 연결·API base 설명을 정정했고, A의 `docs/environment.md`도 설명만 정정했다. 삭제 경로320개는 source 추가/수정109개와 별개이며, 모두 DB/node_modules/bytecode 추적 해제다.
