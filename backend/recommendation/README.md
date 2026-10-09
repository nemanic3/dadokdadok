# 추천 API 계약과 결정적 규칙

기존 HTML/CSS/Vanilla JS 및 Django/DRF를 유지한다. 모델·마이그레이션 추가와 추천 요청의 DB 쓰기는 없다.

## 기존 네이버 추천

`GET /api/recommendation/naver/?isbn=...&query=...&display=5`

- 기존 배열과 `isbn/title/author/publisher/image/link` 키를 유지한다.
- `query` 단독과 정확한 ISBN-10/13 입력을 지원한다. checksum이 틀리거나 공백/추가 토큰이 붙은 ISBN은 보정하지 않고 400으로 거절한다.
- `display`: 기본 5, 정수 1~100. `query`: trim 후 최대 200자.
- ISBN이 있으면 저장된 저자·출판사 메타데이터를 우선 사용하고, 없으면 공유 `book.services`의 정확한 ISBN 조회를 사용한다. 일반 검색 요청에 `d_isbn`을 보내지 않는다.
- 메타데이터/저자·출판사가 없으면 명시적으로 전달된 `query`에만 fallback한다. fallback도 없으면 200 `[]`이다. upstream 장애를 메타데이터 없음으로 숨기지 않는다.
- 공유 서비스의 연결/읽기 timeout `(3.05, 10)`을 사용한다. 정상 빈 목록 200 `[]`, upstream/응답 형식 오류 502, timeout 504를 구분하고 원문 예외를 응답하지 않는다.
- 유효하지 않은 후보, 현재 책, ISBN-10/13 별칭 중복을 제외한다. 필터링 후 후보가 적어도 추가 무제한 외부 검색으로 채우지 않는다.

## 추가 개인화 추천

`GET /api/recommendation/personalized/?isbn=...&display=5` — 인증 필요. ISBN은 현재 책 제외용 선택 인자이며 입력/배열/키/display 계약은 위와 같다.

- 후보는 **이미 DB에 저장된 미독 도서**다. 사용자에게 리뷰가 있는 책은 평점이 없거나 낮아도 읽은 책으로 제외한다. 현재 ISBN, invalid/missing ISBN, ISBN-10/13 별칭 중복도 제외한다.
- 해당 인증 사용자의 4~5점 리뷰만 선호도를 만든다. 가중치는 `rating - 3`, 저자·출판사 문자열은 비교할 때만 strip/casefold한다. 저자 점수는 2배, 출판사는 1배다. 원본 데이터는 바꾸지 않는다.
- 순위: 개인 선호 점수 내림차순 → 유효한 0~5점 community 평균 내림차순 → 평점 개수 내림차순 → ISBN identity/원본 ISBN/PK 오름차순. cold-start는 개인 점수 0인 같은 규칙이다.
- 다른 사용자의 개인 선호도나 요청의 `user` 인자를 사용하지 않는다. 응답에는 도서 allowlist 키만 있고 리뷰 원문·이메일·사용자 ID·개인 점수는 없다.
- 두 추천 API는 `book` scope의 IP throttle을 공유한다. 기본 `60/min`, `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES.book`으로 변경 가능. 임의 `X-Forwarded-For`를 신뢰하지 않는다. 실제 다중 worker 환경의 제한은 cache 배포 설정에 달려 있다.
- 전체 로컬 후보를 평가하는 작은 규칙 기반 MVP다. 협업 필터링/의미 검색/장르 이해/추천 품질 평가를 구현했다고 주장하지 않는다.

## 프론트와 검증 경계

로그인 상세 화면은 같은 recommendation grid에서 개인화를 우선 사용한다. 후보 없음/개인화 실패 시 ISBN과 기존 제목 query를 포함한 공개 네이버 추천으로 fallback한다. 익명은 네이버만 호출한다. 기존 SafeDOM, 클래스, grid 레이아웃을 유지한다.

추천 회귀는 `backend/recommendation/tests.py`, 최근 목록 회귀는 `backend/book/tests.py`, 실제 HTML/jsdom 및 Django URL resolution 검증은 `frontend/tests/recommendations.test.cjs`에 있다. 네이버는 HTTP 경계만 mock한다. 실제 네이버 자격정보·쿼터·성공률·추천 실품질은 검증하지 않았다.
