# SprintLens 개발 가이드

## 프로젝트 개요
프로그램팀 스프린트 일정 진행상황 리포트를 웹 페이지로 출력하는 서비스.
지라/컨플루언스에서 데이터를 가져와 실시간 웹 리포트 + 매일 아침 슬랙 리포트를 제공한다.

## 기술 스택
- Python 3.13 / Flask
- Jira & Confluence (사내 구축, atlassian-python-api)
- Slack Bot (보조 기능)
- Docker 배포

## 프로젝트 구조
```
sprintlens/          # 메인 패키지
  config.py          # 환경 변수 기반 설정
  logging_config.py  # 로깅 설정
  jira_service.py    # Jira API 클라이언트
  confluence_service.py  # Confluence API 클라이언트
  slack_service.py   # Slack 메시지 발송
  report_service.py  # 리포트 생성 로직
  scheduler.py       # 슬랙 리포트 스케줄러
templates/           # Flask HTML 템플릿
static/              # CSS, JS 정적 파일
tests/               # 테스트 코드
app.py               # Flask 애플리케이션 엔트리 포인트
```

## 개발 규칙
- 모든 문서와 주석은 한국어로 작성
- 전문 용어는 영어 유지
- PEP 8 준수 (ruff 사용)
- 테스트 커버리지 80% 이상 유지
- 타입 힌트 필수
- 서비스 레이어 패턴 (config, service, handler 분리)

## 실행 방법
```bash
# 로컬 개발
pip install -e ".[dev]"
python app.py

# Docker
docker-compose up --build

# 테스트
pytest

# 린트 & 포맷
ruff check .
ruff format .
```
