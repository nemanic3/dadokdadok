# 환경변수와 안전한 실행

## 키·데이터 경계

설정은 프로세스 환경변수를 우선합니다. 개발 `DEBUG=True`에서만 비추적 `backend/local_credentials.json`을 읽을 수 있습니다. 이 파일에 있던 기존 키를 임의로 교체하지 않았으며 값도 문서에 기록하지 않습니다. 운영 모드에서는 로컬 파일을 읽지 않습니다. `.env` 자동 로더는 도입하지 않았습니다.

| 변수 | 의미 |
|---|---|
| DJANGO_DEBUG | 개발 1 / 운영 0. 운영에서는 허용 host·키·메일 backend 명시 필요 |
| DJANGO_SECRET_KEY | Django private signing key. 비어 있으면 기동 실패 |
| JWT_SIGNING_KEY | JWT 서명키. 운영 필수, 개발 미설정시 Django key 사용 |
| DJANGO_ALLOWED_HOSTS | 쉼표 구분. 개발 loopback, 운영 wildcard/누락 거절 |
| DJANGO_CORS_ALLOWED_ORIGINS | 정확한 scheme/host/port origin 목록. 전체 허용하지 않음 |
| DJANGO_DB_PATH | SQLite 경로. 개발 실행기·테스트에서는 원본과 다른 DB만 사용 |
| NAVER_CLIENT_ID / NAVER_CLIENT_SECRET | 승인된 네이버 테스트/운영 자격정보. 자동 테스트는 mock |
| EMAIL_BACKEND | 테스트 locmem. 운영은 명시적 Django SMTP만 허용 |
| EMAIL_HOST / EMAIL_PORT | 승인된 SMTP endpoint/port |
| EMAIL_HOST_USER / EMAIL_HOST_PASSWORD | 사설 SMTP 자격정보. Git/log 노출 금지 |
| EMAIL_USE_TLS | 기본 1. SMTP TLS 사용 |
| DEFAULT_FROM_EMAIL | 승인된 발신 주소 |
| PASSWORD_RESET_URL | 신뢰하는 프론트 복구 화면. 운영 HTTPS, 개발 HTTP loopback만 허용 |

`DJANGO_DB_PATH`는 비워 두지 말고 분리된 절대 경로를 지정하십시오. 기본 Django 관리 명령은 기존 DB를 가리킬 수 있으므로, 직접 `manage.py migrate`를 실행하기 전에 환경변수를 반드시 확인해야 합니다. `scripts/dev.py`는 원본·그 별칭을 거절합니다.

## 이메일

회귀/E2E의 locmem 메일은 실제 전송하지 않습니다. 서버 프로세스 메모리에만 보관하며 테스트가 전달할 복구 링크를 읽습니다. 개발 설정의 console backend는 복구 링크를 stdout으로 출력할 수 있으므로, 비밀정보 로그를 금지하는 환경에서는 사용하지 말고 locmem 또는 승인된 SMTP를 명시하십시오. 운영은 미설정·빈값·console·filebased·dummy·locmem을 기동 시 거절합니다.

복구 안내는 등록 여부를 노출하지 않는 동일 응답입니다. 메일 장애에서도 주소·SMTP 비밀값·토큰이 응답이나 에러 로그에 포함되지 않습니다. `PASSWORD_RESET_TIMEOUT`은 3600초이며 링크는 사용 후 재사용할 수 없습니다.

## 프론트

`api.js`보다 앞에서 `window.DADOK_API_BASE_URL` 또는 `meta[name=api-base-url]`를 설정합니다. 설정이 없으면 loopback 프론트는 API port8000, 그 외는 same-origin입니다. 명시적 API base는 다른 origin도 허용하며 access/refresh를 그 base로 전송합니다. helper는 frontend origin이 아니라 설정된 API base와 다른 origin 및 `/api/` 밖의 요청을 거절합니다. 운영은 승인된 HTTPS API base로 고정하고 설정·정적 파일 변조를 방지합니다. 별도 API origin에는 사용자 승인·정확한 CORS 허용목록·실제 브라우저 검증이 필요합니다.

API의 media URL과 프론트의 기본 프로필 자산은 서로 구분합니다. 개발 Django만 media 별칭을 제공합니다. 운영 static/media 제공·TLS·trusted proxy는 운영 인프라에서 별도 설정해야 합니다.

## 운영 모드 검사

`DEBUG=0`에서는 SSL redirect, secure session/CSRF cookie, HSTS, nosniff, DENY frame을 활성화합니다. TLS 종료 프록시를 사용하는 경우 실제 인프라의 trusted header 정책을 검증해야 합니다. 저장소 코드만으로 TLS·백업·복구·monitoring 정상성을 선언할 수 없습니다.

운영 구성 검사에는 실제 키 대신 충분히 긴 격리 검사 키, 예시 host, 명시적 SMTP backend를 설정하고 원본과 다른 DB 경로를 사용하십시오. `manage.py check --deploy`는 설정 검사이지 운영 배포나 실제 SMTP 전달 성공이 아닙니다.

## Git

DB·자격정보·가상환경·node_modules·bytecode·새 IDE 파일은 ignore됩니다. 기존 DB/의존성/bytecode의 index 추적만 해제했고 로컬 파일을 삭제하지 않았습니다. 과거 Git 이력의 키와 DB는 별도로 남아 있습니다. 실제 키 교체·기존 세션 폐기·이력 재작성은 사용자 승인 없이 실행하지 않습니다.
