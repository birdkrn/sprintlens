"""Confluence 스프린트 일정 HTML 파서 모듈."""

import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MatchedIssue:
    """매칭된 Jira 이슈 정보."""

    key: str
    summary: str
    status: str
    status_category: str = ""  # "done", "indeterminate", "new"
    icon_url: str = ""
    parent_key: str = ""
    parent_summary: str = ""
    resolved_date: str | None = None  # "YYYY-MM-DD"


@dataclass
class ScheduleTask:
    """개별 일감 항목."""

    title: str
    assignees: list[str] = field(default_factory=list)
    estimate_days: float = 0.0
    sub_items: list[str] = field(default_factory=list)
    matched_issues: list[MatchedIssue] = field(default_factory=list)
    match_confidence: str = ""  # "high", "medium", "low", "none"


@dataclass
class ScheduleCategory:
    """카테고리(h2) 단위 일정 그룹."""

    name: str
    tasks: list[ScheduleTask] = field(default_factory=list)

    @property
    def total_estimate(self) -> float:
        return sum(t.estimate_days for t in self.tasks)


@dataclass
class ScheduleSection:
    """섹션(h1) 단위 그룹."""

    name: str
    categories: list[ScheduleCategory] = field(default_factory=list)


@dataclass
class SprintSchedule:
    """파싱된 스프린트 일정 전체."""

    title: str
    period: str = ""
    work_days: str = ""
    members: str = ""
    target_velocity: str = ""
    sections: list[ScheduleSection] = field(default_factory=list)

    @property
    def total_estimate(self) -> float:
        return sum(
            cat.total_estimate
            for sec in self.sections
            for cat in sec.categories
        )

    @property
    def remaining_estimate(self) -> float:
        """완료되지 않은 작업의 추정일 합계를 반환한다."""
        from sprintlens.burndown import calc_done_estimate

        return self.total_estimate - calc_done_estimate(self)

    @property
    def all_assignees(self) -> list[str]:
        """모든 담당자 목록 (중복 제거, 정렬)."""
        names: set[str] = set()
        for sec in self.sections:
            for cat in sec.categories:
                for task in cat.tasks:
                    names.update(task.assignees)
        return sorted(names)

    def to_dict(self) -> dict:
        """캐시 저장을 위해 딕셔너리로 변환한다."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SprintSchedule":
        """딕셔너리에서 SprintSchedule을 복원한다."""
        sections = [
            ScheduleSection(
                name=sec["name"],
                categories=[
                    ScheduleCategory(
                        name=cat["name"],
                        tasks=[
                            ScheduleTask(
                                title=t["title"],
                                assignees=t.get("assignees", []),
                                estimate_days=t.get("estimate_days", 0.0),
                                sub_items=t.get("sub_items", []),
                                matched_issues=[
                                    MatchedIssue(**mi)
                                    for mi in t.get("matched_issues", [])
                                ],
                                match_confidence=t.get(
                                    "match_confidence", ""
                                ),
                            )
                            for t in cat.get("tasks", [])
                        ],
                    )
                    for cat in sec.get("categories", [])
                ],
            )
            for sec in data.get("sections", [])
        ]
        return cls(
            title=data.get("title", ""),
            period=data.get("period", ""),
            work_days=data.get("work_days", ""),
            members=data.get("members", ""),
            target_velocity=data.get("target_velocity", ""),
            sections=sections,
        )


# ------------------------------------------------------------------
# 파서 유틸리티
# ------------------------------------------------------------------

# (숫자) 패턴으로 추정일 추출: "(5)", "(0.5)" 등
_ESTIMATE_RE = re.compile(r"^\((\d+(?:\.\d+)?)\)\s*")

# 담당자 추출: 마지막 "- 이름1, 이름2" 패턴
_ASSIGNEE_RE = re.compile(r"\s*-\s*((?:[가-힣a-zA-Z]+(?:\s*,\s*)?)+)\s*$")


def _parse_task_text(text: str) -> ScheduleTask:
    """일감 텍스트 한 줄을 파싱한다.

    예: "(5) 기사단전 3.0 퀘스트, 시스템 - 정경수, 이진명"
    """
    text = text.strip()
    estimate = 0.0
    assignees: list[str] = []

    # 추정일 추출
    match = _ESTIMATE_RE.match(text)
    if match:
        estimate = float(match.group(1))
        text = text[match.end():]

    # 담당자 추출 (쉼표 구분 여러 명 지원)
    match = _ASSIGNEE_RE.search(text)
    if match:
        raw = match.group(1)
        assignees = [name.strip() for name in raw.split(",") if name.strip()]
        text = text[: match.start()]

    return ScheduleTask(
        title=text.strip(),
        assignees=assignees,
        estimate_days=estimate,
    )


class _ScheduleHTMLParser(HTMLParser):
    """Confluence 스프린트 일정 HTML을 파싱하는 내부 파서."""

    def __init__(self) -> None:
        super().__init__()
        self._sections: list[ScheduleSection] = []
        self._current_section: ScheduleSection | None = None
        self._current_category: ScheduleCategory | None = None
        self._overview_items: list[str] = []

        # 상태 추적
        self._current_tag: str = ""
        self._in_h1 = False
        self._in_h2 = False
        self._in_li = False
        self._li_depth = 0  # ul 중첩 깊이
        self._ul_depth = 0
        self._text_buffer: list[str] = []
        self._before_first_h2 = True  # 첫 h2 전 = 개요 li

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._current_tag = tag
        if tag == "h1":
            self._in_h1 = True
            self._text_buffer = []
        elif tag == "h2":
            self._in_h2 = True
            self._text_buffer = []
        elif tag == "ul":
            # 부모 li 안에서 자식 ul이 시작되면, 부모 li 텍스트로 task를 먼저 생성
            if (
                self._in_li
                and self._ul_depth == 1
                and self._current_category
                and not self._before_first_h2
            ):
                text = "".join(self._text_buffer).strip()
                if text:
                    task = _parse_task_text(text)
                    self._current_category.tasks.append(task)
                    self._text_buffer = []
            self._ul_depth += 1
        elif tag == "li":
            self._in_li = True
            self._li_depth = self._ul_depth
            self._text_buffer = []
        elif tag == "time":
            for name, value in attrs:
                if name == "datetime" and value:
                    self._text_buffer.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._in_h1:
            self._in_h1 = False
            name = "".join(self._text_buffer).strip()
            if name and name != "개요":
                self._finish_section()
                self._current_section = ScheduleSection(name=name)
                self._before_first_h2 = True

        elif tag == "h2" and self._in_h2:
            self._in_h2 = False
            name = "".join(self._text_buffer).strip()
            if name and self._current_section:
                self._finish_category()
                self._current_category = ScheduleCategory(name=name)
                self._before_first_h2 = False

        elif tag == "ul":
            self._ul_depth = max(0, self._ul_depth - 1)

        elif tag == "li" and self._in_li:
            self._in_li = False
            text = "".join(self._text_buffer).strip()
            if not text:
                return

            # 개요 영역의 li
            if self._current_section is None:
                self._overview_items.append(text)
                return

            # h2 이전 li면 개요 항목으로
            if self._before_first_h2:
                self._overview_items.append(text)
                return

            # 중첩 li (sub-item)
            if self._li_depth > 1 and self._current_category:
                if self._current_category.tasks:
                    self._current_category.tasks[-1].sub_items.append(text)
                return

            # 일반 task li
            if self._current_category:
                task = _parse_task_text(text)
                self._current_category.tasks.append(task)

    def handle_data(self, data: str) -> None:
        if self._in_h1 or self._in_h2 or self._in_li:
            self._text_buffer.append(data)

    def _finish_category(self) -> None:
        if self._current_category and self._current_section:
            if self._current_category.tasks:
                self._current_section.categories.append(
                    self._current_category
                )
            self._current_category = None

    def _finish_section(self) -> None:
        self._finish_category()
        if self._current_section and self._current_section.categories:
            self._sections.append(self._current_section)
        self._current_section = None

    def get_result(self) -> tuple[list[ScheduleSection], list[str]]:
        """파싱 결과를 반환한다."""
        self._finish_section()
        return self._sections, self._overview_items


def _parse_overview(items: list[str]) -> dict[str, str]:
    """개요 리스트 항목을 딕셔너리로 변환한다."""
    result: dict[str, str] = {}
    for item in items:
        # 반각(:) 또는 전각 콜론 모두 지원
        normalized = item.replace("\uff1a", ":")
        if ":" in normalized:
            key, _, value = normalized.partition(":")
            result[key.strip()] = value.strip()
    return result


def _clean_title(title: str) -> str:
    """Confluence 문서 제목에서 핵심 부분만 추출한다.

    예: "프로그램팀 2026년 3월 2회차 일정 회의" → "프로그램팀 2026년 3월 2회차"
    """
    match = re.search(r"(.+\d+회차)", title)
    if match:
        return match.group(1)
    return title


def parse_schedule_html(title: str, html: str) -> SprintSchedule:
    """Confluence 스프린트 일정 HTML을 파싱한다."""
    parser = _ScheduleHTMLParser()
    parser.feed(html)
    sections, overview_items = parser.get_result()

    overview = _parse_overview(overview_items)

    schedule = SprintSchedule(
        title=_clean_title(title),
        period=overview.get("기간", ""),
        work_days=overview.get("작업일", ""),
        members=overview.get("인원", ""),
        target_velocity=overview.get("목표 속도", ""),
        sections=sections,
    )

    logger.info(
        "일정 파싱 완료: 섹션 %d개, 총 추정일 %.1f일",
        len(sections),
        schedule.total_estimate,
    )
    return schedule
