# 다독다독 출시 실행 절차와 승인 게이트

작성: 2026-10-09. 이 문서는 출시 준비이며 운영 배포 승인이 아니다. HTML/CSS/Vanilla JavaScript + Django/DRF + SQLite 구조를 유지한다. 완료 근거는 `completion-reverification.md`, 커밋 범위는 `commit-scope.md`를 따른다.

## 이번에 준비한 것 / 실행하지 않은 것

- 현재 코드가 실제로 읽는 변수만 담은 `release-environment.example`을 준비했다. 실제 값은 모두 비워 두었고 자동 적용하지 않는다.
- 아래 P0 → P1 → P2 순서, 담당 승인, 실행 절차, 통과 기준과 중단/복구 기준을 정의했다.
- 운영 배포, 원본 DB migration, 키 교체, 기존 세션 폐기, Git 이력 정리, 실제 Naver/SMTP 호출은 수행하지 않았다.
- 아래 명령의 실행 주체는 승인 후 작업자다. 이번 문서화가 미래 작업의 실행 결과를 뜻하지 않는다.

## P0 — 출시 차단 항목

### 1. 과거 노출과 인증 정책

근거: `docs/environment.md`, `backend/dadokdadok/settings.py`, `backend/user/security.py`, `backend/user/recovery.py`.

1. Git 과거 이력에 있었던 키·DB 노출의 영향 범위를 비밀값/개인정보를 출력하지 않고 평가한다. 새 커밋의 추적 해제는 과거 이력 삭제가 아니다.
2. 사용자에게 Naver/Django/JWT/SMTP 키 교체와 기존 세션 처리 범위의 별도 승인을 받는다. 새 값은 비밀관리 기능이나 비추적 전용 파일로 전달하고 채팅·Git·명령 인자·로그에 기록하지 않는다.
3. 키 교체/배포/세션 폐기의 순서를 정하고, 노출된 키로 되돌리는 rollback을 금지한다. JWT 변경이 모든 기존 access/refresh에 미치는 영향을 staging에서 확인한다.
4. Git 이력 정리는 협업자·백업·원격 복제본 영향과 별도의 승인 후 계획한다. 이 요청의 일반 push와 분리하며 force push를 수행하지 않는다.
5. 현재 access 유효기간은 최대 1시간, refresh는 7일이며 `ROTATE_REFRESH_TOKENS=False`다. 클라이언트의 회전 대응 테스트는 운영 회전 활성화가 아니다. 로그아웃/비밀번호 변경/reset 직후 기존 access의 즉시 폐기가 필요한지 결정한다. 즉시 폐기가 필요하면 서버 측 검증 설계·회귀 테스트를 먼저 추가한다.
6. 기존 중복 이메일 정책을 결정한다. 현재 모호한 로그인/복구는 거절하지만 이메일 unique schema가 해결된 것은 아니다. 사용자가 승인하기 전 중복 병합·삭제·이메일 unique migration을 만들거나 적용하지 않는다.

통과 기준: 승인된 새 비밀정보 공급·세션 정책·데이터 정책과 staging 검증 기록. 정책 미결 또는 노출 키 재사용이면 출시 중단.

### 2. 운영 경로·HTTPS·프록시·요청 제한

근거: `backend/dadokdadok/settings.py`, `backend/book/throttles.py`, `backend/user/throttles.py`, `frontend/scripts/api.js`.

- 권장 구조는 같은 HTTPS origin에서 `/api/`는 Django WSGI로, `/screen/`, `/scripts/`, `/styles/`, `/assets/`는 기존 frontend 정적 파일로 제공하는 방식이다. 운영은 `scripts/dev.py`/Django runserver/Python http.server로 제공하지 않는다. WSGI 대상은 `dadokdadok.wsgi:application`이나 운영 서버 패키지·서비스 정의는 아직 정해지지 않았다.
- 비-loopback 기본 API는 same-origin이다. 다만 `window.DADOK_API_BASE_URL` 또는 meta `api-base-url`로 지정한 HTTP(S) API base는 다른 origin도 허용하며 access/refresh를 그 base로 전송한다. helper는 frontend origin이 아니라 설정된 API base와 다른 origin 및 `/api/` 밖의 요청을 거절한다. API base는 승인된 HTTPS origin으로 고정하고 설정·정적 파일 변조를 방지한다. 별도 API origin은 사용자 승인·정확한 CORS 허용목록·실제 브라우저 검증이 필요하다. 타 frontend origin으로의 인증정보 전송 자체를 금지하려면 별도 helper 정책 변경 승인과 회귀 검증이 필요하다.
- `DEBUG=0`에서는 HTTPS redirect·secure cookies·1년 HSTS(includeSubDomains/preload)를 설정한다. 하위 도메인까지 HTTPS로 제공할 수 있는지 확인한다. 코드에 preload 값이 있다고 실제 preload 목록 등록을 뜻하지 않는다.
- 현재 `SECURE_PROXY_SSL_HEADER`, trusted proxy 목록, proxy/cache 환경변수 스위치는 없다. TLS 종료 프록시를 선택하면 header 제거/덮어쓰기·백엔드 직접 접근 차단·HTTPS 판별을 먼저 구현/검증해야 한다. 미설정 상태에서 reverse proxy만 붙이면 redirect loop가 날 수 있으므로 검증 전 배포하지 않는다.
- throttle은 클라이언트가 보낸 X-Forwarded-For를 신뢰하지 않고 `REMOTE_ADDR`를 사용한다. 프록시 도입 후 모든 사용자에게 프록시 IP 하나의 budget이 적용되지 않도록 검증한다. 사용자 헤더를 그대로 신뢰하도록 바꾸면 안 된다.
- 현재 캐시는 Django 기본 프로세스 로컬 캐시다. 다중 worker/인스턴스 간 공통 quota가 아니다. 공유 캐시 선택·설정과 경합/429/Retry-After/위조 IP 테스트가 필요하며 공유 캐시만으로 원자적 제한을 보장하지 않는다. Naver import는 검색/ISBN/추천/리뷰의 동일 BookThrottle budget을 유지한다.
- 인증 정보·reset UID/token·이메일·Authorization header가 app/proxy/APM 로그에 남지 않도록 redaction을 설정한다. 복구 링크의 query string을 access log에 저장하지 않는다.

사용자 결정: 호스팅 환경·접근 방식, frontend 도메인, same-origin 여부, TLS 종료 위치, 공유 캐시 사용 가능 여부, 예상 사용자/동시 요청 수. 결정 후 운영 서버·프록시·캐시 설정 및 회귀 검증은 작업자가 수행한다. 아직 이를 완료했다고 보고하지 않는다.

통과 기준: HTTPS 화면/API/reset, redirect loop 없음, 백엔드 우회 차단, spoofed header 거절, 배포 전체 quota 검증. Web Locks가 없는 브라우저의 교차 탭 보장은 현재 검증되지 않았으므로 지원 브라우저 정책도 결정한다.

### 3. DB 백업·migration·복구

근거: `backend/goal/migrations/0003_explicit_nullable_period.py`, `0004_scoped_uniqueness.py`, `backend/review/migrations/0003_align_review_model_state.py`와 이전 복사본 보존 검증.

1. 운영/원본 경로와 작업 DB 경로를 따로 확정한다. `DJANGO_DB_PATH`는 checkout 밖의 절대 경로다. 일반 manage.py의 기본값은 원본 DB일 수 있다.
2. 원본 적용 전에 명시적 승인을 받는다. SQLite 연결의 backup API로 일관된 private backup을 만들고 권한·암호화·보관기간·복구 책임자를 설정한다. 실행 중 SQLite/WAL 파일 하나만 단순 복사하는 방식을 백업으로 삼지 않는다.
3. 백업 복사본에서 migration plan과 예상 SQL을 확인하고 적용한다. 모든 기존 테이블/PK/행/필드, legacy 기간 NULL, migration history 확장, integrity_check와 foreign_key_check를 비교한다. 출력에는 개인 행을 넣지 않는다.
4. 사용자 작업을 잠시 멈추는 maintenance window와 되돌리기 시점을 승인받는다. 이후 원본/운영 경로를 재확인하고 승인된 migration만 적용한다. 이메일 재해석이나 unique 정책 변경을 이 과정에 끼워 넣지 않는다.
5. rollback은 새 데이터 유실 여부를 검토한 백업 복구와 호환 코드 조합으로 계획한다. `migrate <old number>`가 항상 안전하다고 가정하지 않는다. 쓰기를 재개한 뒤 오래된 백업으로 무단 복구하지 않는다.
6. SQLite 동시 쓰기·SQLITE_BUSY·백업 중 요청·다중 worker 부하를 staging에서 검증한다. DB vendor 전환은 별도 승인 사항이다.

승인 후 격리 복사본에서만 수행할 명령 예시(먼저 private 프로세스 환경을 주입한다). 일반 manage.py는 원본 guard가 없으므로 DJANGO_DB_PATH가 비어 있지 않은 절대 경로, checkout 밖의 승인된 복사본이고 원본 또는 그 symlink/hardlink와 다른 파일인지 확인하며 미확인 시 중단한다:

```sh
# CWD: backend, Python: requirements가 설치된 승인된 venv
python -B manage.py showmigrations --plan
python -B manage.py migrate --plan
# --plan은 적용하지 않는다. 복사본 migrate는 격리 복사본 작업 승인 후 수행한다.
# 원본/운영 DB migrate는 별도의 원본 적용 승인 후에만 수행한다.
```

통과 기준: 복사본 보존 재검증·실제 복구 연습·승인된 maintenance/rollback 계획. 이번 원본 `backend/db.sqlite3`는 계속 미변경이다.

## P1 — staging 통합·운영 구성

### 4. 비밀정보 주입과 설정 검사

`release-environment.example`은 참고 템플릿이다. Django는 `.env`를 자동 로드하지 않는다. 배포 플랫폼이 프로세스 환경에 값을 주입한다. 운영은 로컬 `local_credentials.json`을 읽지 않는다.

- 필수 입력: DJANGO_SECRET_KEY, JWT_SIGNING_KEY, 명시적 non-wildcard DJANGO_ALLOWED_HOSTS, 분리된 절대 DJANGO_DB_PATH, 승인된 NAVER_CLIENT_ID/SECRET, SMTP host/port/user/password/TLS, DEFAULT_FROM_EMAIL, HTTPS PASSWORD_RESET_URL.
- same-origin 구성은 DJANGO_CORS_ALLOWED_ORIGINS를 비워 둘 수 있다. 별도 API origin은 명시적으로 설정할 수 있으나 승인된 HTTPS base로 고정하고 정확한 CORS 허용목록과 실제 access/refresh 흐름을 브라우저에서 검증한다.
- EMAIL_BACKEND는 `django.core.mail.backends.smtp.EmailBackend`로 명시한다. console/file/locmem/dummy는 운영 기동에서 거절한다. 현재 코드는 EMAIL_USE_TLS만 읽는다. implicit TLS(예: 465/EMAIL_USE_SSL)가 필수인 SMTP라면 환경변수만 추가하지 말고 구현/검증 변경이 필요하다.
- `PASSWORD_RESET_URL`은 승인된 frontend의 `/screen/find-account.html` HTTPS URL로 지정한다. reset-link 유효기간은 현재 3600초다.

위 필수 입력은 운영 절차상의 필수 gate이며 모두 기동 시 강제 검증되는 것은 아니다. Naver/SMTP 상세 값과 reset URL은 누락/기본값이어도 check가 통과할 수 있다. 비밀값을 출력하지 않고 승인된 값의 존재·SMTP 방식·HTTPS reset URL을 별도로 확인하고 미입력 시 외부 전달/출시 gate를 중단한다.

일반 manage.py에는 dev.py의 원본 경로 거절 guard가 없다. 아래 모든 관리 명령 전에 DJANGO_DB_PATH가 비어 있지 않은 절대 경로이고 checkout 밖의 승인된 복사본이며, 원본 또는 원본의 symlink/hardlink와 다른 파일인지 확인한다. 미확인/불일치 시 중단한다. 원본/운영 DB 명령은 별도 적용 승인 없이는 실행하지 않는다.

실제 외부 호출 없이 격리 staging/복사본 환경에서 먼저 실행:

```sh
# CWD: backend; 환경에 DJANGO_DEBUG=0 및 승인된 설정을 주입
python -B manage.py check --deploy
python -B manage.py makemigrations --check --dry-run
```

`check --deploy` 통과는 SMTP/Naver 전달·HTTPS 프록시·DB 복구 성공을 증명하지 않는다. stdout/stderr에는 비밀정보를 출력하지 않으며 설정 dump/diff를 공개 로그로 남기지 않는다.

### 5. static/media와 실제 전달

- frontend는 번들 빌드 없이 정적 파일 전체를 같은 버전으로 올린다. 화면 URL은 `/screen/index.html`을 사용하며 root redirect는 운영 웹서버에서 결정한다. JS/CSS 캐시 갱신이 이전/새 버전을 섞지 않도록 release 단위로 배포한다.
- Django STATIC_ROOT는 현재 `backend/staticfiles`, MEDIA_ROOT는 `backend/media`다. frontend static과 Django collectstatic의 결과는 별개다. collectstatic은 승인된 staging release 복사본에서 먼저 실행하고 체크아웃 원본/사용자 media를 덮어쓰지 않는다. 운영 media는 DEBUG=0에서 Django 개발 별칭으로 제공되지 않는다.
- 운영 웹서버에서 공개 `/media/profile_images/`를 실제 `backend/media/profile_image/` 또는 승인된 release의 고정 SVG 디렉터리로 명시적으로 alias한다. 일반 `/media/` → MEDIA_ROOT 매핑만으로는 현재 API의 복수형 URL을 제공하지 못한다. 저장된 이미지 값이나 원본 DB는 수정하지 않는다. DEBUG=0 staging에서 API가 반환하는 6개 URL을 직접 요청하여 HTTP200·SVG Content-Type/본문을 확인한다. frontend `/assets/` fallback 표시는 media 검증 성공이 아니다.
- Chart.js/Pretendard CDN 실패·SRI·CSP 허용목록을 staging에서 확인한다. CSP를 문서 작성만으로 활성화했다고 간주하지 않는다. 자체 호스팅을 선택하면 고정 bytes/SRI·라이선스·실제 브라우저 회귀를 다시 확인한다.
- 승인된 Naver 테스트 자격정보로 검색/ISBN/추천/미등록 도서 리뷰 import, 정상 빈 결과, upstream 장애, quota 소진을 확인한다. 자동 테스트 mock 성공과 별도 기록한다.
- 승인된 SMTP와 수신 테스트 계정으로 아이디 안내/reset 전달·지연/실패·만료·1회성·다른 계정 세션 보존을 확인한다. 스팸함·발신 도메인 인증도 운영 담당자가 확인한다. 실제 사용자 전체를 대상으로 테스트 메일을 보내지 않는다.

통과 기준: static/media HTTP 성공, 승인된 외부 전달 증거, recovery 비노출, error path 정상, 비밀정보 없는 로그. 테스트 자격정보/수신 주소가 없으면 해당 게이트는 미검증이다.

### 6. 출시 검증·모니터링·배포 승인

1. 정확한 commit으로 fresh checkout하고 `backend/requirements.txt` 설치, frontend `npm ci`로 재현한다. 기존 DB/node_modules를 배포 산출물로 복사하지 않는다.
2. README의 backend/DOM/JWT/root/dependency 검증과 Chromium HTTP 33/native 세션 9 회귀를 격리 DB·합성 키·mock/locmem으로 수행한다. 별도로 실제 staging HTTPS/SMTP/Naver 검증을 기록한다.
3. 예상 부하에서 로그인/복구/책 import quota, DB 잠금, 다중 worker·탭 간 순서, 백업/재시작 중 요청을 검증한다. Web Locks 지원 조건과 테스트 범위를 명시한다.
4. 5xx·지연·429·메일 실패·Naver 오류·디스크·백업 실패를 관측하고 알림 담당자·채널을 정한다. reset query/JWT/이메일/본문은 수집하지 않는다. 현재 별도 health endpoint/운영 모니터링 통합은 없으므로 성공한 public read probe와 프로세스 점검을 설계한다.
5. 출시 승인자는 P0/P1 체크리스트와 복구 연습을 확인하고 release commit/maintenance window를 승인한다. 실제 운영 배포는 그 별도 승인 후 수행한다.

## P2 — 출시 범위/후속 개선

- 추천의 실사용 품질, 전체 접근성·키보드/스크린리더, 좁은 모바일 차트 가독성, 지원 브라우저 행렬을 평가한다.
- 현 기능의 명확한 제한: 통계 기준은 리뷰 created_at이며 실제 완독일·재독은 추측하지 않는다. legacy 목표는 기간을 자동 재해석하지 않는다.
- 사용자의 출시 범위 결정을 받아 차단 항목과 후속 항목을 나눈다. P2를 생략할 때도 필수 접근성/지원 범위는 별도 합의한다.

## 사용자가 제공하거나 결정할 항목

비밀값은 채팅에 보내지 않는다. 비밀관리 UI/승인된 저장 방식으로 입력한다.

| 입력/결정 | 필요한 내용 | 다음 작업 |
|---|---|---|
| 운영 인프라 | 호스팅·접근 권한, domain, same-origin 여부, TLS 종료, 공유 캐시 가능 여부, 예상 부하 | WSGI/proxy/cache/static/media 설정과 실제 HTTPS/부하 검증 |
| Naver/SMTP | 승인된 Naver 계정·앱 자격정보, SMTP host/port/TLS 방식·발신 주소·private credential, 테스트 수신 주소 | staging 전달/장애/quota 테스트 |
| 노출 대응 승인 | 키 교체 범위·시점, 기존 세션 처리, 별도 Git 이력 정리 여부 | 영향 계획·새 키 공급·승인된 교체; 이번 작업에서는 실행 금지 |
| 데이터 승인 | 운영 DB 경로·maintenance window·백업/보관/복구 담당, 원본 migration 승인, 중복 이메일 정책 | 복사본 재검증 후 승인된 원본 적용; 이번 작업에서는 실행 금지 |
| 제품/보안 정책 | access 즉시 폐기 필요 여부, 지원 브라우저/Web Locks 조건, 출시 범위·알림 담당/채널 | 필요한 구현·회귀·운영 검증 후 출시 승인 요청 |

입력/결정만 받으면 자동으로 운영 완료가 되는 것은 아니다. 아직 프록시·공유 cache/운영 서버 통합, 실제 외부 전달, 부하·복구·모니터링 검증이 남아 있으며 결정된 환경에 맞춰 후속 구현/검증이 필요하다.
