"""QA_GMG 대시보드 관련 라우트 모듈."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)

qa_gmg_pages = Blueprint("qa_gmg_pages", __name__)
qa_gmg_api = Blueprint("qa_gmg_api", __name__, url_prefix="/api")


def init_qa_gmg_routes(
    *,
    config,
    qa_gmg_report_service=None,
    starred_store=None,
    get_setting_fn,
) -> None:
    """QA_GMG 관련 라우트를 등록한다."""

    # ------------------------------------------------------------------
    # HTMX 파셜 라우트
    # ------------------------------------------------------------------

    @qa_gmg_pages.route("/partials/qa-gmg")
    def partials_qa_gmg():
        """HTMX 파셜: QA_GMG 대시보드 (로딩 화면)."""
        return render_template("partials/qa_gmg_loading.html", config=config)

    @qa_gmg_pages.route("/partials/qa-gmg/data")
    def partials_qa_gmg_data():
        """HTMX 파셜: QA_GMG 대시보드 데이터 (비동기 로드)."""
        report = _build_qa_gmg_report()
        starred_keys = starred_store.get_all() if starred_store else set()
        return render_template(
            "partials/qa_gmg_dashboard.html",
            report=report,
            jira_base_url=config.jira_base_url,
            starred_keys=starred_keys,
            new_issue_days=config.qa_gmg_new_issue_days,
            config=config,
        )

    # ------------------------------------------------------------------
    # API 라우트
    # ------------------------------------------------------------------

    @qa_gmg_api.route("/qa-gmg/star", methods=["POST"])
    def api_toggle_star():
        """QA_GMG 이슈 별표를 토글한다."""
        if not starred_store:
            return jsonify({"error": "별표 저장소가 초기화되지 않았습니다."}), 503
        data = request.get_json()
        if not data or not data.get("issue_key"):
            return jsonify({"error": "issue_key가 필요합니다."}), 400
        starred = starred_store.toggle(data["issue_key"])
        return jsonify({"ok": True, "starred": starred})

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def _build_qa_gmg_report():
        """QA_GMG 대시보드용 프로젝트 리포트를 생성한다."""
        if not qa_gmg_report_service:
            return None
        try:
            dev_members_str = get_setting_fn("qa_gmg_dev_members")
            dev_members = (
                tuple(
                    m.strip()
                    for m in dev_members_str.split(",")
                    if m.strip()
                )
                if dev_members_str
                else config.qa_gmg_dev_members
            )
            return qa_gmg_report_service.generate_project_report(
                config.qa_gmg_jira_project_key,
                statuses=config.qa_gmg_jql_statuses,
                dev_members=dev_members,
            )
        except Exception:
            logger.exception("QA_GMG 프로젝트 리포트 생성 실패")
            return None
