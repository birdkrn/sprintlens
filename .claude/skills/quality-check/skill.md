---
name: quality-check
description: "SprintLens 코드 품질 검증 가이드. pytest 테스트 작성/실행, ruff 린트/포매팅, 통합 정합성 검증, 경계면 교차 비교. 테스트를 작성하거나 코드 품질을 검사할 때, 또는 변경 사항의 정합성을 검증할 때 반드시 이 스킬을 사용할 것."
---

# SprintLens 코드 품질 검증 가이드

## 테스트 실행

```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=sprintlens --cov-report=term-missing

# 특정 파일
pytest tests/test_specific.py

# 느린 테스트 제외
pytest -m "not slow"

# 통합 테스트만
pytest -m integration
```

## 린트 및 포매팅

```bash
# 린트 검사
ruff check .

# 자동 수정
ruff check --fix .

# 포매팅 검사
ruff format --check .

# 포매팅 적용
ruff format .
```

**ruff 규칙:** E, W, F, I, N, UP, B, SIM, RUF (E501 무시, 테스트 N802 무시)

## 테스트 작성 패턴

### 기본 구조

```python
import pytest
from sprintlens.module import TargetClass

class TestTargetClass:
    def test_정상_동작(self):
        # Given
        sut = TargetClass(...)

        # When
        result = sut.method(input_data)

        # Then
        assert result.field == expected_value

    def test_엣지_케이스(self):
        # Given
        sut = TargetClass(...)

        # When / Then
        with pytest.raises(ValueError):
            sut.method(invalid_data)
```

### 모킹 원칙

유닛 테스트에서만 모킹을 허용한다. 외부 API 호출을 모킹하는 패턴:

```python
from unittest.mock import MagicMock, patch

class TestJiraService:
    @patch("sprintlens.jira_service.Jira")
    def test_활성_스프린트_조회(self, mock_jira_cls):
        mock_jira = MagicMock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get.return_value = {"values": [...]}
        # ...
```

### conftest.py 패턴

```python
import pytest

@pytest.fixture
def sample_issues():
    """테스트용 이슈 목록"""
    return [IssueInfo(key="G2M-1", summary="테스트", ...)]
```

## 경계면 교차 비교 (핵심 QA)

단순 존재 확인이 아닌, 경계면을 넘나드는 데이터의 shape을 비교한다.

### 비교 대상

| 경계면 | 출력 측 | 입력 측 | 비교 항목 |
|--------|---------|---------|----------|
| 서비스→라우트 | `ReportService.generate_sprint_report()` | `routes.py` → `dashboard.html` | SprintReport 필드 |
| 파서→템플릿 | `schedule_parser.py` SprintSchedule | `schedule.html` | ScheduleTask/ScheduleCategory 속성 |
| AI매칭→파서 | `schedule_matcher.py` 매칭 결과 | `ScheduleTask.matched_issues` | MatchedIssue 필드 |
| 라우트→HTMX | `routes.py` API 응답 | `templates/` hx-get URL | 엔드포인트 URL 일치 |
| 캐시→서비스 | `CacheStore.get()` | `schedule_builder.py` | to_dict/from_dict 직렬화 왕복 |

### 검증 방법

```python
# 서비스 출력의 필드 목록
service_fields = {f.name for f in dataclasses.fields(SprintReport)}

# 템플릿이 참조하는 변수 (수동 확인 또는 Jinja2 AST 분석)
template_vars = {"sprint", "issues", "by_assignee", "by_story", "progress_percent"}

# 불일치 확인
missing = template_vars - service_fields
assert not missing, f"템플릿이 참조하지만 서비스가 제공하지 않는 필드: {missing}"
```

## 통합 검증 체크리스트

변경 사항 반영 후 확인:

1. **데이터 흐름 정합성**
   - 새 필드 추가 시: 데이터 모델 → 서비스 → 라우트 → 템플릿 전체 경로 확인
   - 필드 삭제/변경 시: 모든 참조 지점 업데이트 확인

2. **직렬화 왕복**
   - `to_dict()` → 캐시 저장 → `from_dict()` 복원 시 데이터 손실 없음
   - 새 필드 추가 시 직렬화/역직렬화 로직 업데이트 확인

3. **HTMX 라우트 일치**
   - 템플릿의 `hx-get`, `hx-post` URL이 `routes.py`의 실제 라우트와 일치
   - `hx-target` ID가 템플릿 내 실제 DOM 요소 ID와 일치

4. **에러 경로**
   - 외부 API 실패 시 사용자에게 적절한 에러 메시지 표시
   - None/빈 데이터 시 템플릿 렌더링 오류 없음
