# 다독다독 프로젝트 개발 상태·출시 준비 점검 보고서

- 점검일: **2026-10-09, KST**
- 대상: `/Users/shinsunghyun/Desktop/dadokdadok`
- 기준 커밋: `f094c504664a2c152dd8b4b13ab473be3e7d5292` / 브랜치 `master`
- 작업 방식: **읽기 전용 소스 분석, SQLite 읽기 전용 조회, 원본 코드 격리 실행**
- 변경 범위: 이 Markdown 보고서만 프로젝트에 추가. 기존 소스·설정·DB 수정, 패키지 설치, 마이그레이션 적용, 실제 API 데이터 변경은 하지 않음.
- 근거 표기: `backend/...`, `frontend/...`는 프로젝트 루트 기준 `파일:줄 범위`. `[1]` 등은 마지막의 공식 문서 출처.

## 1. 요약 및 전체 판정

**현재 상태는 주요 기능의 UI와 API가 존재하는 개발용 프로토타입이며, 그대로 실제 서비스를 출시하기에는 부족하다.** 단순 화면 목업만 있는 프로젝트는 아니다. 회원가입/로그인, 본인 프로필, 도서 검색, 리뷰, 좋아요·댓글, 목표·통계와 연관 도서 검색의 실제 처리 코드가 있다. 그러나 보안 경계, 일부 API 계약, 독서 목표의 기간 의미, 미구현 계정 기능, 실행·배포 재현성이 정리되지 않았다.

### 출시를 막는 핵심 문제

1. **리뷰 수정·삭제의 서버 소유자 검사 누락**: 다른 인증 사용자를 차단하는 코드가 없다. 삭제 원본 메서드를 합성 객체로 실행하여 비작성자 조건에서도 삭제 함수가 호출되는 것을 재현했다. 실제 데이터 삭제는 하지 않았다. (`backend/review/views.py:14-22,48-56`)
2. **사용자 콘텐츠의 미이스케이프 HTML 삽입**: 댓글, 닉네임, 리뷰 요약을 `innerHTML`에 직접 넣는다. 합성 문자열이 HTML sink에 그대로 들어가는 것을 확인했다. 브라우저 공격 실행은 하지 않았다. (`frontend/scripts/review-detail.js:219-234`, `frontend/scripts/book-detail.js:75-82`, `frontend/scripts/library.js:72-81`)
3. **비밀정보와 계정·토큰 DB의 Git 포함**: Django/JWT 서명키, 네이버 자격정보가 설정에 하드코딩되어 있고 SQLite DB도 추적된다. 실제 키 유효성·외부 공개 여부·운영 환경 사용 여부는 확인하지 않았다. 값은 보고서에 재기재하지 않는다. (`backend/dadokdadok/settings.py:8,121-122,130-133`)
4. **익명 공개 프로필에 이메일 반환**: 본인 정보용 serializer를 공개 조회에도 재사용한다. (`backend/user/views.py:132-139`, `backend/user/serializers.py:38-41`)
5. **로그인·로그아웃 계약 불완전**: 서버가 반환한 refresh token을 프론트가 저장하지 않고, 로그아웃에는 `null`을 보낸다. 발급한 refresh의 폐기를 보장하지 못한다. (`frontend/scripts/login.js:46-50`, `frontend/scripts/common.js:38-46`)
6. **연간 목표가 전기간 독서량을 집계**하고, 월간 목표는 없으며 월별 리뷰 작성 통계만 있다. (`backend/goal/models.py:4-12`, `backend/goal/views.py:35-49,60-83`)
7. **실제 통합 실행은 미검증**: 발견한 Python 환경에 Django 의존성이 없어 Django 검사/테스트가 시작되지 않았다. 프로젝트 자동 테스트도 placeholder뿐이다.

### 판정 기준

| 분류 | 의미 |
|---|---|
| **구현 완료** | 점검한 범위에서 UI·처리 코드·API 계약이 연결되고 필수 처리 경로가 존재함. **정적 구현 판정이며 실제 서비스 E2E 통과를 의미하지 않음.** |
| **부분 구현** | 주요 구현은 있으나 필수 흐름 누락, 계약·정책 불일치 또는 기능을 훼손하는 결함이 있음. |
| **미구현** | 동작에 필요한 서버/처리 흐름이 없거나 UI·주석·죽은 코드만 있음. |
| **검증 필요** | 환경·외부 서비스·실제 프레임워크/브라우저 실행 없이는 성공 여부를 확정할 수 없음. |

구현 상태와 검증 수준은 별개로 기록한다. 격리 테스트의 PASS는 **명시한 동작이나 결함을 재현했다는 뜻**이지 전체 서비스가 정상이라는 뜻이 아니다. 런타임 검증이 없다는 이유만으로 구현된 코드를 모두 미구현으로 분류하지 않았다.

## 2. 기술 스택 및 디렉터리 구조

### 2.1 실제 기술 스택

| 영역 | 소스에서 확인한 기술 | 비고/근거 |
|---|---|---|
| 프론트엔드 | 정적 HTML, CSS, Vanilla JavaScript, 브라우저 `fetch`, `localStorage` | **React 프로젝트가 아님.** `frontend/screen/`, `frontend/scripts/`, `frontend/styles/` |
| 그래프·폰트 | Chart.js CDN, Pretendard CDN | Chart.js 버전 미고정. 실제 CDN 로드·렌더링은 미검증. `frontend/screen/main.html:9`, `frontend/screen/goals.html:9-11` |
| npm 의존성 | axios `^1.7.9`, lockfile의 axios `1.7.9` | 본문 API 요청은 native fetch. axios를 사용하는 앱 코드 연결은 확인되지 않음. `frontend/package.json:1-5`, `frontend/package-lock.json:17-26` |
| 백엔드 | Python, Django **5.1.5**, Django REST Framework **3.15.2** | requirements 선언 버전이며 현재 실행 환경 설치 버전이 아님. `backend/requirements.txt:4-6` |
| 인증 | SimpleJWT **5.4.0**, PyJWT **2.10.1**, refresh blacklist | 기본 JWT 인증/로그인 필요 권한과 공개 예외가 설정됨. `backend/requirements.txt:7-9`, `backend/dadokdadok/settings.py:105-124` |
| CORS·외부 HTTP | django-cors-headers **4.6.0**, requests **2.32.3** | `backend/requirements.txt:5,10` |
| 저장소 | SQLite, Django ORM·마이그레이션 | `backend/dadokdadok/settings.py:72-78` |
| 외부 도서 데이터 | 네이버 검색 API | `backend/book/services.py:4-40`, `backend/recommendation/services.py:5-77` |

Django 공식 지원표에서 5.1 계열의 확장 지원 종료일은 **2025-12-03**이며, 현재 미지원 계열로 표시된다. 출시 전에 지원되는 계열의 검증된 패치 버전으로 옮겨야 한다. 이 감사에서는 패키지 업그레이드나 전체 CVE 스캔을 하지 않았다.[4]

### 2.2 실제 구조

```text
dadokdadok/
├── README.md
├── frontend/
│   ├── screen/              # HTML 13개: 로그인/가입/복구/메인/서재/목표/프로필/도서·리뷰
│   ├── scripts/             # JS 15개: 페이지별 처리 + auth/common
│   ├── styles/              # CSS 14개
│   ├── assets/images/       # 로고, 표지 배너, 기본 프로필, 별·하트
│   ├── package.json
│   ├── package-lock.json
│   └── node_modules/        # Git에 포함된 의존성 파일
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── dadokdadok/           # settings, root urls, ASGI/WSGI
│   ├── user/                # CustomUser, 가입/인증/본인·공개 프로필
│   ├── book/                # Book, 네이버 검색/ISBN 조회
│   ├── review/              # Review, Like, Comment, 서재·리뷰 API
│   ├── goal/                # Goal, 진행률·월별 통계, signals
│   ├── recommendation/      # 네이버 연관 키워드 검색
│   ├── media/               # 기본 SVG 이미지와 아이콘
│   ├── db.sqlite3           # 기존 계정·도서·리뷰·목표·토큰 데이터
│   └── 각 앱의 migrations/, tests.py
└── .idea/                   # IDE 메타데이터
```

인벤토리를 프로그램으로 집계했다. 감사 전 `git ls-files --cached --others --exclude-standard` 중복 제거 결과는 **465개**이며, `node_modules`/`__pycache__`를 제외하면 소스·설정·문서·이미지·DB·IDE 파일 **146개**다. Python 61개, HTML 13개, JavaScript 15개, CSS 14개를 확인했다. HTML/JS 전체를 기능·연결 기준으로 점검했고, Python 전체는 문법 검사 및 주요 처리·마이그레이션 대조를 수행했다. 이미지 시각 품질이나 모든 CSS의 브라우저 렌더링을 검증한 것은 아니다.

### 2.3 문서와 실제 구현의 차이

- README는 React/Bootstrap, Django 4.0, `components/pages`, `api/config/public` 구조를 설명하지만 실제 구조·버전과 다르다. (`README.md:80-83,122-128,143-152`)
- README의 `npm start` 지침은 현재 실행 불가: package.json에 start script가 없다. test/build도 없다. **정적 웹사이트에 번들 빌드가 반드시 필요한 것은 아니며**, 문제는 문서와 재현 가능한 실행 절차가 일치하지 않는다는 점이다. (`README.md:98-103`, `frontend/package.json:1-5`)
- 리뷰 기반 맞춤 추천·월간 목표라는 설명은 현재 코드 수준보다 넓다. (`README.md:34-39,49-60`)
- 루트 `.gitignore`가 없고, Git 인벤토리에는 `node_modules` 파일 150개, `__pycache__` 파일 169개가 포함된다. DB/비밀정보 관리와 함께 저장소 정리가 필요하다. 과거 이력 삭제는 별도 승인 없이 수행하지 않았다.

## 3. 기능별 구현 상태표

| 기능 | 판정 | 구현/결함 요약 및 소스 근거 | 실행 검증 수준 |
|---|---|---|---|
| 회원가입 | **부분 구현** | POST·중복 확인·비밀번호 해싱 있음. 비밀번호 정책 호출과 이메일 무결성 미흡. `backend/user/serializers.py:15-36`, `frontend/scripts/register.js:19-44` | 원본 create 경로 격리 실행. 실제 가입/DRF 검증은 미실행 |
| 사용자명 로그인 | **구현 완료** | username/password 인증과 access/refresh 반환, UI access 저장 연결. `backend/user/views.py:32-49`, `frontend/scripts/login.js:30-50` | 프론트 성공 응답 소비만 합성 검증. 실제 로그인은 검증 필요 |
| 이메일 로그인 | **미구현** | UI 안내와 달리 username 인증만 있음. 별도 이메일 backend 없음. `backend/user/views.py:36-39`, `frontend/scripts/login.js:21-34` | 정적 확인. 이메일을 username으로 가입한 우연한 경우와 구분 |
| 로그아웃 | **부분 구현** | refresh blacklist 서버 코드 존재. refresh 미저장·null 전달·중복 요청. `backend/user/views.py:52-62`, `frontend/scripts/common.js:34-60` | payload·중복 handler 재현. 실제 blacklist 결과는 검증 필요 |
| 토큰 갱신 | **부분 구현** | 서버 refresh route 있음, 프론트 갱신/재시도 없음. `backend/dadokdadok/urls.py:11-12` | 정적 확인 |
| 본인 프로필 조회 | **구현 완료** | 인증 + request.user 조회, 프론트 필드 일치. `backend/user/views.py:65-70`, `frontend/scripts/mypage.js:19-45` | 정적 계약/합성 응답 검증. 실제 HTTP는 미실행 |
| 닉네임·기본 이미지 수정 | **부분 구현** | 본인 수정 처리 있음. 변경 후 닉네임 캐시·이미지 제공 계약 불일치. `backend/user/views.py:72-79`, `frontend/scripts/mypage_edit.js:60-101` | 정적 확인. 실제 저장·이미지 로드 검증 필요 |
| 로그인 상태 비밀번호 변경 | **미구현** | UI가 password를 보내나 유효 serializer에 해당 필드/변경 처리 없음. `frontend/scripts/mypage_edit.js:79-83`, `backend/user/serializers.py:38-41` | AST로 유효 필드 확인 |
| 아이디 찾기·비밀번호 재설정 | **미구현** | 프론트 요청만 있고 서버 route/view·메일·토큰 처리 없음. `frontend/scripts/find-account.js:16,46`, `backend/user/urls.py:9-17` | 정적 확인 |
| 본인 계정 삭제 | **부분 구현** | 본인 삭제 API 있음. 대응 UI/재인증·토큰 정책 불완전. `backend/user/views.py:81-85` | 실제 삭제/토큰 사용 결과는 검증 필요 |
| 공개 프로필 | **부분 구현** | 닉네임 조회 구현, 이메일 공개 문제. `backend/user/views.py:132-139`, `backend/user/serializers.py:38-41` | 정적 확인 |
| 키워드 도서 검색 | **부분 구현** | 네이버 요청·직렬화·목록 UI 연결. 오류·빈 결과·query/q·페이지 처리 문제. `backend/book/views.py:14-26`, `frontend/scripts/search.js:19-105` | mock 요청/원본 처리 재현. 실네이버 성공은 검증 필요 |
| ISBN 도서 조회 | **부분 구현** | DB 우선 조회 + 외부 검색 있음. 빈 items 예외/ISBN 일치 검증 없음. `backend/book/views.py:33-49`, `backend/book/services.py:21-40` | 빈 items IndexError 및 view500 경로 격리 재현 |
| 리뷰 작성 | **부분 구현** | ISBN 책 조회/생성·서버 사용자 지정·중복 방지 있음. 평점/내용 검증 미흡. `backend/review/views.py:24-46`, `backend/review/serializers.py:30-40` | 프론트 POST body 확인. 실제 ORM 생성은 미실행 |
| 리뷰 조회·도서별 목록 | **부분 구현** | 공개 조회/목록·이동 존재. nullable 데이터·익명 Authorization 처리 문제. `backend/review/views.py:153-173`, `frontend/scripts/review-detail.js:67-70,125-130` | null 내용/평점 예외 재현 |
| 리뷰 수정·삭제 | **부분 구현** | PUT/DELETE UI·API 있음. 서버 소유자 권한 누락으로 출시 불가. `backend/review/views.py:14-22,48-56`, `frontend/scripts/review-detail.js:73-112` | 비작성자 합성 삭제 경로 재현. 실제 삭제 미수행 |
| 내 서재 | **부분 구현** | 본인 리뷰 기반 목록 있음. 빈 객체/배열 계약 및 없는 버튼 예외. `backend/review/views.py:123-149`, `frontend/scripts/library.js:42-65` | 두 결함을 원본 JS VM에서 재현 |
| 좋아요 토글 | **구현 완료** | 서버 user 지정 get_or_create 토글·unique 제약·UI POST 연결. `backend/review/views.py:59-72`, `backend/review/models.py:27-36` | 프론트 요청 계약 확인. 실제 DB/동시성은 검증 필요 |
| 좋아요 초기 상태 | **미구현** | 프론트 `/api/review/liked/` 기대, 대응 서버 경로/action 없음. `frontend/scripts/review-detail.js:132-145`, `backend/review/urls.py:11-33` | 정적 확인. 실제 오류 status는 미측정 |
| 댓글 작성·목록 | **부분 구현** | 서버 사용자 지정·내용 저장·공개 목록 연결. XSS sink/비문자열 처리 문제. `backend/review/views.py:75-100`, `frontend/scripts/review-detail.js:207-234,273-301` | mock POST·HTML sink·타입 예외 확인 |
| 댓글 수정·삭제 | **미구현** | 삭제 버튼 markup 없음, 서버 post만 지원, 수정 처리 없음. `frontend/scripts/review-detail.js:229-250`, `backend/review/views.py:75-90` | 정적 확인 |
| 연간 목표 설정·진행률 | **부분 구현** | 본인 목표 CRUD/차트 있음. year·기간 unique 없음, 전기간 집계. `backend/goal/models.py:4-12`, `backend/goal/views.py:13-50` | API 계약·원본 집계 조건 격리 검증 |
| 월간 목표 설정·달성률 | **미구현** | 월간 목표 모델/API/UI 없음. `backend/goal/models.py:4-12`, `backend/goal/urls.py:5-12` | 정적 확인 |
| 월별 독서량 통계 | **부분 구현** | 현재 연도 12개월 리뷰 작성량/차트 존재. 실제 완독일·과거 연도 선택 없음. `backend/goal/views.py:58-84`, `frontend/scripts/goals.js:51-87` | 합성 집계·Chart 호출 확인. 실제 그래프 렌더링은 미검증 |
| 목표 저장 counter 자동 갱신 | **부분 구현** | signal 함수 존재, 표준 초기화의 import/ready 연결 없음. `backend/goal/signals.py:6-34`, `backend/goal/apps.py:4-6` | 명시적 함수 호출만 검증. 실제 receiver 등록은 검증 필요 |
| 연관 도서 추천 | **부분 구현** | 제목 축약/저자·출판사 검색 결과 제공. 에러200·ISBN 계약·fallback 문제. `backend/recommendation/services.py:5-77` | 합성 정상/오류 경로 확인 |
| 리뷰·평점 기반 개인화 추천 | **미구현** | user/review/rating 선호도·유사도·개인화 순위·평가 로직 없음. `backend/recommendation/services.py:5-53`, `backend/recommendation/views.py:13-23` | 정적 확인 |
| 실제 네이버 API 성공·자격정보 | **검증 필요** | 실제 외부 요청/키 유효성·쿼터 확인을 하지 않음 | 공식 문서 계약만 대조 |
| 실제 브라우저↔Django E2E·운영 환경 | **검증 필요** | Django 의존성 부재, 서버/브라우저·배포 환경 미실행 | 문법·원본 격리 코드·DB 구조만 확인 |

## 4. 회원가입·로그인·프로필 상세

### 4.1 확인된 올바른 경계

- 가입 비밀번호는 `write_only`, 저장 전 `make_password`를 사용한다. **평문 비밀번호 저장이나 비밀번호 응답 반환으로 분류하지 않는다.** (`backend/user/serializers.py:18-19,33-36`)
- `me/update_profile/delete`는 인증된 `request.user` 기준이며 임의 user id로 다른 프로필을 수정하는 경로는 아니다. (`backend/user/views.py:65-85`)
- 현재 프로필 이미지는 **선택형 CharField + allowlist**다. 파일 업로드는 구현되지 않았으며, 무제한 파일 업로드 취약점이라고 평가하지 않는다. (`backend/user/models.py:6-19`, `backend/user/views.py:105-128`)

### 4.2 주요 미완성·보안 문제

1. **비밀번호 정책 미연결**: settings에 validators가 있어도 가입 serializer는 해싱 후 `User.objects.create`만 호출한다. `validate_password` 호출이 없다. Django 공식 문서도 모델 생성 수준에 validators가 자동 적용되지 않음을 설명한다. 실제 전체 serializer가 1글자 비밀번호를 허용했다고 주장한 것이 아니라, 원본 create 경로에 정책 강제가 없음을 확인했다. (`backend/dadokdadok/settings.py:81-86`, `backend/user/serializers.py:21-36`)[5]
2. **UserSerializer 중복 정의**: 7행과 38행에 같은 클래스가 있으며 마지막 정의의 필드는 `id,nickname,email,profile_image`다. 비밀번호 변경은 이 계약에 포함되지 않는다. 프로필 성공 메시지를 비밀번호 변경 성공으로 오인할 수 있다. (`backend/user/serializers.py:7-13,38-41`, `frontend/scripts/mypage_edit.js:79-100`)
3. **이메일 정책 불일치**: 가입의 exists 검사만 있고 DB email unique가 없다. 프로필 수정에는 같은 validate_email 검사가 없다. 이메일을 복구 식별자로 쓸지, 공백/대소문자/소유 확인 정책을 먼저 결정해야 한다. 동시성 경쟁은 실제 부하 테스트하지 않았다. (`backend/user/serializers.py:27-31,38-41`, `backend/user/migrations/0001_initial.py:28`)
4. **refresh 미저장·갱신 부재**: 실제 프론트 원본을 합성 로그인 응답으로 실행해 token/username만 저장됨을 확인했다. auth/common 로그아웃 body의 refresh는 null이다. `RefreshToken(None)`의 실제 라이브러리 동작을 실행하지 않았으므로 **로그아웃이 반드시 HTTP400이라는 단정은 하지 않는다**. 핵심은 발급받은 refresh를 전달·폐기하지 못한다는 점이다. (`frontend/scripts/login.js:46-50`, `frontend/scripts/auth.js:28-58`, `backend/user/views.py:55-62`)
5. **중복·실패 세션 처리**: main/goals는 auth/common을 함께 로드해 클릭 한 번에 로그아웃 요청 두 개를 보낸다. 실패 때 로컬 세션 정리는 일관되지 않다. logout은 refresh 철회만 구현하며 access 즉시 무효화의 명세·검증도 필요하다. (`frontend/screen/main.html:65-66`, `frontend/screen/goals.html:95-96`, `frontend/scripts/common.js:49-60`)
6. **이미지 계약**: API/model 경로는 `profile_images/`, 실제 backend media 폴더는 `profile_image/`다. root URLconf에는 media 제공 연결이 없고, 리뷰 화면은 JSON profile endpoint를 `<img src>`로 사용한다. 마이페이지는 로컬 assets 매핑이 있어 그 화면까지 항상 깨진다고 단정하지 않는다. (`backend/user/views.py:95-100,114-120,136-139`, `backend/dadokdadok/urls.py:7-26`, `frontend/scripts/mypage.js:35-45`, `frontend/scripts/review-detail.js:117-120,222-224`)

## 5. 네이버 API 기반 도서 검색

### 5.1 실제 흐름

- 검색: URL `query` → `GET /api/book/search/` → 네이버 일반 검색 → items → title/author/publisher/published_date/isbn/image_url/link 배열 → 화면.
- ISBN 상세: 저장된 Book 조회 → 미등록이면 일반 네이버 검색의 `query=isbn, display=1` → 첫 항목 반환.
- 상세 GET의 외부 결과는 DB에 저장하지 않는다. Book 저장은 리뷰 생성 경로에서 이루어진다. **DB 우선 조회를 TTL 검색 캐시로 계산하지 않는다.** (`backend/book/views.py:14-49`, `backend/book/serializers.py:21-31`, `backend/review/views.py:30-44`)

### 5.2 발견한 문제

- **빈 ISBN 결과 예외**: `{items: []}`에서 첫 항목을 인덱스로 접근해 IndexError. 원본 service·view 격리 실행에서 view500 경로를 확인했다. (`backend/book/services.py:33-38`, `backend/book/views.py:39-49`)
- **장애/빈 결과 혼동**: 검색의 upstream RequestException은 `{error}`이고 view는 이를 정상 결과 없음과 같은 404로 변환한다. 프론트는 `!ok`에서 오류로 처리해 정상 빈 목록 UI를 보여주지 못한다. (`backend/book/services.py:13-19`, `backend/book/views.py:19-26`, `frontend/scripts/search.js:35-42,62-64`)
- **timeout·retry·캐시·페이지네이션 없음**: requests.get에 timeout이 없고 검색은 기본 10개 items만 전달한다. start/sort/total 전달 및 다음 페이지 UI가 없다. 검색/추천의 코드상 throttle도 없다. 외부 reverse proxy/WAF 정책은 미검증. (`backend/book/services.py:4-17,21-40`, `backend/dadokdadok/settings.py:105-113`)
- **ISBN 식별 검증 미흡**: 형식/길이/checksum·외부 결과 ISBN 일치 확인 없이 첫 검색 결과를 사용한다. 리뷰 생성은 요청 ISBN을 key로 저장한다. 반환된 link도 Book 생성 때 저장하지 않는다. (`backend/book/models.py:9`, `backend/book/services.py:27-38`, `backend/review/views.py:26-44`)
- **검색 handler 중복**: 첫 블록은 query, 둘째는 q를 사용하나 서버는 query만 읽는다. 정상 query 경로는 동작 가능한 연결이며 항상 실패하지 않는다. q 단독은 계약이 다르고, query+q는 응답 순서에 따라 오류가 결과를 덮는 것을 합성 fixture로 확인했다. (`frontend/scripts/search.js:19-68,71-105`, `backend/book/views.py:15-17`)

네이버 공식 문서에서 일반 `book.json` 검색의 `query`는 필수이며, `d_isbn`은 별도 상세 검색 `book_adv.xml`의 파라미터로 설명된다. 현재 추천 ISBN helper는 일반 URL에 d_isbn만 보내므로 명세상 URL/파라미터 조합이 맞지 않는다. **실제 네이버 오류 코드·현재 키의 유효성을 측정한 결과는 아니다.** 수정 시 상세 XML 계약/파싱을 사용하거나 일반 query 검색 후 ISBN 일치 검증 등 명시적인 경로를 선택해야 한다. (`backend/dadokdadok/settings.py:133`, `backend/recommendation/services.py:60-66`)[1]

## 6. 리뷰 CRUD·좋아요·댓글

### 6.1 리뷰 및 서재

- 생성 시 서버가 user/book을 지정하며 user+book 중복을 검사한다. 실제 DB에도 해당 unique index가 있다. 현재 사용자/책 중복 리뷰 그룹은 0이다. (`backend/review/views.py:24-46`, `backend/review/serializers.py:30-40`, `backend/review/models.py:17-21`)
- 수정/삭제의 UI 버튼을 작성자에게만 보여주는 것과 서버 권한은 별개다. 전체 queryset + IsAuthenticated만으로는 객체 소유권이 보장되지 않는다. 특히 destroy는 직접 get_object_or_404 후 삭제하므로 객체 권한 검사도 호출하지 않는다. DRF 공식 문서의 객체 권한 절차와도 구분이 필요하다. (`backend/review/views.py:14-22,48-56`, `frontend/scripts/review-detail.js:73-112`)[2]
- 내용/평점이 nullable이고 평점 범위 검증이 없다. content=None은 도서별 목록 `[:50]`에서 TypeError, rating=None은 프론트 `toFixed`에서 예외를 유발한다. **현재 로컬 리뷰 8행에는 null 내용·null 평점·0~5 밖 평점이 없으므로**, 관측된 저장 데이터 문제와 허용되는 잠재 입력 문제를 구분한다. (`backend/review/models.py:12-13`, `backend/review/serializers.py:14-24`, `backend/review/views.py:168`, `frontend/scripts/review-detail.js:127`)
- 빈 서재는 HTTP200 `{message}`를 반환하지만 프론트는 배열을 기대해 books.map 예외가 난다. 별도로 없는 write-review-btn에 addEventListener도 수행한다. (`backend/review/views.py:128-130`, `frontend/scripts/library.js:42-46,62-65`, `frontend/screen/library.html:30-40`)
- 최근 도서는 최신 리뷰를 먼저 자른 뒤 set으로 중복 제거하므로 최신 도서 순서나 필요한 도서 수가 보장되지 않는다. 프론트 reverse는 정렬 복구가 아니다. (`backend/book/views.py:58-60`, `backend/review/views.py:108-109`, `frontend/scripts/main.js:20-24`)

### 6.2 좋아요

POST 토글, user+review unique, count 반환은 구현되어 있다. 다만 처음 읽을 때 필요한 사용자별 좋아요 조회 API가 없다. 상세 응답에 `is_liked`를 넣거나 실제 liked 경로를 구현해야 한다. 이미 좋아요한 리뷰를 재진입할 때 빈 하트가 보일 수 있다. 실제 HTTP 오류 status나 동시 토글의 결과는 미측정이다. (`backend/review/views.py:59-72`, `backend/review/models.py:32-36`, `frontend/scripts/review-detail.js:132-164`)

### 6.3 댓글

POST와 공개 목록 GET은 연결되어 있고 user는 서버 request에서 지정한다. 그러나 HTML 렌더링의 안전성, 비문자열 content 입력 검증, 수정/삭제가 미완성이다. int content 합성 입력은 serializer 이전 `.strip()`에서 AttributeError를 재현했다. 삭제 코드는 생성되지 않는 버튼에 붙으며 서버에는 DELETE handler가 없다. (`backend/review/views.py:79-100`, `backend/review/serializers.py:63-71`, `frontend/scripts/review-detail.js:219-250`)

## 7. 연간·월간 독서 목표

### 7.1 연간 목표는 기간 없는 숫자 목표

Goal에는 user/total_books/read_books/is_completed만 있으며 연도·월·기간·기간별 unique가 없다. progress는 사용자의 **전기간 distinct 도서 수**를 읽고, 월별 통계는 **현재 연도 created_at 기준 리뷰 수**를 읽는다. UI의 ‘올해 읽은 수’가 서로 다른 모집단을 보여준다. 과거 독서·늦게 쓴 리뷰·재독을 정확한 독서 이벤트로 관리하지 못한다. (`backend/goal/models.py:4-12`, `backend/goal/views.py:35-49,60-83`, `backend/review/models.py:14-21`)

원본 두 메서드를 합성 ORM으로 실행한 부모 probe에서 전기간 3권/당해연도 0권 조건을 넣었을 때 progress=3권, monthly=0권을 얻고, 실제 filter 인자에 연도 조건이 한쪽에만 있는 것을 확인했다. 이 숫자는 fixture이며 실제 사용자 기록이 아니다.

### 7.2 월간 목표와 월별 통계는 다름

- **월간 목표 설정/달성률은 미구현**이다.
- 월별 통계는 당해연도 12개월을 0으로 채우는 로직과 goals 화면 차트가 있다.
- 실제 완독일 필드나 과거 연도 선택은 없다. 목표가 없으면 리뷰가 있어도 통계404 경로로 간다.
- `datetime.now().year`와 Django timezone 집계의 연도 경계 정책도 확인해야 한다. 현재 host는 KST이므로 다른 OS timezone 조건에서의 위험을 현재 발생한 버그처럼 서술하지 않는다. (`backend/goal/views.py:58-83`)

### 7.3 저장 counter·달성 상태 불일치

- signal receiver 코드는 있지만 `GoalConfig.ready()` 또는 다른 source import가 없다. 표준 기동 경로에 등록 연결이 없는 정적 결함이며 실제 registry는 미검증이다. **progress는 직접 리뷰를 다시 세므로 signal 미등록이 모든 그래프 증가를 막는다는 뜻은 아니다.** (`backend/goal/apps.py:4-6`, `backend/goal/signals.py:6-34`, `backend/goal/views.py:40-49`)
- signal을 직접 호출하면 create +1/update 변화 없음/delete -1이지만 모든 사용자 목표에 적용하고 기간·backfill·동시성 처리가 없다. 자동 연결 성공 테스트가 아니다.
- total_books는 양수 제한이 없고 read_books는 writable이다. is_completed의 실제 갱신·응답 처리도 없다. 복수 목표를 만들 수 있지만 조회는 첫 목표만 선택한다. (`backend/goal/serializers.py:4-8`, `backend/goal/views.py:35,62`, `backend/goal/signals.py:18-34`)
- 로컬 DB 집계: 복수 목표 사용자 2명, 저장 read_books와 해당 사용자의 전기간 distinct 리뷰 도서 수가 다른 목표 7행, total_books<=0 목표 1행. **차이의 개별 원인이나 모든 차이가 특정 버그 때문이라는 결론은 내리지 않았다.**
- UI는 읽은 권 수 0을 '-'로 남기거나 목표0을 기본10으로 바꿀 수 있다. main의 monthlyChart canvas는 있지만 월별 요청/차트 처리는 없다. (`frontend/scripts/goals.js:23-30,40-46`, `frontend/scripts/main.js:43-90`, `frontend/screen/main.html:58-60`)

## 8. 도서 추천 시스템

현재 구현은 **‘연관 도서 검색 결과’ 제공**이며 개인화 추천 시스템은 아니다.

1. query가 있으면 네이버 검색을 그대로 실행한다.
2. isbn이 있으면 메타데이터를 얻어 출판사+저자로 다시 검색한다. 성공 경로의 외부 GET은 두 번이며 조회 실패 시 query가 같이 있어도 fallback하지 않는다.
3. 실제 상세 UI는 ISBN branch 대신 제목을 최대6자로 줄인 query branch를 사용한다.
4. user/review/rating/선호 장르·유사도·추천 점수·추천 평가, 읽은 책/현재 책 제외·중복 제거는 없다.
5. service 오류 객체를 view가 HTTP200으로 보내면 프론트는 정상 ‘추천 없음’으로 표시한다. 원본 view/프론트 격리 실행으로 재현했다.
6. display의 타입·범위 검증이 없어 문자열abc는500, 음수/과대한 값은 upstream으로 전달되는 경로가 있다. 실제 upstream 거절 결과는 확인하지 않았다.

근거: `backend/recommendation/services.py:17-53,60-77`, `backend/recommendation/views.py:13-25`, `frontend/scripts/book-detail.js:46-47,114-158`.

기본 연관검색을 MVP 추천으로 출시할 수는 있으나, 그 경우 README·UI의 ‘리뷰 기반 맞춤 추천’ 설명을 바로잡아야 한다. 개인화를 출시 약속에 포함한다면 별도 구현·평가·cold-start 정책이 필요하다. timeout·오류 계약·최소 fallback은 어떤 범위로 출시하더라도 선행되어야 한다.

## 9. 프론트엔드·백엔드 API 연결 상태

‘호출 코드가 있음’과 ‘실제 서버 연결이 정상’은 구별했다. 아래는 소스 계약 대조 결과이며 라이브 API 상태표가 아니다.

| 프론트 소비 기능 | 요청 | 서버 연결/문제 | 핵심 근거 |
|---|---|---|---|
| 가입/로그인 | POST `/api/user/signup/`, `/api/user/login/` | 주요 method/body/응답 키 일치. refresh 소비 누락 | `backend/user/urls.py:10-11`, `frontend/scripts/login.js:30-50` |
| 내 정보/수정 | GET `/api/user/me/`, PUT `/api/user/update_profile/` | nickname/email/image 연결. password는 유효 필드 아님 | `backend/user/views.py:68-79`, `frontend/scripts/mypage_edit.js:79-100` |
| 로그아웃 | POST `/api/user/logout/` | 존재. refresh null·중복 호출·실패 세션 정책 문제 | `frontend/scripts/auth.js:29-58`, `frontend/scripts/common.js:35-62` |
| 계정 복구 | POST `/api/user/find-id/`, `/api/user/reset-password/` | 대응 기능 없음 | `frontend/scripts/find-account.js:16,46`, `backend/user/urls.py:9-17` |
| 도서 검색/상세 | GET `/api/book/search/?query=...`, `/api/book/isbn/{isbn}/` | 주요 필드 일치. q 분기·빈 결과·ISBN 예외 문제 | `backend/book/views.py:14-49`, `frontend/scripts/search.js:19-105` |
| 최근 도서 | GET `/api/book/recent-reviews/` | 연결됨. 순서 보장 없음 | `backend/book/views.py:56-61`, `frontend/scripts/main.js:9-34` |
| 서재 | GET `/api/review/library/` | 목록은 일치, 빈 응답 객체는 불일치 | `backend/review/views.py:127-149`, `frontend/scripts/library.js:42-46,69-81` |
| 도서별 리뷰 | GET `/api/review/library/{isbn}/` | 필드 일치. 외부 도서 미등록은404 경로, 익명에도 Bearer null 전송 | `backend/review/views.py:157-173`, `frontend/scripts/book-detail.js:55-83` |
| 리뷰 CRUD | GET/PUT/DELETE `/api/review/{id}/`, POST `/api/review/` | 연결됨. PUT의 isbn은 책 변경 입력이 아님. 소유자 검사 누락 | `backend/review/urls.py:8-9,33`, `backend/review/views.py:14-56` |
| 좋아요 | POST `/api/review/{id}/like/`, GET `/api/review/liked/` | 토글은 존재, liked 초기 조회 기능 없음 | `backend/review/urls.py:12`, `frontend/scripts/review-detail.js:132-164` |
| 댓글 | GET `/api/review/{id}/comments/list/`, POST/DELETE `/api/review/{id}/comments/` | GET/POST 존재, DELETE/수정 없음 | `backend/review/urls.py:13-14`, `backend/review/views.py:75-100` |
| 목표 CRUD | GET/POST `/api/goal/goal/`, PUT `/api/goal/goal/{id}/` | **중첩 goal/goal/는 실제 route와 일치**하며 오타로 판정하지 않음 | `backend/goal/urls.py:5-11`, `frontend/scripts/mypage.js:54-102` |
| 목표·월별 통계 | GET `/api/goal/progress/`, `/api/goal/monthly-progress/` | 주요 키 일치. 기간 의미 다름. FE의 goal_id는 응답에 없지만 현재 미사용 | `backend/goal/views.py:46-50,80-84`, `frontend/scripts/goals.js:23-24,51-87` |
| 추천 | GET `/api/recommendation/naver/?query=...` | 성공의 image 필드는 FE와 일치. error 객체200은 불일치 | `backend/recommendation/services.py:40-53`, `frontend/scripts/book-detail.js:133-151` |
| 프로필 이미지 | `<img src=/api/user/profile/{nickname}/>` | 해당 API는 JSON이며 이미지가 아님 | `backend/user/views.py:136-139`, `frontend/scripts/review-detail.js:117-120,222-224` |

### 공통 연결 문제

- 15개 JS 모두 `http://127.0.0.1:8000`을 포함한다. 외부 사용자의 브라우저는 사용자 자신의 loopback을 바라보므로 운영 API 주소 구성 없이는 정상 서비스 연결이 되지 않는다. 공통 API_BASE_URL/same-origin 정책이 필요하다. (`frontend/scripts/login.js:30`, `frontend/scripts/mypage.js:2`, `frontend/scripts/search.js:33`)
- 공개 도서 리뷰에도 `Bearer null`/만료 token을 보낸다. AllowAny는 잘못된 JWT 인증 header를 무시하는 정책이 아니므로 익명 열람 실패 위험이 있다. VM에서 header를 확인했으며 실제401 응답은 미측정이다. (`frontend/scripts/book-detail.js:57-68`, `backend/dadokdadok/settings.py:106-111`)
- welcome inline은 없는 logout-btn을 참조하고, 인증 확인이 들어 있는 별도 welcome.js는 로드하지 않는다. (`frontend/screen/welcome.html:20-32`, `frontend/scripts/welcome.js:1-29`)
- frontend를 HTTP document root로 간주한 로컬 HTML 자원 검사에서 참조 실패4건: `.html` 1건, login.html 1건, default_profile.png 2건. JS의 no_image.png fallback도 파일이 없다. `/scripts`, `/styles`, `/assets` 절대 경로는 frontend를 root로 제공하면 맞으므로 무조건 깨진다고 판정하지 않았다. (`frontend/screen/mypage.html:23`, `frontend/screen/mypage_edit.html:23`, `frontend/screen/review-detail.html:43,72`, `frontend/scripts/review-write.js:89-90`)

## 10. 보안·버그·미완성 기능 정리

| 우선순위 | 문제 | 근거/증거 수준 | 필요한 조치 |
|---|---|---|---|
| **P0** | 타인 리뷰 수정·삭제 차단 누락 | 정적 + 비작성자 destroy 원본 격리 재현. `backend/review/views.py:14-22,48-56` | 서버 owner permission/객체조회 일관화, 비작성자 PUT/PATCH/DELETE 거절 회귀 테스트 |
| **P0** | 저장형 XSS 경로 | 원본 댓글 HTML sink 재현, 실제 브라우저 악용 미수행. `frontend/scripts/review-detail.js:219-234` | textContent/DOM 생성, 필요한 HTML만 제한적 sanitize, URL/속성 검증, CSP 보조 방어 |
| **P0** | secret·계정/토큰 DB Git 포함 | 리터럴/추적 상태/집계 확인. 키값 미기재 | 자격정보 교체·환경 분리, DB 공유 중단, 과거 이력·유출 범위 검토 |
| **P0** | 익명 profile 이메일 노출 | 공개 view+유효 serializer 정적 대조 | public/private serializer 분리·개인정보 동의/공개 정책 |
| **P0** | 운영 설정·지원 버전 미비 | DEBUG True, wildcard hosts/CORS, 미지원 Django 계열 | 운영 설정·TLS·허용 origin/host, 지원 버전 회귀 검증 |
| **P1** | refresh·로그아웃·갱신·중복 handler | 원본 frontend VM 재현 | 인증 처리 공통화, 발급 refresh의 보관·갱신·정확한 폐기, 실패 세션 정리 |
| **P1** | 프로필 비밀번호·계정 복구 UI-only | route/serializer 부재 | 안전한 비밀번호 변경/복구 구현 또는 미완성 UI 비노출 |
| **P1** | welcome/서재 예외·빈 응답·nullable | 원본 VM/AST 재현 | DOM 방어, 응답 계약·입력 정책 통일, 정상 빈/0/오류 상태 |
| **P1** | 연간/월간 의미·counter·목표 무결성 | 코드·합성 집계·DB 집계 | 완독 이벤트/기간 모델, single source of truth, 데이터 정리 계획 |
| **P1** | 네이버 빈 결과·추천ISBN·장애 처리 | 원본 AST 재현 + 공식 명세 대조 | timeout, 검증, 빈 배열·외부 오류 분리, 올바른 endpoint/params |
| **P1** | 배포 API host·이미지·익명 header 계약 | 소스 + VM/파일 존재 검사 | 환경별 주소·static/media·공개 API 인증 정책 |
| **P1** | liked 상태·댓글 수정/삭제 누락 | 소스 정적 확인 | 약속된 기능 구현/연결 또는 범위 축소 |
| **P2** | 최근 정렬·N+1·페이지·캐시 | 정적 위험, 부하/query count 미측정 | ordered dedup, select_related/prefetch, 페이지·TTL 정책 |
| **P2** | 단순 검색을 개인화로 설명 | 구현/README 대조 | 개인화 구현·품질 평가 또는 설명 정정 |
| **P2** | 중복 클래스·죽은 코드·문서·의존성 파일 | 인벤토리/정적 확인 | 구조 정리, 실행 문서, Git hygiene, 버전 고정 |

운영 보안 설정은 개발에 편리한 값과 분리해야 한다. Django 공식 배포 체크리스트는 secret의 비공개 보관, 운영 DEBUG 비활성화, 적절한 ALLOWED_HOSTS, 로그인 서비스의 HTTPS 등을 요구한다. 이번 감사는 실제 TLS/CSP/reverse proxy/WAF 구성을 확인한 것이 아니므로 인프라에 보호가 없다고 단정하지 않는다. CORS 전체 허용 자체를 JWT 인증 우회로, JWT 헤더 API에 CSRF 토큰이 없다는 이유만으로 CSRF 취약점으로 단정하지도 않는다. (`backend/dadokdadok/settings.py:7-14,35-50,105-124`)[3]

## 11. 실제 실행한 검사·테스트

### 11.1 환경과 결과

점검한 인터프리터는 `/usr/bin/python3` 3.9.6, Homebrew Python 3.14.7, Hermes 도구 Python이다. 이들에서 Django/DRF/SimpleJWT/corsheaders가 발견되지 않았고 프로젝트 루트/backend의 가상환경도 확인되지 않았다. 이는 **현재 발견한 실행 환경**의 결과이지 다른 머신이나 모든 가능한 인터프리터에 패키지가 없다는 주장은 아니다. Node는 v26.8.1, npm은11.19.0이었다.

| 검사 | 실행 결과 | 입증 범위 |
|---|---|---|
| Python 원문 AST parse | **61/61 문법 검사 통과** | import·Django 초기화·실행 성공이 아님 |
| `node --check` | **JS 15/15 통과** | 문법만 검증, 브라우저 동작 아님 |
| 전체 frontend 원본 VM probe | **31/31 단언 통과**: JS 문법15 + 기능/결함 단언16 | DOM/fetch/Chart/storage는 합성 substitute. 성공 경로 요청 계약과 결함 모두 포함 |
| HTML별 로그인/비로그인 mount | **26개 관측 기록** | 별도 ‘26개 E2E 통과’가 아님. 서재 로그인1·welcome2 조건에서 null DOM 예외 관측 |
| book/goal/recommendation 원본 격리 probe | **backend21 + frontend5 케이스 단언 통과** | 네이버/ORM/Response substitutes. 빈 ISBN, 오류 status, display, 기간, signal 직접 호출, 검색 race 포함 |
| 부모의 리뷰/도서/목표 원본 AST probe | **8개 관측·재현 완료** | 비작성자 destroy, permissions, content 타입/null, 빈 서재, ISBN 빈 목록, 추천 요청·기간 조건 |
| 부모의 프론트 원본 VM probe | **5개 관측·재현 완료** | 빈 서재/null 평점/HTML sink/refresh 미저장/logout null |
| 인증 원본 AST/VM 재실행 | **두 실행 exit0, 출력 조건 재확인** | 유효 serializer, create 정책 경로, refresh subject 비교 부재, double logout/welcome 결함 |
| SQLite `mode=ro` 검사 | 스키마·인덱스·집계 성공, FK 위반0 | 실제 ORM/migration 적용·쓰기 검증이 아님 |
| HTML 로컬 자원 참조 검사 | HTML13개, 누락 참조4건 | frontend document root 가정, HTTP/image loading 없음 |

상기 suite는 **같은 결함을 중복 검증하는 항목이 있으므로 합산해 독립 테스트 수나 coverage로 발표하지 않는다.** 프론트 기능 fixture의 성공 응답은 실서비스 응답이 아니라 명시적 테스트 입력이다. 자식 감사의 probe는 부모가 소스를 읽고 직접 재실행했으며 각각 exit0을 확인했다.

### 11.2 실행이 차단되거나 구성되지 않은 검사

실제로 실행한 명령과 결과:

```text
/opt/homebrew/bin/python3 -B manage.py check
/opt/homebrew/bin/python3 -B manage.py test --noinput
/opt/homebrew/bin/python3 -B manage.py makemigrations --check --dry-run
/opt/homebrew/bin/python3 -B manage.py check --deploy
→ 각각 exit 1, ModuleNotFoundError: No module named 'django'

npm run
→ exit 0, 실행 script 목록 없음
npm run start
→ exit 1, Missing script: "start"
npm run test
→ exit 1, Missing script: "test"
npm run build
→ exit 1, Missing script: "build"
```

- backend 5개 앱의 tests.py는 TestCase import + placeholder이며 `test_` 함수/메서드는 **0개**다. 이번 격리 probe는 감사자가 scratch에 만든 것으로 프로젝트 기존 회귀 테스트가 아니다. (`backend/user/tests.py:1-3`, `backend/book/tests.py:1-3`, `backend/review/tests.py:1-3`, `backend/goal/tests.py:1-3`, `backend/recommendation/tests.py:1-3`)
- `makemigrations --check`는 Django import 이전에 실패했으므로 schema drift가 없다고 판정할 수 없다. 정적 대조에서는 Review unique_together migration과 현 모델의 named UniqueConstraint 표현/related_name 차이가 있다. 실제 로컬 DB의 user+book uniqueness 자체는 유효하다. (`backend/review/migrations/0002_initial.py:19-55`, `backend/review/models.py:10-21,29-35,44-45`)
- `STATICFILES_DIRS`가 가리키는 backend/static 폴더는 없었다. 실제 Django 경고 여부는 실행이 차단되어 확인하지 않았다. (`backend/dadokdadok/settings.py:94-98`)
- 설치/데이터 변경 없는 분석 범위를 유지하기 위해 패키지 설치·DB migration·실제 서버 시작으로 우회하지 않았다. 대신 stdlib AST와 Node VM의 원본 코드 실행으로 좁은 결함을 검증했다.

### 11.3 테스트하지 못한 항목과 이유

| 항목 | 상태 | 이유/다음 검증 |
|---|---|---|
| 실제 signup/login/refresh/blacklist·비밀번호 정책 | **검증 필요** | Django/DRF/SimpleJWT 런타임 없음. 격리 전용 DB·승인된 의존성 환경에서 검증 필요 |
| ORM 기반 review/like/comment/goal CRUD·권한 | **검증 필요** | 앱 미기동, 실제 쓰기 미수행. 특히 사용자A/B 권한 테스트 필수 |
| 마이그레이션·빈 DB 최초 구축·signal registry | **검증 필요** | Django import 실패. 기존 DB를 변경하지 않음 |
| 실제 네이버 성공·인증/쿼터/timeout·결과 품질 | **검증 필요** | 보관된 키로 실외부 호출하지 않음. 공식 문서만 조회·대조 |
| 실제 브라우저/E2E·CDN/Chart·반응형/접근성·이미지 | **검증 필요** | VM은 브라우저가 아니며 실제 HTTP/렌더링·CDN 다운로드 없음 |
| XSS 실행·JWT 위조·실데이터 권한 악용 | **검증 필요** | 공격이나 실제 상태 변경은 의도적으로 수행하지 않음. 보안 전용 격리 테스트 필요 |
| 동시 가입/좋아요·목표 counter·성능·부하 | **검증 필요** | ORM·부하 환경 없음, 합성 단일 호출만 수행 |
| 실제 운영 TLS/CSP/CORS/proxy/backup·배포 | **검증 필요** | 저장소 외 운영 인프라를 조회/접속하지 않음 |
| 전체 의존성 CVE·Git 과거 이력 secret 조사 | **검증 필요** | 전체 스캔/과거 이력 조사 미수행. Django 지원 상태만 공식 확인 |

## 12. 로컬 DB 및 원본 보존 확인

### 12.1 읽기 전용 DB 관측

| 집계 | 결과 |
|---|---:|
| user / book / review | 6 / 6 / 8행 |
| comment / like / goal | 3 / 2 / 8행 |
| 동일 user+book 중복 리뷰 그룹 | 0 |
| 복수 목표 사용자 | 2명 |
| 저장 read_books와 해당 사용자 전체 distinct 리뷰 도서 수 불일치 목표 | 7행 |
| total_books<=0 목표 | 1행 |
| 비어 있지 않은 password를 가진 user | 6행 |
| outstanding token / 비어 있지 않은 token | 72 / 72행 |
| SQLite 외래키 위반 | 0 |

사용자명·이메일·비밀번호 해시·토큰·리뷰 본문은 보고서에 포함하지 않았다. 사용자/토큰 데이터가 테스트용인지 실사용자인지, 토큰이 현재 유효한지는 판단하지 않았다. FK 위반0이나 기존 데이터 존재는 기능 E2E 성공 증거가 아니다.

### 12.2 보존과 감사 산출물

- 감사 전 원본146개 파일의 SHA-256을 비교해 **변경0·누락0**을 확인했다. source/settings/db.sqlite3 포함이며 의존성·bytecode 디렉터리는 해시 기준에서 제외했다.
- 시작 Git 상태는 `master...origin/master`, 기존 미추적 `.idea/.name`이었다. 기존 파일을 되돌리거나 삭제하지 않았다.
- 최종 Git 상태에서도 기존 미추적 `.idea/.name` 외 **이 보고서 추가만 존재함을 확인했다.** 기존 원본146개 파일은 해시가 일치했고 누락이 없었다.
- 상세 검증 로그·probe 코드·JSON은 `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-audit/`에 있다. 이 경로는 임시 캐시이므로 영구 보관을 보장하지 않는다. 위 테스트 결과·오류·한계는 이 보고서에도 남겼다.
- 재실행 진입점: `probes.py`, `frontend-probes.cjs`, `frontend/probe.cjs`, `domain/probe_domain.py`, `domain/probe_frontend.cjs`, `auth/isolated_probe.py`, `auth/frontend_probe.js`. 모두 실제 API/DB 쓰기 없는 격리 probe다.

## 13. 실제 서비스 출시를 위한 작업 — 중요도순

**P0는 공개 출시 전 반드시 해결해야 하는 차단 사항, P1은 약속한 MVP 기능의 정확성과 운영 검증, P2는 규모·품질 개선**으로 구분한다. 일정/공수는 실행 환경·제품 범위가 정해지지 않아 임의 산정하지 않았다.

| 순서/우선순위 | 작업 | 출시 수용 기준 |
|---|---|---|
| **1 · P0** | 비밀정보·DB 보호 및 노출 대응 | 운영 Django/JWT·네이버 키 교체·환경 분리. 공유 Git에서 DB/비밀 제거 계획과 과거 노출 범위 검토. 기존 세션 폐기 정책 확인. 보고서 작성 중 키/DB를 임의 삭제하지 않음 |
| **2 · P0** | 리뷰 객체 소유권 보호 | 사용자A로 B의 리뷰 PUT/PATCH/DELETE가403/404, 원문·B의 독서 상태 불변. 본인 CRUD는 정상. destroy에도 동일 보호 적용 |
| **3 · P0** | XSS·공개 개인정보 경계 | 댓글/리뷰/닉네임 공격 문자열이 텍스트로 표시되고 executable DOM을 만들지 않음. URL scheme/속성 안전 처리. 익명 프로필에 이메일 등 비공개 정보 없음 |
| **4 · P0** | 재현 가능한 운영 환경·보안 설정 | 지원 Django/Python 조합과 의존성 고정. prod DEBUG False, hosts/origins 최소화, HTTPS·proxy/secure-cookie 정책 점검, API 주소·static/media 제공 설정. check/check--deploy·빈 DB migration·staging smoke 결과 확보[3][4] |
| **5 · P1** | 인증·가입·프로필 흐름 완성 | 서버 비밀번호 정책, 이메일 식별/검증 정책, login→refresh→logout 일관화·중복 요청 제거. 비밀번호 변경 후 구/신 비밀번호 동작·토큰 정책 검증. 신규 사용자 welcome/서재 콘솔 오류 없음 |
| **6 · P1** | API 응답·입력·오류·이미지 계약 정리 | 빈 서재/검색은 명시적 배열/envelope, null/0/오류 표시 일관화, 공개 조회에서 Bearer null 제거. profile JSON↔image URL 정리. 네이버 timeout/정상 빈/인증·쿼터·서버 장애 구분, ISBN 결과 일치·display 범위 검증 |
| **7 · P1** | 독서 이벤트·기간 목표 모델과 데이터 정합성 | 완독일·재독 정책, 연도/월 목표 unique 정책, annual/monthly 같은 모집단. 저장 counter 제거/동기화 중 하나 선택. 기존7행 counter 차이·복수 목표·비양수 목표 정리 계획. 연도 전환/과거 기록/삭제/목표 생성 순서/동시성 회귀 테스트 |
| **8 · P1** | 미완성 기능의 출시 범위 결정·구현 | 아이디 찾기/비밀번호 재설정·liked 초기 상태·댓글 수정/삭제·월간 목표를 구현하거나 약속/화면에서 명시적으로 제외. 안전한 복구 토큰 만료·1회성·이메일·요청 제한 검증. 단순 연관검색을 개인화로 홍보하지 않음 |
| **9 · P1** | 제품 회귀 테스트·실제 통합 검증 | Django 테스트와 프론트 테스트를 저장소에 추가. 독립 테스트 DB·mock 네이버·선택적 실외부 smoke 분리. 사용자A/B 권한·signup/login/refresh/logout·검색→리뷰→서재→목표·좋아요/댓글·빈/오류 흐름을 실제 브라우저에서 통과. CI 재현 가능 |
| **10 · P1** | 운영·개인정보·남용 대응 | 로그인/가입/복구·공개 네이버 프록시 rate limit. 에러/응답 지연·쿼터 모니터링, 알림, DB 백업 및 복구 연습, 계정삭제·보관 정책, 리뷰/댓글 신고·운영 처리 범위 정의 |
| **11 · P2** | 성능·확장·추천 품질 | 검색 pagination/metadata·TTL/refresh, stable 최신 도서 dedup/정렬, query count 측정 후 N+1 개선, 부하·동시성 검증. 개인화가 필요하면 cold-start·후보 제외·랭킹·평가 지표를 별도로 구현 |
| **12 · P2** | UI·구조·문서 정리 | 중복 serializer/handler·미연결 welcome.js/죽은 코드 정리, main 월별 차트·0/초과 표시·누락 자원 수정, CDN 버전 고정, 반응형/접근성·오류 안내, 실제 스택/실행 명령으로 README 갱신, Git hygiene |

### 최종 출시 판정 게이트

- [ ] P0 보안·개인정보·환경 문제 해결 및 회귀 테스트 확보
- [ ] 선택한 MVP 범위와 구현/미구현 화면·문서가 일치
- [ ] 신규 계정부터 검색→독서 기록→공유→목표까지 실제 E2E 성공
- [ ] 사용자A/B 권한·refresh 폐기·악성 문자열·정상 빈/오류·연도 경계 테스트 성공
- [ ] 승인된 키·staging에서 네이버 성공 및 오류 대응 확인
- [ ] 지원 환경의 의존성·migration·배포·백업/복구·모니터링 재현

**현재는 이 게이트를 통과했다고 볼 수 없다.** 위 보고서는 구현 현황과 재현된 결함을 정리한 것이며, 수정 완료나 실제 서비스 실행 성공을 선언하는 보고서가 아니다.

## Sources

[1] https://developers.naver.com/docs/serviceapi/search/book/book.md
[2] https://www.django-rest-framework.org/api-guide/permissions
[3] https://docs.djangoproject.com/en/5.1/howto/deployment/checklist
[4] https://www.djangoproject.com/download
[5] https://docs.djangoproject.com/en/5.1/topics/auth/passwords
