# 다독다독 무료 배포

2026-10-10. 사용자가 승인한 구성은 Cloudflare Pages + Render 무료 Docker Web Service + Neon 무료 PostgreSQL이다. 유료 서버, 영구 디스크, 유료 DB, 로컬 Tunnel 상시 운영은 선택하지 않는다. 기존 `backend/db.sqlite3` 이전은 별도 점검 후 진행하며 자동 import하지 않는다.

## 실행 구성

- Pages 프로젝트: `dadokdadok`, GitHub `nemanic3/dadokdadok`, 운영 브랜치 `master`.
- Pages 저장소 루트: `/`, 빌드 `python3 scripts/build_pages.py`, 출력 `dist`.
- 공개 도메인: `dadok.nemanic.dev`. 기존 `nemanic-website` 및 다른 도메인/DNS를 변경하지 않는다.
- 기존 HTML/CSS/JS와 고정 프로필 SVG 6개·API가 반환하는 아이콘 SVG 8개를 Pages에 게시한다. 루트는 로그인 화면으로 이동하며 없는 경로는 404다. DB, 개발 자격정보, tests, node_modules는 게시하지 않는다.
- Pages Functions는 `/api/*`만 고정 HTTPS Django origin으로 전달한다. JWT/POST/query를 유지하고 캐시를 금지하며 리디렉션을 따르지 않는다. API 설정이 없거나 preview 호스트면 503으로 차단한다.
- Django는 Render Singapore 무료 서비스에서 `deploy/Dockerfile`로 실행한다. Django 개발 서버 대신 non-root Gunicorn 단일 sync worker를 사용한다. 저장은 Neon Singapore PostgreSQL 16에 하며 로컬 컨테이너 파일시스템에 DB를 저장하지 않는다.
- 프로필은 업로드가 아닌 기존 선택형 SVG다. R2 또는 별도 파일 저장소가 필요하지 않다. Django admin/static은 공개 Pages 경로에 게시하지 않는다.
- Pages와 Django가 공유하는 `ORIGIN_PROXY_SECRET`을 검증한 뒤 HTTPS/IP metadata를 신뢰한다. 직접 origin API 접근은 403이다. DB-backed cache는 재시작 뒤에도 quota 상태를 유지하지만 DRF의 best-effort 제한이 원자적 동시성 제한이라는 뜻은 아니다.
- 무료 Render는 SMTP 포트를 차단하므로 기존 복구 메일 내용을 HTTPS Resend API로 전달한다. 실패는 기존의 일반 안내 응답을 유지하고 키·수신자·복구 링크를 로그에 출력하지 않는다.

## 설정할 환경 변수

실제 비밀 값은 Git/문서/공개 빌드 변수에 넣지 않는다. 플랫폼 환경 변수/Secrets에만 입력한다. 아래는 이름과 비밀이 아닌 설정 예시다.

| 대상 | 이름 | 설정 |
|---|---|---|
| Pages 운영 | `PUBLIC_HOST` | `dadok.nemanic.dev` |
| Pages 운영 | `DJANGO_ORIGIN` | 생성한 Render 서비스의 HTTPS origin, 경로/query 없음 |
| Pages 운영 Secret | `ORIGIN_PROXY_SECRET` | Django와 동일한 신규 임의 secret, 32자 이상 |
| Render | `DJANGO_SETTINGS_MODULE` | `dadokdadok.production` |
| Render | `DJANGO_DEBUG` | `0` |
| Render | `DJANGO_ALLOWED_HOSTS` | 정확한 Render 서비스 hostname |
| Render Secret | `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY` | 신규 독립 난수 키, 충분한 길이 |
| Render Secret | `ORIGIN_PROXY_SECRET` | Pages와 동일 |
| Render Secret | `DATABASE_URL` | Neon 접속 URL, TLS 필수 |
| Render Secret | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 승인된 현재 네이버 운영 자격정보 |
| Render | `EMAIL_BACKEND` | `user.email_backend.ResendEmailBackend` |
| Render Secret | `RESEND_API_KEY` | 검증된 발신 도메인의 발송 키 |
| Render | `DEFAULT_FROM_EMAIL` | 검증된 발신 주소 |
| Render | `PASSWORD_RESET_URL` | `https://dadok.nemanic.dev/screen/find-account.html` |

Preview 배포에 운영 origin/secret을 설정하지 않는다. 프런트에는 별도 API base나 비밀 값이 필요하지 않다. Render가 제공하는 `PORT`를 Gunicorn이 사용한다. `DJANGO_DB_PATH` 및 기존 SMTP 비밀번호는 이 운영 구성에서 사용하지 않는다.

## 배포·데이터

`render.yaml`은 `plan: free`를 명시하고 필수 private 설정을 `sync: false`로 둔다. GitHub 계정의 해당 저장소를 실제 연결해야 자동 배포가 가능하다. 공개 Git URL만 연결하면 자동 배포가 되지 않을 수 있다. `autoDeployTrigger: checksPass`는 GitHub CI 성공 후 재배포한다.

컨테이너 시작은 운영 설정 검증 → PostgreSQL migration → cache table 준비 → Gunicorn이다. 기존 SQLite를 읽거나 import하지 않는다. 운영 데이터가 생긴 이후 schema migration 전에는 Neon에서 복구 가능한 백업/branch와 호환성 검토가 필요하다. 컨테이너에 있는 파일 복사는 DB 백업이 아니다. 무료 Neon의 복구 보관/용량/compute 한도를 확인하고 외부 백업·복구 절차를 정해야 한다.

기존 DB 이전 전에는 비공개 일관된 복사본에서 migration history, FK/PK, 중복 이메일, legacy 목표, 계정 및 도서 데이터의 적합성을 검토한다. 공개 이력의 과거 노출 때문에 기존 서명키를 재사용하지 않는다. 이전은 승인 후 별도 실행하고 로그인 비밀번호와 PK 관계를 보존하며 PostgreSQL 시퀀스도 검증한다.

## 무료 제한

Render 무료 서버는 idle 15분 후 중단될 수 있고 재개 시 첫 요청이 느리다. Pages API proxy는 재개를 고려해 최대 90초를 기다리지만 플랫폼 timeout/월 사용량 한도와 정상 기동을 보장하지 않는다. 유료 keep-alive 또는 자동 유료 전환은 적용하지 않는다. Neon/Resend의 무료 quota가 소진되면 기능이 제한될 수 있으며 결제 승인 없이 업그레이드하지 않는다.

## 검증 및 진행 상태

- SQLite 전체 Django 테스트 148개 통과(2026-10-10).
- PostgreSQL 16 전체 Django 테스트 148개 통과. DB 교체로 발견된 SQLite 문자열 전용 중복 처리 3곳을 실제 PostgreSQL 제약 metadata 기반으로 수정했다. 관련 없는 NOT NULL/PK 오류를 중복으로 오인하지 않는 테스트도 유지했다.
- 프런트 DOM 회귀 112개, Pages proxy 테스트 3개 통과.
- Docker 이미지 빌드 및 실제 운영 모드 Gunicorn/PostgreSQL TLS 기동 성공. 합성 HTTP로 회원가입·로그인·JWT 갱신·프로필·리뷰 작성/조회/수정·좋아요·댓글·서재·연간 목표/진행률·로그아웃 후 refresh 폐기를 확인했다. 실제 Naver/메일 전달 성공과 구분한다. 원본 DB/media SHA-256 보존 확인.
- 플랫폼 프로젝트·도메인·환경 변수·실제 Naver/메일 전달은 계정 인증과 비밀 값 입력 후 별도로 검증해야 한다. 이 문서는 그 완료를 주장하지 않는다.

참고: [Cloudflare Pages GitHub 연동](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/), [Render 무료 제한](https://render.com/docs/free), [Render Blueprint](https://render.com/docs/blueprint-spec), [Neon 무료 제공](https://neon.com/blog/neon-free-plan-1-gb-per-project), [Resend 발송 API](https://resend.com/docs/api-reference/emails/send-email).
