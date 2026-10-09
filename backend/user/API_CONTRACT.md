# 사용자 API 계약 (2026-10-09)

기존 `/api/user/` 경로와 성공 응답 키를 유지한다. 공개 프로필의 이메일 제거는 보안상 의도된 예외다. 스키마/기존 데이터 변경 없음.

| 경로 | 요청 | 동작 |
|---|---|---|
| GET `profile/<nickname>/` | 익명 허용 | `id,nickname,profile_image`만 반환. 이메일/비밀번호 없음. 없는 닉네임 404. |
| GET `me/` | JWT 인증 | 본인 `id,nickname,email,profile_image`. |
| POST `signup/` | `username,nickname,email,password`, 선택 `profile_image` | username은 Django `normalize_username`(NFKC)을 모델 validators·unique 검사 전에 적용. 이메일 필수·공백 제거·소문자 저장·대소문자 무시 중복 검사. Django 비밀번호 validators 적용 후 create_user 해싱. 성공 201, 검증 실패 400. |
| POST `login/` | `username`에 아이디 또는 이메일, 혹은 `email`; `password` 필수 | 식별자는 조회 전 Django NFKC 정규화, 이메일 대소문자 무시. username/email 후보가 정확히 1명일 때만 인증. 중복/교차 충돌·비활성·오인증 401. 형식/누락 400. `message,access_token,refresh_token,user` 유지. |
| POST `logout/` | 인증 + 문자열 `refresh_token` | JWT refresh 검증, subject가 인증 사용자와 일치해야 blacklist. 타인 토큰 403이며 미폐기. 누락/null/타입 오류/만료/access/폐기 토큰 400. 정상 200. access 즉시 폐기는 별개 정책. |
| PUT `update_profile/` | 인증, 선택 `nickname,email,profile_image` | 부분 수정. 검증 실패시 어떤 필드도 저장하지 않음. |
| PUT `update_profile/` | 인증, `password,current_password` | 현재 비밀번호 재인증, 변경 예정 프로필 기준 비밀번호 validators, set_password 저장 및 본인 outstanding refresh 전체 blacklist. 응답에 두 비밀번호 필드 없음. |
| GET `profile-images/` | 익명 허용 | 모델 선택 목록에서 `/media/profile_images/*.svg` URL 6개 생성. root URLconf의 개발용 기존 실제 `profile_image/` 폴더 alias와 일치. |
| POST `update-profile-image/` | 인증, `profile_image` | 저장 키 `profile_images/*.svg`와 위 목록의 상대 URL 모두 수락. 가입·프로필 수정도 동일 선택 검증 사용. 임의 URL/경로/null 거절. DB에는 기존 선택 키 저장. |
| POST `find-id/` | `email` | 활성·usable password·유일 이메일 계정에만 아이디 메일. 등록/미등록/모호/비활성 모두 같은 200 `message`; 응답에는 아이디 없음. |
| POST `reset-password/` | `email` | 비밀번호를 바꾸지 않고 uid/token 링크만 이메일 전송. 동일한 열거 방지 응답. 이메일 중복이면 전송하지 않음. |
| POST `reset-password/` | `uid,token,new_password` | Django 기본 PasswordResetTokenGenerator: 시간 만료, 기존 비밀번호/이메일/last_login 바인딩, 변경 후 재사용 거절. 활성/usable 확인, 정책 및 현재와 다른 비밀번호 요구. transaction + select_for_update로 검증/저장/refresh 철회. 잘못된 링크 400, 성공 200. |

가입의 기존 SQLite username/nickname unique 제약은 검증 뒤 insert 경쟁이 발생해도 기존 필드 메시지·`unique` code의400으로 처리하고 이미 생성된 승자 계정을 보존한다. 무관한 integrity 오류를 중복으로 오분류하지 않는다. 이메일 DB unique 추가나 기존 중복 행 정리는 아래 승인 경계대로 보류한다.

프론트 가입/reset 확인은 익명 `auth:false` 요청으로 기존 만료 JWT의 영향을 받지 않는다. reset 성공 표시는 로그인 변경과 독립이며 소모한 폼을 숨긴다. 로컬 세션 정리는 reset UID와 동일 JWT owner·요청 당시 epoch가 현재인 경우에만 수행하며 다른/새 계정은 보존한다.

## 설정과 요청 제한

- 링크 기준은 **`settings.PASSWORD_RESET_URL`** (부모 설정의 같은 이름 환경변수)이며 요청 Host/Origin에서 생성하지 않는다. 운영 `DEBUG=False`는 HTTPS 필수. 개발 `DEBUG=True`는 HTTP loopback만 허용. userinfo/query/fragment가 있는 기준 URL은 거절한다. 설정 오류는 등록 여부와 무관하게 동일한 503이며 메일을 보내지 않는다.
- 만료는 `PASSWORD_RESET_TIMEOUT`을 그대로 사용한다. 운영 `DEBUG=False`는 `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`를 명시해야 기동한다. 미설정/빈값/console/filebased/dummy/locmem/미승인 backend는 `ImproperlyConfigured`로 fail-closed. 개발 `DEBUG=True`의 console 기본값과 테스트 locmem은 유지한다. production 조건의 복구 동작 테스트는 settings override locmem으로만 실행하며 실제 SMTP 연결은 하지 않는다. SMTP/OSError는 민감정보 없는 로그를 남기고 같은 일반 응답을 유지한다.
- `USER_AUTH_THROTTLE_RATES` 딕셔너리로 아래 scope를 선택 재정의할 수 있다. 전역 `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`의 `auth/recovery/books`와 별도이며 전역 클래스 미설정이어도 활성화된다.

| scope | 기본 제한 |
|---|---|
| `signup_ip` | 5/min |
| `login_ip` / `login_identity` | 10/min / 5/min |
| `recovery_ip` / `recovery_identity` | 10/hour / 3/hour; find-id와 reset 메일 요청 합산 |
| `reset_ip` / `reset_identity` | 10/min / 10/min; 토큰 확인 |
| `user_mutation` | 20/min; 프로필·이미지·로그아웃·삭제 사용자별 합산 |

- 제한 초과 429 + Retry-After. IP는 REMOTE_ADDR로 계산하고 임의 X-Forwarded-For를 신뢰하지 않는다. 식별자 cache key는 정규화한 문자열의 SHA-256이며 이메일 원문/토큰은 저장하지 않는다. 로그인은 NFKC 동등 입력이 같은 식별자 제한을 공유한다.
- DRF cache throttling은 best-effort다. 다중 프로세스 운영에는 shared cache·프록시/edge 요청 제한 설정을 별도 검증해야 한다. trusted proxy 뒤 REMOTE_ADDR 집계 정책도 운영 설정에서 결정한다.
- 기존 email 필드에 DB unique 제약은 추가하지 않았다. 기존 중복 행을 수정하지 않고 모호한 이메일 인증/복구를 거절한다. 동시 가입까지의 DB 유일성 보장은 승인된 후속 migration 영역이다.
- root `/api/auth/token/`은 기존 URL/name 및 SimpleJWT 성공 응답 키 `access,refresh`를 유지하고 `LoginView`의 검증·username/email 후보 충돌 거절·인증 흐름을 그대로 재사용한다. `/api/user/login/`과 IP/식별자 throttle cache scope를 공유하며, 동일 식별자의 URL/IP 변경 및 NFKC 동등 Unicode 표기는 같은 제한에 집계한다. `/api/auth/token/refresh/`는 기존 SimpleJWT 갱신 경로 그대로다. 비밀번호 변경 후 refresh는 철회되지만 이미 발급된 access의 즉시 철회에는 부모의 SimpleJWT CHECK_REVOKE_TOKEN 등 별도 정책이 필요하다.

## 공개 리뷰/댓글 이미지 응답

`ReviewSerializer`와 `CommentSerializer`에 읽기 전용 `profile_image`를 additive 제공한다. 작성자의 선택 키에 대응하는 `/media/profile_images/*.svg` URL만 반환하고 email은 추가하지 않는다. 기존 DB에 allowlist 밖 이미지 값이 있으면 응답만 기본 이미지로 보정하며 저장 값은 변경하지 않는다. 리뷰/댓글 작성 payload의 `profile_image`는 무시하여 작성자 선택을 바꾸지 않는다.

## 검증

`backend`에서 현재 `requirements.txt`가 설치된 `.venv-dev`의 Python을 사용한다. 환경변수 DJANGO_SECRET_KEY/JWT_SIGNING_KEY(합성 테스트용), DJANGO_DEBUG=1, DJANGO_DB_PATH(원본과 다른 scratch 경로), EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend, PYTHONDONTWRITEBYTECODE=1을 설정해 `../.venv-dev/bin/python -B manage.py test user --noinput` 및 전체 suite를 실행한다. 설치·전체 검증은 root README를 따른다. 기존 `.venv-runtime`은 이전 버전 비교용이다. 원본 DB/migrate/배포/git 쓰기 없음.

기존 RED→GREEN 로그는 `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-development/auth-*.log`, 독립 리뷰 결함 수정의 단계별 RED/GREEN 로그는 `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-finalization/auth-fixes/`에 있다. 각 핵심 동작에 실제 Django/DRF 요청과 격리 DB 회귀 테스트가 있다. production SMTP 전달 성공/배포 검증은 하지 않았다.
