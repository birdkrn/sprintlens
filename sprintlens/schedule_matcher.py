"""Confluence 일정과 Jira 이슈를 AI로 매칭하는 서비스 모듈."""

from __future__ import annotations

import json

from sprintlens.gemini_service import GeminiService
from sprintlens.jira_service import IssueInfo
from sprintlens.logging_config import get_logger
from sprintlens.prompt_loader import PromptLoader
from sprintlens.schedule_parser import (
    MatchedIssue,
    SprintSchedule,
)

logger = get_logger(__name__)


class ScheduleMatcher:
    """Confluence 일정과 Jira 이슈를 Gemini AI로 매칭한다."""

    def __init__(
        self,
        gemini_service: GeminiService,
        prompt_loader: PromptLoader,
    ) -> None:
        self._gemini = gemini_service
        self._prompt_loader = prompt_loader

    def match(
        self,
        schedule: SprintSchedule,
        issues: list[IssueInfo],
    ) -> SprintSchedule:
        """일정의 각 task에 관련 Jira 이슈를 매칭한다.

        SprintSchedule을 직접 수정(mutate)하여 반환한다.
        """
        schedule_text = self._format_schedule_tasks(schedule)
        issues_text = self._format_jira_issues(issues)

        prompt = self._prompt_loader.load(
            "match_schedule.txt",
            schedule_tasks=schedule_text,
            jira_issues=issues_text,
        )

        logger.info("Gemini AI로 일정-이슈 매칭 요청")
        response = self._gemini.generate_content(
            prompt,
            temperature=0.1,
            system_instruction=(
                "JSON 형식으로만 응답하세요. "
                "코드 블록(```)없이 순수 JSON 배열만 출력하세요."
            ),
        )

        matches = self._parse_response(response.text)
        self._apply_matches(schedule, matches)

        matched_count = sum(
            1
            for sec in schedule.sections
            for cat in sec.categories
            for t in cat.tasks
            if t.matched_issues
        )
        total_count = sum(
            len(cat.tasks)
            for sec in schedule.sections
            for cat in sec.categories
        )
        logger.info(
            "매칭 완료: %d/%d 일감에 Jira 이슈 매칭됨", matched_count, total_count
        )
        return schedule

    @staticmethod
    def _format_schedule_tasks(schedule: SprintSchedule) -> str:
        """일정 데이터를 Gemini 프롬프트용 텍스트로 변환한다."""
        lines: list[str] = []
        for section in schedule.sections:
            for cat in section.categories:
                lines.append(f"[{cat.name}]")
                for task in cat.tasks:
                    assignee = f" - {', '.join(task.assignees)}" if task.assignees else ""
                    lines.append(
                        f"  ({task.estimate_days}) {task.title}{assignee}"
                    )
        return "\n".join(lines)

    @staticmethod
    def _format_jira_issues(issues: list[IssueInfo]) -> str:
        """Jira 이슈 목록을 Gemini 프롬프트용 텍스트로 변환한다."""
        lines: list[str] = []
        for issue in issues:
            assignee = issue.assignee or "미배정"
            lines.append(
                f"{issue.key} | {issue.summary} | "
                f"{issue.status} ({issue.status_category}) | {assignee}"
            )
        return "\n".join(lines)

    @staticmethod
    def _parse_response(text: str) -> list[dict]:
        """Gemini 응답 텍스트에서 JSON 매칭 결과를 파싱한다."""
        cleaned = text.strip()
        # 코드 블록 제거
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 첫 줄(```json)과 마지막 줄(```) 제거
            lines = [
                line
                for line in lines
                if not line.strip().startswith("```")
            ]
            cleaned = "\n".join(lines)

        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            logger.warning("Gemini 응답 JSON 파싱 실패: %s...", cleaned[:200])
        return []

    @staticmethod
    def _apply_matches(
        schedule: SprintSchedule, matches: list[dict]
    ) -> None:
        """파싱된 매칭 결과를 SprintSchedule의 task에 적용한다."""
        # task title → task 객체 매핑 (빠른 검색용)
        task_map: dict[str, list] = {}
        for section in schedule.sections:
            for cat in section.categories:
                for task in cat.tasks:
                    key = task.title.strip().lower()
                    task_map.setdefault(key, []).append(task)

        for match in matches:
            task_title = match.get("schedule_task", "").strip().lower()
            tasks = task_map.get(task_title, [])
            if not tasks:
                # 부분 매칭 시도
                for key, candidates in task_map.items():
                    if task_title in key or key in task_title:
                        tasks = candidates
                        break

            if not tasks:
                continue

            matched_issues = [
                MatchedIssue(
                    key=issue.get("key", ""),
                    summary=issue.get("summary", ""),
                    status=issue.get("status", ""),
                    status_category=issue.get("status_category", ""),
                )
                for issue in match.get("matched_issues", [])
                if issue.get("key")
            ]
            confidence = match.get("match_confidence", "")

            for task in tasks:
                task.matched_issues = matched_issues
                task.match_confidence = confidence
