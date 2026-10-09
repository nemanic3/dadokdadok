# 다독다독 무료 배포

2026-10-10. 사용자가 승인한 구성은 Cloudflare Pages + Render 무료 Docker Web Service + Neon 무료 PostgreSQL이다. 유료 서버, 영구 디스크, 유료 DB, 로컬 Tunnel 상시 운영은 선택하지 않는다. 기존 `backend/db.sqlite3`은 복사본 점검 및 PostgreSQL 복원 비교 후 운영 Neon에 33개 기록을 이전했다. 원본은 보존했고 컨테이너가 자동 import하지 않는다.

## 실행 구성

- Pages 프로젝트: `dadokdadok`, GitHub `nemanic3/dadokdadok`, 운영 브랜치 `master`.
- Pages 저장소 루트: `/`, 빌드 `python3 scripts/build_pages.py`, 출력 `dist`.
- 공개 도메인: `dadok.nemanic.dev`. 기존 `nemanic-website` 및 다른 도메인/DNS를 변경하지 않는다.
- 기존 HTML/CSS/JS와 고정 프로필 SVG 6개·API가 반환하는 아이콘 SVG 8개를 Pages에 게시한다. 루트는 홈 화면으로 이동하며 없는 경로는 404다. DB, 개발 자격정보, tests, node_modules는 게시하지 않는다.
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
| Pages 운영 | `DJANGO_ORIGIN` | `https://dadokdadok-api.onrender.com`, 경로/query 없음 |
| Pages 운영 Secret | `ORIGIN_PROXY_SECRET` | Django와 동일한 신규 임의 secret, 32자 이상 |
| Render | `DJANGO_SETTINGS_MODULE` | `dadokdadok.production` |
| Render | `DJANGO_DEBUG` | `0` |
| Render | `DJANGO_ALLOWED_HOSTS` | `dadokdadok-api.onrender.com` |
| Render Secret | `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY` | 신규 독립 난수 키, 충분한 길이 |
| Render Secret | `ORIGIN_PROXY_SECRET` | Pages와 동일 |
| Render Secret | `DATABASE_URL` | Neon 접속 URL, TLS 필수 |
| Render | `BOOK_SEARCH_PROVIDER` | `kakao` |
| Render Secret | `KAKAO_REST_API_KEY` | 카카오 Daum 책 검색 REST API 키 |
| Render | `EMAIL_BACKEND` | `user.email_backend.ResendEmailBackend` |
| Render Secret | `RESEND_API_KEY` | 검증된 발신 도메인의 발송 키 |
| Render | `DEFAULT_FROM_EMAIL` | `다독다독 <noreply@mail.dadok.nemanic.dev>` |
| Render | `PASSWORD_RESET_URL` | `https://dadok.nemanic.dev/screen/find-account.html` |

Preview 배포에 운영 origin/secret을 설정하지 않는다. 프런트에는 별도 API base나 비밀 값이 필요하지 않다. Render가 제공하는 `PORT`를 Gunicorn이 사용한다. `DJANGO_DB_PATH` 및 기존 SMTP 비밀번호는 이 운영 구성에서 사용하지 않는다.

## 배포·데이터

`render.yaml`은 `plan: free`를 명시하고 필수 private 설정을 `sync: false`로 둔다. GitHub 계정의 해당 저장소를 실제 연결해야 자동 배포가 가능하다. 공개 Git URL만 연결하면 자동 배포가 되지 않을 수 있다. `autoDeployTrigger: checksPass`는 GitHub CI 성공 후 재배포한다.

컨테이너 시작은 운영 설정 검증 → PostgreSQL migration → cache table 준비 → Gunicorn이다. 기존 SQLite를 읽거나 import하지 않는다. 운영 데이터가 생긴 이후 schema migration 전에는 Neon에서 복구 가능한 백업/branch와 호환성 검토가 필요하다. 컨테이너에 있는 파일 복사는 DB 백업이 아니다. 무료 Neon의 복구 보관/용량/compute 한도를 확인하고 외부 백업·복구 절차를 정해야 한다.

기존 DB 이전 전에는 비공개 일관된 복사본에서 migration history, FK/PK, 중복 이메일, legacy 목표, 계정 및 도서 데이터의 적합성을 검토한다. 공개 이력의 과거 노출 때문에 기존 서명키를 재사용하지 않는다. 이전은 승인 후 별도 실행하고 로그인 비밀번호와 PK 관계를 보존하며 PostgreSQL 시퀀스도 검증한다.

## 무료 제한

Render 무료 서버는 idle 15분 후 중단될 수 있고 재개 시 첫 요청이 느리다. Pages API proxy는 재개를 고려해 최대 90초를 기다리지만 플랫폼 timeout/월 사용량 한도와 정상 기동을 보장하지 않는다. 유료 keep-alive 또는 자동 유료 전환은 적용하지 않는다. Neon/Resend의 무료 quota가 소진되면 기능이 제한될 수 있으며 결제 승인 없이 업그레이드하지 않는다.

## 검증 및 운영 상태

- 공개 주소: https://dadok.nemanic.dev (HTTPS 활성). 오타 `dodok` 연결은 제거했다. `nemanic.dev`, `www`, `portfolio`, `hongikbot` 레코드는 보존했다.
- Pages `dadokdadok`, Render `dadokdadok-api` (service `srv-db4ibchsrm7s73fqnqkg`, Docker Free Singapore), Neon `dadokdadok` (project `plain-paper-15851031`, PostgreSQL 16 Free Singapore) 생성 및 연결 완료.
- GitHub `master` 연동: Pages 자동 배포, Render는 CI 성공 이후 자동 배포. [Linux/PostgreSQL 검증 성공](https://github.com/nemanic3/dadokdadok/actions/runs/37967553989)을 확인했다.
- Django 전체 152개 테스트가 SQLite와 Linux Docker/PostgreSQL 16에서 통과했다. 프런트 DOM 회귀 112개와 Pages proxy 3개도 통과했다. SQLite 오류 문자열에 의존하던 중복 처리를 PostgreSQL 제약 정보로 교체했고 Linux 연도 표시 차이도 수정했다.
- 공개 API 실제 검증: health 200, 책 검색 및 ISBN 조회, 임시 계정 가입·로그인·JWT 갱신·프로필 변경·리뷰 작성/조회/수정·좋아요·댓글·서재·목표/월별 통계·로그아웃·refresh 폐기 통과. 임시 계정 및 연결 기록은 삭제했다. 원본 API는 비밀 없는 직접 접속을 403으로 차단한다.
- DB 이전: 원본의 integrity/FK/중복 이메일 점검 통과. 원본은 구 스키마였으므로 복사본에 migration 4개 적용 후 격리 PostgreSQL 복원을 검증했다. 계정 6, 책 6, 리뷰 8, 댓글 3, 좋아요 2, 목표 8을 빈 Neon DB에 트랜잭션으로 이전하고 전체 33개 기록·PK·비밀번호 해시·날짜·관계 일치를 확인했다. legacy 목표의 미상 기간은 임의로 추정하지 않는다. 기존 JWT 세션은 이전하지 않으며 새 서명키를 사용하므로 다시 로그인한다.
- 원본 SQLite 및 고정 SVG의 SHA-256은 배포 전과 동일하다. DB 및 비밀 값은 Docker/Pages/Git에 포함되지 않는다.
- Resend `mail.dadok.nemanic.dev` 발신 도메인 검증 완료, 발송 전용 키와 Django HTTPS 메일 backend 설정 완료. 실제 사용자에게 메일은 보내지 않았다. 실제 수신 확인은 운영자가 계정 복구 화면에서 수행한다.
- 남은 운영 작업: 복구 메일 실제 수신 확인, 운영 DB의 정기 외부 백업·복구 절차 설정. 무료 quota와 휴면 재기동 지연을 관리한다. 유료 옵션·결제 설정은 적용하지 않았다.

참고: [Cloudflare Pages GitHub 연동](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/), [Render 무료 제한](https://render.com/docs/free), [Render Blueprint](https://render.com/docs/blueprint-spec), [Neon 무료 제공](https://neon.com/blog/neon-free-plan-1-gb-per-project), [Resend 발송 API](https://resend.com/docs/api-reference/emails/send-email).

[네이버 공식 공지](https://developers.naver.com/notice/article/32530)에 따라 책 검색 API는 2026-07-31 종료되어 운영 도서 검색은 카카오 Daum 책 검색으로 교체한다. 공개 API의 필드와 ISBN 조회·추천 호출 경로는 유지한다. 무료 쿼터만 사용하고 유료 API는 활성화하지 않는다.

카카오 무료 쿼터 및 요청 형식: [책 검색 REST API](https://developers.kakao.com/docs/ko/daum-search/dev-guide#search-book), [무료 쿼터](https://developers.kakao.com/docs/ko/getting-started/quota). 운영 서버의 `BOOK_SEARCH_PROVIDER=kakao`를 유지한다. 과거 Naver 어댑터는 기존 개발 테스트 호환용이며 운영에 사용하지 않는다.
