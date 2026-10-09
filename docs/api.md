# API 개요

기존 `/api/` 경로를 유지합니다. JSON 요청에는 `Content-Type: application/json`, 인증 요청에는 `Authorization: Bearer [REDACTED]`가 필요합니다. 실제 토큰·비밀번호는 문서에 넣지 않습니다.

## 사용자

상세 계약은 `backend/user/API_CONTRACT.md`를 확인하십시오.

- POST `/api/user/signup/`: 가입·비밀번호 정책·정규화/중복 검증
- POST `/api/user/login/`: `username`(아이디/이메일) 또는 `email`, `password`. 기존 `access_token,refresh_token,user` 응답 유지
- POST `/api/auth/token/`: 동일 인증/제한 정책, 기존 `access,refresh` 응답 유지
- POST `/api/auth/token/refresh/`: `refresh` → 새 `access`
- POST `/api/user/logout/`: 본인 `refresh_token` 검증·blacklist
- GET `/api/user/me/`, PUT `/api/user/update_profile/`: 본인 정보·프로필·현재 비밀번호 재인증 후 변경
- GET `/api/user/profile/<nickname>/`: 공개 필드만. email 제외
- GET `/api/user/profile-images/`, POST `/api/user/update-profile-image/`: allowlist 선택 이미지
- POST `/api/user/find-id/`, `/api/user/reset-password/`: 이메일 안내 또는 `uid,token,new_password` 확인

비밀번호 변경/재설정은 outstanding refresh를 폐기합니다. 이미 발급된 access의 즉시 폐기까지 보장하는 정책은 별도이며, 현재 access 만료까지의 잔여 위험을 감추지 않습니다.

## 도서

- GET `/api/book/search/?query=...&display=10&start=1`: 기존 배열 응답 유지, `q` 호환. display1~100/start1~1000. 페이지 정보는 `X-Total-Count`, `X-Page-Start`, `X-Page-Size` 헤더
- GET `/api/book/isbn/<isbn>/`: DB 우선, 없으면 네이버에서 정확히 일치하는 유효 ISBN 검색. 요청 ISBN을 임의로 고치지 않음
- GET `/api/book/recent-reviews/`: 안정적인 최근 도서 중복 제거

정상 빈 검색은 200/배열, ISBN 미존재는 404, 잘못된 입력은 400, upstream 오류는 안전한 502/504입니다. 검색·ISBN·추천과 리뷰 POST의 미등록 도서 upstream import는 같은 IP 기준 `book` 요청 제한(기본60/min)을 공유합니다. 캐시된 도서의 리뷰 생성·조회·수정·삭제는 upstream 제한을 소비하지 않습니다. 실제 upstream 오류의 자격정보/URL 원문은 응답하지 않습니다. 외부 네이버 성공은 승인된 키로 별도 확인해야 합니다.

요청 제한 설정은 `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['book']`입니다. 기존 `books`만 설정된 경우 호환 fallback으로 읽으며 두 키가 있으면 명시 `book` 설정이 우선합니다.

## 리뷰·공유

- GET/POST `/api/review/`, GET/PUT/PATCH/DELETE `/api/review/<id>/`
- GET `/api/review/library/`: 본인 서재. 정상 빈 배열
- GET `/api/review/library/<isbn>/`: 도서별 공개 리뷰
- POST `/api/review/<id>/like/`: 토글, count 반환
- GET `/api/review/liked/`: 본인 liked review ID 목록
- POST/PATCH/PUT/DELETE `/api/review/<id>/comments/`: 댓글 생성·수정·삭제. 수정/삭제에는 `comment_id`, 수정에는 `content`
- GET `/api/review/<id>/comments/list/`: 공개 목록

리뷰 수정·삭제와 댓글 수정·삭제는 서버에서 작성자를 검증합니다. user/book 등 소유 필드는 클라이언트가 바꿀 수 없습니다. 리뷰·댓글에는 읽기 전용 선택 이미지 URL을 제공하고 이메일은 제공하지 않습니다.

현재 SQLite 스택에서 ISBN insert 경쟁은 기존 Book 승자를 필드 변경 없이 재사용합니다. 동일 사용자·도서 리뷰 unique 경쟁은 기존 메시지의400으로 처리하며 승자 리뷰를 덮지 않습니다. 이 회귀는 실제 ORM의 결정적 interleaving으로 검증했으며 threaded load/SQLITE_BUSY나 다른 DB backend의 동일 동작까지 보장하지 않습니다.

공개 상세의 `is_liked=false`는 익명 조회 결과일 수 있습니다. 프론트는 로그인 사용자의 liked 상태를 인증 API로 별도 확인하여 새로고침 후에도 유지합니다. 공개 콘텐츠는 만료 JWT 없이 읽을 수 있습니다.

## 목표·통계

상세 계약과 데이터 보존은 `backend/goal/README.md`를 확인하십시오. 무쿼리 `progress/`는 목표가 없으면 기존404를 유지하고, 무쿼리 `monthly-progress/`는 목표 없이도 현재 연도 통계를200으로 제공합니다.

- GET/POST `/api/goal/goal/`, PATCH/PUT/DELETE `/api/goal/goal/<id>/`
- GET `/api/goal/progress/?year=YYYY[&month=M]`
- GET `/api/goal/monthly-progress/?year=YYYY[&month=M]`

명시 연도만 있으면 연간, 월도 있으면 월간 목표입니다. 목표 없으면 `goal_id`는 null, `goal_books`/`progress`는0이며 해당 기간의 `read_books`/`monthly_reading` 기록 집계는 그대로 제공합니다. 통계는 서울 시간대의 리뷰 기록일 기준이며, `read_books`/달성 상태는 동적 읽기 전용입니다. 기존 NULL 기간·counter·중복/잘못된 목표를 자동 재해석·수정·삭제하지 않습니다.

## 추천

- GET `/api/recommendation/naver/?query=...[&isbn=...&display=5]`: 기존 연관검색 배열 키 `isbn,title,author,publisher,image,link` 유지
- GET `/api/recommendation/personalized/?display=5[&isbn=...]`: 인증 필요. 저장된 리뷰·평점·도서 메타데이터를 사용하는 간단한 결정적 랭킹

개인화는 읽은 도서·현재 도서를 제외하고, 충분한 선호도가 없으면 공동 평점 기반 cold-start를 사용합니다. 읽기만 수행하며 새로운 도서를 임의로 원본 DB에 저장하지 않습니다. 후보가 없으면 정상 빈 배열입니다. 기존 UI의 추천 카드에서 개인화를 우선하고 필요하면 네이버 관련 검색으로 전환합니다. 모델 학습/유료 AI 서비스는 도입하지 않았습니다.

자동 테스트는 입력·후보 제외·순위·fallback·오류 계약을 검증합니다. 사용자 만족도나 실제 외부 도서 추천 품질까지 증명하지는 않습니다.
