"""schedule_parser 모듈 테스트."""

from sprintlens.schedule_parser import (
    SprintSchedule,
    _parse_task_text,
    parse_schedule_html,
)

# 실제 Confluence에서 가져온 HTML과 동일한 구조의 테스트 데이터
SAMPLE_HTML = """
<h1>개요</h1>
<ul>
    <li>기간 : <time datetime="2026-03-16" /> ~ <time datetime="2026-03-27" /></li>
    <li>작업일 : 10일</li>
    <li>인원 : 7명</li>
    <li>목표 속도 : 50.6% (41/70)</li>
</ul>
<h1>세부 일정</h1>
<h2>기사단전 3.0</h2>
<ul>
    <li>(5) 기사단전 3.0 퀘스트, 시스템 - 정경수</li>
    <li>(1) 기사단전 시즌 퀘스트 테이블 - 이진명</li>
</ul>
<h2>글로벌</h2>
<ul>
    <li>(2) GMG 빌드 및 전달 - 주세영</li>
    <li>(3) GMG QA 이슈 대응 - 심민석</li>
</ul>
<h1>버퍼(계획 추정값 넘김)</h1>
<h2>추가 작업</h2>
<ul>
    <li>(5) Scene 최적화 - 정경수</li>
    <li>(3) GM 엔진 업데이트(3) - 주세영
        <ul>
            <li>빌드 test - 2</li>
            <li>릴리즈 빌드 및 이슈 대응</li>
        </ul>
    </li>
</ul>
"""


class TestParseTaskText:
    """_parse_task_text 테스트."""

    def test_추정일과_담당자가_있는_일감(self):
        task = _parse_task_text("(5) 기사단전 3.0 퀘스트 - 정경수")
        assert task.estimate_days == 5.0
        assert task.title == "기사단전 3.0 퀘스트"
        assert task.assignee == "정경수"

    def test_소수점_추정일(self):
        task = _parse_task_text("(0.5) 이벤트 상단 재화 표시 - 장준혁")
        assert task.estimate_days == 0.5
        assert task.assignee == "장준혁"

    def test_추정일_없는_일감(self):
        task = _parse_task_text("버그 수정 - 김철수")
        assert task.estimate_days == 0.0
        assert task.assignee == "김철수"

    def test_담당자_없는_일감(self):
        task = _parse_task_text("(2) 기능 개발")
        assert task.estimate_days == 2.0
        assert task.assignee == ""
        assert task.title == "기능 개발"


class TestParseScheduleHtml:
    """parse_schedule_html 테스트."""

    def test_전체_파싱(self):
        result = parse_schedule_html("테스트 일정", SAMPLE_HTML)
        assert isinstance(result, SprintSchedule)
        assert result.title == "테스트 일정"

    def test_개요_파싱(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        assert result.work_days == "10일"
        assert result.members == "7명"
        assert "50.6%" in result.target_velocity

    def test_기간_파싱(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        assert "2026-03-16" in result.period
        assert "2026-03-27" in result.period

    def test_섹션_파싱(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        assert len(result.sections) == 2
        assert result.sections[0].name == "세부 일정"
        assert result.sections[1].name == "버퍼(계획 추정값 넘김)"

    def test_카테고리_파싱(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        section = result.sections[0]
        assert len(section.categories) == 2
        assert section.categories[0].name == "기사단전 3.0"
        assert section.categories[1].name == "글로벌"

    def test_일감_파싱(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        tasks = result.sections[0].categories[0].tasks
        assert len(tasks) == 2
        assert tasks[0].estimate_days == 5.0
        assert tasks[0].assignee == "정경수"

    def test_하위_항목_파싱(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        buffer_tasks = result.sections[1].categories[0].tasks
        engine_task = buffer_tasks[1]
        assert len(engine_task.sub_items) == 2
        assert "빌드 test" in engine_task.sub_items[0]

    def test_총_추정일(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        assert result.total_estimate == 19.0  # 5+1+2+3+5+3

    def test_담당자_목록(self):
        result = parse_schedule_html("테스트", SAMPLE_HTML)
        assignees = result.all_assignees
        assert "정경수" in assignees
        assert "주세영" in assignees
        assert len(assignees) == 4

    def test_빈_HTML(self):
        result = parse_schedule_html("빈 일정", "")
        assert result.sections == []
        assert result.total_estimate == 0.0
