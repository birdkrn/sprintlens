---
name: backend-service
description: "SprintLens 백엔드 서비스 개발 가이드. Jira Server v8.5.7 / Confluence Server v7.4.3 API 연동, Gemini AI 매칭, Flask 라우트, SQLite 저장소, APScheduler 스케줄링, Slack Webhook 개발 시 반드시 이 스킬을 사용할 것. sprintlens/ 패키지 내 Python 코드를 추가하거나 수정할 때 참조."
---

# SprintLens 백엔드 서비스 개발 가이드

## 서비스 계층 구조

```
sprintlens/
├── config.py              # Config frozen dataclass + load_config()
├── jira_service.py        # JiraService (atlassian-python-api 래핑)
├── confluence_service.py  # ConfluenceService (atlassian-python-api 래핑)
├── gemini_service.py      # GeminiService (google-genai)
├── slack_service.py       # SlackService (requests + Webhook)
├── report_service.py      # ReportService (스프린트 리포트 생성)
├── schedule_parser.py     # Confluence HTML → SprintSchedule 파싱
├── schedule_builder.py    # 통합 빌드 (Confluence→파싱→매칭→오버라이드)
├── schedule_matcher.py    # ScheduleMatcher (Gemini AI 매칭)
├── burndown.py            # 번다운 차트 계산
├── unmatched_issues.py    # 미매칭 이슈 → "추가된 일정" 섹션
├── slack_report_formatter.py  # Slack mrkdwn 메시지 포매팅
├── routes.py              # Flask 라우트 + API 엔드포인트
├── base_store.py          # SQLite3 저장소 베이스 (스레드 안전)
├── cache_store.py         # TTL 기반 캐시 (CacheStore)
├── match_store.py         # AI 매칭 결과 영구 저장 (MatchStore)
├── settings_store.py      # 웹 UI 설정 (SettingsStore)
├── manual_match_store.py  # 수동 오버라이드 (ManualMatchStore)
├── prompt_loader.py       # 프롬프트 템플릿 로더
└── scheduler.py           # APScheduler 일일 리포트
```

## API 서비스 개발 패턴

### Jira Server v8.5.7

```python
from atlassian import Jira

# Server 모드로 초기화 (cloud=False가 기본)
jira = Jira(url=base_url, username=username, password=password)

# 래퍼가 파라미터를 지원하지 않을 때 직접 호출
url = f"rest/agile/1.0/sprint/{sprint_id}/issue?startAt={start_at}&maxResults=50&expand=changelog"
response = jira.get(url)
```

**주요 API 경로:**
- 보드 스프린트: `GET /rest/agile/1.0/board/{boardId}/sprint`
- 스프린트 이슈: `GET /rest/agile/1.0/sprint/{sprintId}/issue`
- JQL 검색: `POST /rest/api/2/search`
- 이슈 상세: `GET /rest/api/2/issue/{issueKey}`

### Confluence Server v7.4.3

```python
from atlassian import Confluence

confluence = Confluence(url=base_url, username=username, password=password)

# 페이지 조회
page = confluence.get_page_by_id(page_id, expand="body.storage")
```

### Gemini AI 호출

```python
# 기존 패턴: 지수 백오프 재시도 (최대 3회)
# GeminiService._call_api_with_retry() 참조
# temperature, max_output_tokens 설정 가능
```

## 데이터 모델 패턴

모든 데이터 모델은 `@dataclass`로 정의한다:

```python
from dataclasses import dataclass

@dataclass
class NewModel:
    field1: str
    field2: int
    field3: list[str] | None = None
```

주요 모델: `SprintInfo`, `IssueInfo`, `ProjectInfo`, `PageInfo`, `SprintSchedule`, `ScheduleTask`, `ScheduleCategory`, `ScheduleSection`, `MatchedIssue`, `SprintReport`, `AssigneeReport`, `StoryReport`, `BurndownData`

## 저장소 패턴

BaseStore를 상속하여 SQLite3 저장소를 구현한다:

```python
class NewStore(BaseStore):
    def __init__(self, db_path: str) -> None:
        super().__init__(db_path, self._CREATE_TABLE_SQL)

    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS table_name (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """
```

- 스레드 안전: `threading.Lock` 사용 (BaseStore에 내장)
- 직렬화: `json.dumps/loads`로 복합 데이터 저장
- 경로: `Config.data_dir` 하위에 `.db` 파일

## Flask 라우트 패턴

```python
# 페이지 라우트: base.html에 파셜 포함
@bp.route("/new-page")
def new_page():
    return render_template("index.html", menu=menu, active="new-page")

# 파셜 라우트: HTMX 요청에 파셜 반환
@bp.route("/partials/new-page")
def partials_new_page():
    return render_template("partials/new_page_loading.html")

# 데이터 라우트: 실제 데이터 로드
@bp.route("/partials/new-page/data")
def partials_new_page_data():
    data = service.get_data()
    return render_template("partials/new_page.html", data=data)

# API 라우트: JSON 응답
@bp.route("/api/new-endpoint", methods=["POST"])
def api_new_endpoint():
    return jsonify({"status": "ok"})
```

## 캐시 전략

- **CacheStore**: TTL 기반 단기 캐시 (기본 60분). 일정 데이터, 번다운 데이터에 사용
- **MatchStore**: 해시 기반 영구 캐시. schedule_hash + issues_hash로 변경 감지. AI 매칭 결과 저장
- **SettingsStore**: DB 우선, 환경 변수 폴백

## 설정 추가 시

1. `Config` dataclass에 필드 추가
2. `load_config()`에서 환경 변수 읽기 구현
3. 필요 시 `validate_*()` 메서드에 검증 추가
4. `.env.example`에 예시 추가
