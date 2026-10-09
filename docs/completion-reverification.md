# 이전 작업 완료 여부 재검증 및 잔여 결함 수정

검증일: 2026-10-09 (KST). 대상: 기존 HTML/CSS/Vanilla JavaScript + Django/DRF 다독다독 프로젝트.

## 판정

최종 결합 실행 검증과 frontend/backend 독립 재리뷰 모두 PASS다. 기존 미완료 세션 검증과 이번 재현한 추가6건을 해결했으며, 검토한 범위에서 남은 알려진 코드 차단 결함은 없다. 로컬 코드·회귀 검증 완료이며 운영 출시나 commit/push 완료를 의미하지 않는다.

이번 요청 시작 시 `project-completion-report.md`는 세션 race B1~B4의 수정·독립 리뷰 및 최종 결합 검증을 미완료로 기록했다. 현재 소스에는 상당 부분 수정이 있었지만, 직접 재실행에서 목표 DOM 테스트 6개와 교차 탭 토큰 회전/로그아웃 1개가 실패했다. 이어 독립 리뷰에서 공개 인증 흐름 3건과 서버 quota/unique 경쟁 3건을 추가로 발견했다. 이를 회귀 테스트와 최소 수정으로 마무리했다. 과거 감사 `../PROJECT_AUDIT_2026-10-09.md`는 변경하지 않았다.

## 이번에 완료한 코드·테스트

| 항목 | 수정 및 검증 |
|---|---|
| 기존 세션 B1~B4 | 세션 epoch/owner와 화면별 guard, 지연 refresh/login/me/retry401/logout401가 신규 계정을 복원·혼합·삭제하지 않는 회귀를 확인했다. |
| 교차 탭 회전/폐기 잔여 결함 | `api.js`에 epoch별 Web Lock으로 network+commit을 조정했다. logout은 다른 탭의 회전을 기다리고 최신 refresh를 폐기한다. 잠금 해제 전에 세션을 정리하며 logout401은 잠금을 재귀 획득하지 않는다. |
| 목표 DOM 테스트 미완료 | `goals.test.cjs`의 불완전 AppAPI stub을 제거하고 실제 security.js/api.js를 실행한다. 기존 6개 기능 단언을 유지해 RED→GREEN을 확인했다. |
| R1 공개 가입 | signup에 `auth:false`를 명시했다. 만료 access/blacklist refresh가 있어도 익명 가입 한 번으로 성공하고 기존 세션을 변조하지 않는다. |
| R2 대상 계정만 reset 정리 | Django UID의 정수 사용자 ID가 요청 당시 JWT owner와 같고 epoch도 현재일 때만 세션을 지운다. 다른 B 계정, 불명확한 UID/opaque owner 및 신규 epoch는 보존한다. |
| R3 공개 reset 성공 | 공개 응답을 로그인 epoch guard로 취소하지 않는다. fetch/JSON 중 계정이 바뀌어도 실제 성공을 표시하고 소모한 폼/비밀번호를 지운다. 선택적 세션 정리 실패가 성공을 오류로 바꾸지 않는다. |
| B1 리뷰 ISBN import quota | 미등록 도서 리뷰 생성의 Naver import에도 기존 BookThrottle을 적용했다. 검색/ISBN/추천/리뷰 import의 공유 quota와 위조 XFF 거부, 429/Retry-After를 검증했다. 캐시된 도서 리뷰 CRUD에는 upstream quota를 소비하지 않는다. |
| B2 도서·리뷰 중복 insert | 기존 SQLite ISBN 충돌은 승자의 Book을 변경 없이 재사용한다. 동일 사용자·도서 리뷰 충돌은 기존 메시지의 400으로 처리하고 승자 리뷰를 보존한다. |
| B3 가입 중복 insert | 기존 username/NFKC·nickname unique 경쟁은 기존 필드 메시지/unique code의 400으로 처리하고 승자 계정을 보존한다. 이메일 schema 변경은 하지 않았다. |
| 오류 범위 | 위 unique 제약만 처리하며 무관한 실제 NOT NULL/PK IntegrityError는 삼키지 않는 negative-control 회귀를 추가했다. |
| 실행 문서 | README에 실제 native 회귀 실행과 격리 출력·테스트 메일 설정, Web Locks 지원 경계를 추가했다. 사용자 API 문서의 구 runtime 지침을 현재 `.venv-dev`로 수정했다. |

기존 스택·API 경로·성공 응답 키·CSS를 유지했다. 테스트 fixture의 matching UID/JWT를 실제 소유권 의미에 맞췄고, 익명/다른 계정 보존 단언을 추가했다. 테스트를 완화해 결함을 숨기지 않았다.

## 부모가 직접 재실행한 최종 결과

코드 수정 담당자의 자체 결과와 별개로, 양쪽 수정 종료 후 현재 결합 코드에서 다시 실행했다. 서로 다른 scope의 테스트를 합산해 하나의 E2E 총수로 주장하지 않는다.

| 검사 | 최종 실제 결과 | 범위 |
|---|---|---|
| Django 전체 suite | 139/139 PASS | 실제 ORM/APIClient, in-memory test DB, Naver mock/locmem |
| Django check | 오류 0 | 현재 `.venv-dev` |
| migration drift | No changes detected | `--check --dry-run`; 원 DB 적용 아님 |
| 새 격리 copy의 `npm ci` → `npm test` | 112/112 PASS | 추가 public-auth14 포함; 실제 HTML/scripts/DOM, fetch/Chart mock |
| 실제 Chromium HTTP E2E | 33/33 PASS | 실제 Django WSGI·JWT·분리 SQLite·정적 화면·Chart.js, Naver 상류만 mock |
| E2E 세부 | API 응답153, 캡처28, 미처리 JS 오류0 | 모바일 캡처14의 document width390px; 목표 제목/설명·댓글 컨트롤 직접 확인 |
| native 세션 회귀 | 9/9 PASS | Chromium 공유 localStorage/storage events/Web Locks, fetch fixture. HTTP E2E와 별개 |
| frontend JWT 계약 | 1/1 PASS | 실제 login→refresh→me→logout→blacklist |
| root 실행기/저장소 회귀 | 7/7 PASS | 원 DB/하드링크 거절, Git hygiene |
| 날짜 고정 dependency gate | 4/4 PASS | 현재 고정 환경 지원 floor; 실시간 audit 대체 아님 |
| Python AST / Node syntax | 89/89, 24/24 PASS | 테스트 스크립트 포함, import/브라우저 성공과 별개 |
| `git diff --check` | PASS | commit/staging 수행 없음 |
| pip check / 설치 graph | PASS, 앱 pin13개 전부 일치 | requirements와 실제 설치 대조 |
| PyPI / OSV pip-audit | 각각13개 검사·skipped0·known advisory0 | 검증일 조회; 취약점 부재 보장 아님 |
| npm audit | 알려진 advisory0 | 현재 lock을 격리 설치·audit |
| production check | 오류/경고0 | synthetic 키/host·SMTP backend 설정 import만, 발송 없음 |
| 실제 dev.py 실행 | API/정적 화면 HTTP200, 종료0 | 별도 DB, 직접 시작한 서버 종료·포트 폐쇄 |
| 원 DB backup copy migrate | PASS | 모든 원본 테이블/행/키/필드·기존 migration history·legacy 기간 NULL, integrity/FK 보존 |
| 원본 파일 보존 | 보호167개 변화0 | 원 DB·감사·기존 CSS14+additive CSS·node_modules150 |

`npm ci`의 whatwg-encoding dev 전이 의존성 deprecation 경고와 pip-audit의 hash pin 권고는 보존한다. 이를 테스트 실패나 모든 도구 경고0으로 바꿔 보고하지 않는다. 기대된 hardlink 거절·negative-control DB 오류도 제품의 정상 요청 실패와 구분한다.

## 독립 리뷰와 실패 기록

최초 독립 frontend/backend verdict는 모두 FAIL이었다. 해당 원문과 실패 evidence를 보존했다. 수정 담당자가 보고한 GREEN은 독립 승인이 아니다.

수정 후 독립 재리뷰는 양쪽 모두 `passed=true`, `security_concerns=[]`, `logic_errors=[]`다. 부모가 verdict/실행 evidence를 읽고 현재 source SHA256과 각각18/25개 reviewed manifest를 대조하여 drift0을 확인했다.

- Frontend: 독립 Chromium+실제 Django JWT/APIClient19/19 PASS, 기존 native 세션 fixture9/9 PASS, 전체 frontend112/112 PASS. 과거 공개 인증 source에서는 예상4개 실패, network lock 제거 snapshot에서는 예상4개 concurrency 실패를 재현해 negative control도 확인했다. APIClient bridge이며 backend HTTP E2E와 별개다.
- Backend: 한정25개 PASS(신규 독립12, 이전 probe scheduling 적응본4, 저장소 회귀9). 실제 승자를 패자 atomic 밖에서 autocommit해 Book201·Review/username/nickname400와 전체 승자 필드 보존을 확인했다. 무관한 실제 NOT NULL/PK6종의 오류 전파도 확인했다. 전체139/check/drift/HTTP Chromium은 위 부모 실행으로 별도 확정했다.
- 전체 부하/SQLITE_BUSY·다른 DB backend·Web Locks 없는 브라우저·운영 배포는 승인 범위에 포함하지 않는다. reviewer harness의 최초 memory/greenlet 연결, Chart SRI 대상, checksum int/float 표현 오류는 증거를 보존하고 수정한 후 전체 한정 검사를 다시 통과했다.

재현 도구의 한계/수정도 구분했다.

- native 교차 탭 테스트는 대기 중 logout Promise를 동기적으로 기다리면 refresh 해제를 못 한다. 시작만 한 뒤 살아 있는 탭의 공유 storage로 완료를 관측하도록 수정했다. 성공 navigation으로 사라지는 page-local flag를 완료 증거로 쓰지 않는다.
- 공개 가입 native probe는 성공 navigation이 기존 평가 context를 없애므로 살아 있는 탭에서 동일 성공/계정 생성 단언을 관측했다. 원래 harness 실패를 보존했다.
- unique 경쟁의 승자는 패배 insert savepoint 밖에 실제 ORM으로 저장한다. 기존 mock create 안에 가상 승자를 만드는 probe는 새 atomic에서 승자까지 rollback하므로 그대로 통과했다고 주장하지 않는다.
- DB copy verifier의 최초 실행은 실존 table `goal` 대신 추측한 `goal_goal`을 조회해 실패했다. 원본에는 쓰지 않았고 실제 모델 db_table 확인 후 새 복사본으로 모든 보존 단언을 통과했다.

## 보존·승인 경계 및 남은 작업

원본 `backend/db.sqlite3` SHA256은 시작과 최종 모두 `93613a7440f9d4845bee95c82dacde5aea6047cc4cab81cb7fbf48b38f335bae`다. 테스트/마이그레이션은 memory 또는 scratch backup copy에만 수행했다. 기존 사용자 데이터/legacy 목표를 재해석하거나 정리하지 않았다. 기존 CSS와 node_modules를 설치·교체하지 않았다. 기존 미커밋 변경사항을 reset/stash하거나 삭제하지 않았다.

남은 승인·운영 검증은 코드 검증과 분리한다.

1. 과거 Git 이력에 포함된 credential/DB 노출 대응: 실제 키 교체, 기존 세션 처리, history 정리는 별도 승인 필요.
2. 원본 DB의 새 migration 적용: 복사본 검증은 원본 변경 승인이 아니다. 백업/적용 승인 후 진행한다.
3. 실제 Naver/SMTP 전달: 승인된 테스트 자격정보·staging 검증이 필요하다. 이번 mock/locmem PASS를 실제 외부 성공으로 보고하지 않는다.
4. 운영 TLS·trusted proxy·shared cache/다중 worker 제한·static/media·배포·백업 복구·모니터링·부하 검증은 별도다. 현재 quota는 로컬 cache 기반 best-effort다.
5. 비밀번호 변경/reset/로그아웃 뒤 발급된 access의 즉시 무효화, 기존 중복 이메일 정리/DB unique 제약은 별도 정책·데이터 승인 대상이다. 기존 access는 설정된 최대1시간 동안 남을 수 있다.
6. Web Locks 없는 호스트의 동일 교차 탭 보장은 검증하지 않았다. 실제 native 검증은 secure loopback Chromium153.0.8010.12의 navigator.locks 지원 조건이다.
7. 추천의 실사용 품질·전체 접근성·픽셀 감사·다중 thread/load 검증은 이번 결정적 회귀/E2E 범위 밖이다. 좁은 모바일 차트 가독성은 추가 UX 평가 대상이며 기존 CSS 변경이나 운영 완성을 주장하지 않는다.
8. commit/push는 이번 요청에서 명시적 허가하지 않아 수행하지 않았다. 기존 index의 추적 해제와 모든 미커밋 변경을 보존했다. 배포도 하지 않았다.

## 변경 파일과 재현 증거

이번 추가 변경: frontend `api.js`, `register.js`, `find-account.js`; tests `goals.test.cjs`, `dom.test.cjs`, `native_session_races.py`, 새 `public-auth-regressions.test.cjs`; backend review views/serializers·user serializer, 새 `review/test_import_races.py`, `user/test_signup_races.py`; README·사용자 API 계약·API 개요·dependency-upgrade·frontend 초기 결과의 최신 안내·이 보고서·완료보고서 안내 갱신. 시작 snapshot 대비 기존15개 수정·새4개 추가이며 전체 경로 manifest는 아래 `final/current-manifest.json`에 남겼다. requirements/settings/migrations는 이번 추가 수정 대상이 아니다.

최종 HEAD는 시작과 동일한 `f094c504664a2c152dd8b4b13ab473be3e7d5292`이며 Git index도 byte-identical이다. 신규 파일4개의 whitespace도 별도 검사했다. `--no-index`의 정상 차이 exit1/진단없음을 실패로 오해한 최초 검사 후 의미를 구분해 재실행했다. 실제 staging/commit/push는 없었다.

기본 설치/실행/재현 명령은 `../README.md`를 따른다. 현재 app 환경은 Python3.12.15/Django5.2.18/DRF3.17.2, Node26.8.1/npm11.19.0이다. 별도 Playwright 도구는 격리 경로에서 가져왔으며 original node_modules와 app pins는 바꾸지 않았다.

private evidence root: `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-reverification/`

- `final/parent-gates.json`, `final/frontend-gates.json`, `final/browser-gates.json` 및 명령별 log
- `final/browser/run-e4f92e64028b488a8df06b36f255fb95/results.json`와 captures, `final/native-session/results.json`
- `baseline.json`, `final/syntax-preservation.json`, `migration-preservation.json`, `dev-runner.json`, `audit-gates.json`
- 최초 FAIL: `frontend-review/`, `backend-review/`; 수정 후 독립 리뷰: `frontend-rereview/`, `backend-rereview/`
- 추가 수정 RED/GREEN: `/Users/shinsunghyun/.hermes/cache/scratch/frontend-fixes/`, `/Users/shinsunghyun/.hermes/cache/scratch/backend-fixes/`

scratch는 정리될 수 있다. 원 DB 복사본·개인자료·상세 로그는 Git에 추가하지 않으며, 저장소의 테스트/요약 문서가 재현 기준이다.
