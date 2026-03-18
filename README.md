# SprintLens

프로그램팀 스프린트 일정 진행상황 리포트 웹 서비스

## 주요 기능

- 지라 스프린트 일감 현황을 웹 페이지에서 실시간 확인
- 담당자별 / 스토리별 진행 상태 출력
- 컨플루언스에서 스프린트 일정 연동
- 매일 아침 슬랙으로 리포트 자동 발송 (보조 기능)

## 기술 스택

- Python 3.13 / Flask
- Jira & Confluence (atlassian-python-api)
- Slack Bot
- Docker

## 실행 방법

```bash
# 가상환경 생성 및 의존성 설치
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 환경 변수 설정
cp .env.example .env
# .env 파일에 Jira/Confluence/Slack 접속 정보 입력

# 실행
python app.py
```

## Docker

```bash
docker-compose up --build
```
