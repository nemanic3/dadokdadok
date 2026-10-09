# 다독다독

기존 독서 기록·검색·추천·공유 플랫폼을 완성하는 프로젝트입니다. HTML/CSS/Vanilla JavaScript 프론트엔드와 Django/DRF 백엔드를 유지합니다. React/Next.js 재구축 프로젝트가 아닙니다.

## 개발 원칙

`DEVELOPMENT_PRINCIPLES.md`를 따릅니다. 기존 UI·API·데이터를 최대한 보존하고, P0 → P1 → P2 순으로 작은 수정과 회귀 테스트를 수행합니다. 원본 `backend/db.sqlite3`는 개발·테스트 실행에 사용하지 않습니다.

## 주요 기능

- 회원가입, 아이디/이메일 로그인, access/refresh JWT, 로그아웃 및 refresh 폐기
- 본인 프로필·선택형 이미지 수정, 현재 비밀번호 확인 후 비밀번호 변경
- 이메일 기반 아이디 안내와 만료·1회성 비밀번호 재설정 링크
- 네이버 키워드 검색·정확한 ISBN 조회, 정상 빈 결과/외부 오류 구분
- 리뷰 CRUD와 작성자 권한, 내 서재, 좋아요 상태/토글, 댓글 CRUD
- 연간·월간 기간 목표, 서울 시간대의 리뷰 기록일 기준 통계
- 네이버 연관 도서 추천과 기존 리뷰·평점을 활용한 간단한 개인화 추천

목표의 집계 날짜는 리뷰 `created_at`입니다. 실제 완독일·재독 횟수를 추측하거나 기존 기록에 자동으로 채우지 않습니다. 기존 무기간 목표도 올해 목표로 자동 변환하지 않습니다.

## 구조

```text
backend/
  dadokdadok/       Django 설정·URL·WSGI/ASGI
  user/            인증·프로필·계정 복구
  book/            네이버 검색·ISBN·최근 도서
  review/          리뷰·서재·좋아요·댓글
  goal/            기간 목표·통계·보존형 마이그레이션
  recommendation/  연관·개인화 추천
frontend/
  screen/          기존 HTML 화면
  scripts/         Vanilla JS·공통 API/안전 DOM 처리
  styles/          기존 CSS
  assets/          로고·기본 이미지·아이콘
  tests/           실제 HTML/JS DOM 회귀·Django 계약 테스트
scripts/dev.py     원본 DB를 거절하는 로컬 실행기
tests/             실행기·저장소 안전성·브라우저 통합 검증
docs/              환경·의존성·최종 실행 결과
```

## 설치

프로젝트 루트에서 Python 3.12 가상환경을 만들어 설치합니다. 검증된 Django 5.2.18 / DRF 3.17.2와 호환 의존성은 `backend/requirements.txt`에 고정되어 있습니다. 기존 `.venv-runtime`은 이전 버전 비교용이므로 새 환경에 현재 requirements를 설치하십시오.

```bash
python3.12 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm test
cd ..
```

npm은 프론트 테스트 도구용입니다. 애플리케이션 자체는 번들 빌드가 필요 없는 정적 HTML/JS입니다. Node 20 이상이 필요하며, 실제 검증 버전과 결과는 최종 보고서를 확인하십시오. 기존 추적 node_modules를 재사용할 필요는 없습니다.

## 환경변수

`docs/environment.md`와 `.env.example`을 참고하십시오. Django 설정이 `.env`를 자동으로 읽지는 않습니다. 셸·프로세스 환경에 설정해야 합니다. 운영 키를 개발 키로 덮어쓰거나 Git에 저장하지 마십시오.

최소 로컬 설정:

```bash
export DJANGO_DEBUG=1
export DJANGO_SECRET_KEY='YOUR_PRIVATE_LOCAL_DEVELOPMENT_KEY'
export JWT_SIGNING_KEY="$DJANGO_SECRET_KEY"
export DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost,[::1]'
export EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
```

네이버 실제 호출에는 승인된 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`가 필요합니다. 실메일 발송에는 승인된 SMTP 설정이 필요합니다. 자동 회귀/E2E는 합성 자격정보·mock 네이버·locmem 메일을 사용합니다.

## 로컬 실행

```bash
.venv-dev/bin/python -B scripts/dev.py --check
.venv-dev/bin/python -B scripts/dev.py --frontend-port 5501
```

기본 API는 loopback 8000, 프론트는 loopback 5500입니다. 예시는 5500이 다른 작업에서 사용 중일 때 5501을 사용합니다. 브라우저에서 `http://127.0.0.1:5501/screen/index.html`을 엽니다. 종료는 Ctrl+C입니다.

실행기는 `.local/dev.sqlite3`에만 로컬 마이그레이션을 적용합니다. 원본 DB 경로·심볼릭 링크·하드링크는 거절하고 사용 중인 포트도 먼저 검사합니다. 기존 원본 DB에 마이그레이션을 적용하려면 별도 백업·검토·승인이 필요합니다.

API 주소는 `api.js` 로드 전에 `window.DADOK_API_BASE_URL` 또는 `<meta name="api-base-url" content="...">`로 지정할 수 있습니다. 기본값은 loopback 프론트에서 API 8000, 그 외에서는 same-origin입니다. 명시적으로 설정한 API base는 다른 origin일 수도 있으며 access/refresh는 그 base로 전송됩니다. helper는 설정된 API base와 다른 origin 및 `/api/` 밖의 요청을 거절합니다. 운영 API base는 승인된 HTTPS origin으로 고정하고 설정·정적 파일 변조를 방지해야 합니다.

## 테스트

아래 키는 실제 키가 아닌 테스트용 문자열입니다. DB 경로는 원본과 다른 위치여야 합니다.

```bash
export PYTHONDONTWRITEBYTECODE=1
export DJANGO_DEBUG=1
export DJANGO_SECRET_KEY='isolated-regression-key-not-production'
export JWT_SIGNING_KEY="$DJANGO_SECRET_KEY"
export DJANGO_DB_PATH="$PWD/.local/regression-base.sqlite3"
export EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
export NAVER_CLIENT_ID=''
export NAVER_CLIENT_SECRET=''
cd backend
../.venv-dev/bin/python -B manage.py check
../.venv-dev/bin/python -B manage.py test --noinput
../.venv-dev/bin/python -B manage.py makemigrations --check --dry-run
cd ..
.venv-dev/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
.venv-dev/bin/python -B tests/verify_supported_dependencies.py
.venv-dev/bin/python -B frontend/tests/verify_backend_contract.py
cd frontend && npm test
```

실제 Chromium E2E는 프로젝트 root에서 아래처럼 실행합니다. Playwright는 앱 런타임 의존성이 아닌 선택적 테스트 도구입니다. E2E도 분리된 DB와 합성 계정만 사용합니다. 실제 네이버·SMTP 성공이나 운영 배포를 증명하지 않습니다.

```bash
.venv-dev/bin/python -m pip install playwright==1.63.0
.venv-dev/bin/python -m playwright install chromium
DADOK_EVIDENCE_DIR="$(.venv-dev/bin/python -c 'import tempfile; print(tempfile.mkdtemp(prefix="dadok-verification-"))')"
.venv-dev/bin/python -B tests/browser_smoke.py --output-root "$DADOK_EVIDENCE_DIR/browser" --obtain-cdn
.venv-dev/bin/python -B frontend/tests/native_session_races.py --output "$DADOK_EVIDENCE_DIR/session-races" --cdn-cache "$DADOK_EVIDENCE_DIR/browser/cdn-cache"
```

`--obtain-cdn`은 고정된 실제 Chart.js·Pretendard CSS만 읽기 전용으로 확보합니다. 검증 중 외부 네트워크는 차단하며, 캐시가 있으면 이 옵션을 생략할 수 있습니다. 서버·API/JWT/DB/DOM/Chart는 실제 실행하고 네이버 상류만 모의합니다. 결과 위치는 명령 출력의 `RESULTS` 경로를 확인하십시오.

별도 `native_session_races.py`는 실제 HTML/JS와 Chromium의 공유 localStorage/storage 이벤트/Web Locks를 실행하되 fetch 응답은 합성 fixture입니다. 실제 backend HTTP E2E와 구분합니다. 탭 간 갱신·로그아웃 조정은 secure context의 `navigator.locks` 지원 범위에서 검증했으며, 이 API가 없는 브라우저에 같은 교차 탭 보장을 확대 주장하지 않습니다. 보존 검사·합성 키·loopback 제한과 브라우저 테스트 결과는 아래 완료 보고서에 기록합니다.

DOM 회귀의 Django URLconf 검사는 `.venv-dev` → `.venv-runtime` → `.venv` Python을 탐색합니다. 격리 frontend 복사본에서는 `DADOK_PROJECT_ROOT`와 필요하면 `DADOK_TEST_PYTHON`을 지정합니다. `DADOK_TEST_JSDOM`으로 기존 설치한 jsdom 경로를 지정할 수도 있습니다.

## API·검증 문서

- `backend/user/API_CONTRACT.md`: 인증·복구·프로필 계약
- `backend/goal/README.md`: 연간·월간 목표·legacy 데이터·통계 기준
- `docs/api.md`: 전체 API와 오류·추천 계약
- `docs/environment.md`: 개발/운영 설정
- `docs/dependency-upgrade.md`: 지원 버전 업데이트와 실제 검증
- `docs/completion-reverification.md`: 이전 작업 재검증·잔여 결함 수정·현재 최종 실행 결과·남은 승인 사항
- `docs/commit-scope.md`: 기존 미커밋 구현·추가 재검증 수정의 커밋 범위와 보존·보안 검사
- `docs/release-runbook.md`: 출시 P0/P1/P2 실행 절차·승인 게이트·사용자 입력
- `docs/release-environment.example`: 실제 값이 없는 운영 프로세스 환경 참고 템플릿
- `docs/project-completion-report.md`: 이전 작업 수정 내역·과거 테스트·진행 상태 기록 및 최신 보고서 안내
- `PROJECT_AUDIT_2026-10-09.md`: 수정 전 감사 기록. 현재 동작과 구분하십시오.

## 보안·제한

원본 DB·키·토큰·node_modules·bytecode는 신규 커밋에 포함하지 않습니다. 추적 해제는 로컬 파일 삭제가 아니며, Git 과거 이력의 비밀정보를 지우지도 않습니다. 확인된 과거 노출에는 별도 키 교체/이력 정리 승인이 필요합니다.

키 교체, 원본 DB 변경, 서비스 배포, 실메일·실네이버 호출은 이번 로컬 검증과 별도입니다. 운영 출시 완료 여부는 최종 보고서의 게이트와 제한사항을 확인하십시오.
