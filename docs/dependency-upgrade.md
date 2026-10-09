# 지원 의존성 업데이트 — 검증 및 적용

기준일: 2026-10-09 (KST). `backend/requirements.txt`에 검증된 Django 5.2.18 및 호환·보안 수정 pin을 적용했다. Django/DRF 스택, 원본 DB, 운영 자격정보와 기존 `.venv-runtime`은 유지했다.

이 문서는 지원 의존성 적용 단계의 검증 기록이다. 후속 코드 수정과 현재 backend139/frontend112/실제 Chromium33 및 독립 재리뷰 결과는 `completion-reverification.md`를 따른다. 아래 당시 테스트 수/과거 실패 증거는 유지한다.

## 버전 선택

공식 지원 표에서 Django 5.1은 지원 종료, 5.2 LTS는 지원 대상이며 5.2.18과 2028년 4월 확장 지원 종료를 확인했다.[1]

5.2.18의 첫 PyPI 업로드는 2026-10-06T13:01:04.413659Z였다.[7]

공식 업그레이드 지침과 Python 3.12 지원을 확인했다.[2][3]

모든 13개 pin의 PyPI 파일 게시 시각·yanked 상태를 실제 설치 보고서의 artifact URL/SHA256과 대조했다. 기준일 이후 파일을 사용하지 않았다.

| 패키지 | 기존 | 적용 | 근거 |
|---|---|---|---|
| Django | 5.1.5 | 5.2.18 | 지원 LTS patch[1][7] |
| django-cors-headers | 4.6.0 | 4.7.0 | 공식 changelog의 Django 5.2 지원[5] |
| djangorestframework | 3.15.2 | 3.17.2 | 공식 release notes·배포본·audit[4][9] |
| djangorestframework_simplejwt | 5.4.0 | 5.5.1 | 배포 metadata 및 실제 JWT 계약 검증[8] |
| idna | 3.10 | 3.15 | 게시 파일 및 audit 수정 floor[10] |
| PyJWT | 2.10.1 | 2.15.1 | 게시 파일 및 audit 수정 floor[11] |
| requests | 2.32.3 | 2.33.0 | 게시 파일 및 audit 수정 floor[12] |
| sqlparse | 0.5.3 | 0.6.0 | 게시 파일 및 audit 수정 floor[13] |
| urllib3 | 2.3.0 | 2.8.0 | 게시 파일 및 audit 수정 floor[14] |

asgiref 3.8.1, certifi 2025.1.31, charset-normalizer 3.4.1, tzdata 2025.1은 resolver/audit를 만족하여 유지했다. 초기 DRF 3.16.1 후보도 audit finding으로 거절했다. Django만 올리고 알려진 취약점이 있는 HTTP/JWT/parser pin을 남기지 않았다.

## RED → GREEN / 최신 실행

날짜 고정 `tests/verify_supported_dependencies.py`는 기존 runtime에서 4개 중 3개 assertion 실패(RED), 후보에서 4개 모두 통과(GREEN)했다. 실시간 audit를 대체하는 검사는 아니다.

최초 후보 suite 120개는 성공했지만 동시 추가된 신규 도서 리뷰 계약 회귀 2개가 구현 전에 실행되어 양쪽 환경에서 122개 중 2개 실패했다. 당시 pin을 복원하고 적용을 보류했다. 이후 미등록 도서 빈 리뷰 200/[] 및 신규 도서 Naver link 보존을 수정한 안정 코드에서 부모가 재검증했다. 아래 결과로 보류 원인을 해소하고 pin을 적용했다.

| 검사 | 최신 결과 |
|---|---|
| 지원 Django 최신 suite | 130/130 PASS, exit0 (calendar5/rate설정2 회귀 추가) |
| Django check | 오류 0, exit 0 |
| makemigrations --check --dry-run | No changes detected, exit 0 |
| 실제 frontend JWT login/refresh/logout 계약 | 1/1 PASS |
| 지원 버전 acceptance | 4/4 PASS |
| pip check | No broken requirements found, exit 0 |
| 현재 pin = 실제 설치 = fresh resolver | app 13개 전부 일치, 미고정 추가 package 없음 |
| 원 DB 복사본 migrate | 기존/후보 성공, 원본 행·키·필드와 legacy NULL 보존 |
| check --deploy --fail-level WARNING | 오류·경고 0, exit 0. 실제 SMTP 연결 없음 |
| 실제 scripts/dev.py 기동 | API와 정적 화면 HTTP 200, 직접 시작한 서버/포트 종료 |

검증은 macOS arm64 / Python 3.12.15였다. scratch의 `supported-runtime`은 현재 pin, `dependency-audit-runtime`은 별도 audit 환경이다. 프로젝트에도 새 비추적 `.venv-dev`를 만들어 현재13개 pin을 설치하고 pip check/지원gate4개/전체backend123개 및 frontend75개를 통과했다. 기존 `.venv-runtime`의 Django5.1.5는 비교용으로 그대로 남겼다. 다른 checkout에서는 README대로 `.venv-dev`에 현재 requirements를 설치한다.

## Audit

별도 pip-audit 2.10.1로 PyPI advisory service와 OSV를 각각 조회했다.[6] 기존 pin은 양쪽에서 8개 package의 advisory가 있었고, 현재 pin은 각각 app 13개 전체 검사·skipped 0·알려진 advisory 0·exit 0이다. 서로 다른 DB의 결과를 합산해 고유 CVE 수라고 주장하지 않는다. advisory 0은 모든 취약점의 부재를 보장하지 않는다.

`--no-deps --disable-pip`는 별도 resolver 및 실제 설치 graph에서 모든 app transitive dependency가 13개 고정 pin에 포함됨을 먼저 확인한 뒤 사용했다. pip·선택적 Playwright는 앱 의존성과 분리했다.

## 데이터 및 승인 경계

원본 SQLite는 mode=ro로 열고 private backup을 만들었다. 기존/후보 복사본에만 migrate하여 모든 원본 테이블·행·키·원래 field 값, legacy 목표 year/month NULL, 기존 migration history의 보존을 검사했다. integrity_check와 foreign_key_check도 성공했고 원본 bytes/semantic snapshot은 동일했다. row·토큰·credentials 값은 출력하지 않았다.

원 DB 적용, 기존 세션 폐기, 키 교체, 운영 배포는 하지 않았다. 실제 Naver/SMTP, Linux/Windows resolution 및 운영 인프라는 별도 검증 대상이다.

## 재현 및 증거

일반 설치·test 환경변수·분리 DB 설정은 README를 따른다.

```bash
python3.12 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r backend/requirements.txt
.venv-dev/bin/python -m pip check
.venv-dev/bin/python -B tests/verify_supported_dependencies.py
# README의 테스트 전용 환경변수 적용 후
cd backend
../.venv-dev/bin/python -B manage.py check
../.venv-dev/bin/python -B manage.py test --noinput
../.venv-dev/bin/python -B manage.py makemigrations --check --dry-run
```

private scratch `/Users/shinsunghyun/.hermes/cache/scratch/dadokdadok-finalization/`의 최신 증거:

- `supported-parent-results.json` 및 명령별 `supported-*.log`
- `supported-app-graph.json`, `parent-resolver.json`, `parent-audit-{pypi,osv}.json`
- `supported-dev-runner-results.json`
- `dependency-upgrade/selected-release-evidence.json`, `installation-report.json`, `migration-preservation-results.json`

scratch는 자동 정리될 수 있다. 코드·최종 요약은 저장소에 남지만 가상환경·private 상세 로그의 영구 보존을 보장하지 않는다.

## Sources

[1] https://www.djangoproject.com/download
[2] https://docs.djangoproject.com/en/5.2/howto/upgrade-version
[3] https://docs.djangoproject.com/en/5.2/releases/5.2
[4] https://www.django-rest-framework.org/community/release-notes
[5] https://raw.githubusercontent.com/adamchainz/django-cors-headers/4.7.0/CHANGELOG.rst
[6] https://pypi.org/project/pip-audit
[7] https://pypi.org/pypi/Django/5.2.18/json
[8] https://pypi.org/pypi/djangorestframework_simplejwt/5.5.1/json
[9] https://pypi.org/pypi/djangorestframework/3.17.2/json
[10] https://pypi.org/pypi/idna/3.15/json
[11] https://pypi.org/pypi/PyJWT/2.15.1/json
[12] https://pypi.org/pypi/requests/2.33.0/json
[13] https://pypi.org/pypi/sqlparse/0.6.0/json
[14] https://pypi.org/pypi/urllib3/2.8.0/json
