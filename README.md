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

## 배포 (Windows 서비스)

운영 환경에서는 [NSSM](https://nssm.cc)(Non-Sucking Service Manager)을 사용하여 Windows 서비스로 등록하여 실행한다.
서비스로 등록하면 PC 재부팅 시 자동으로 시작되며, 프로세스가 비정상 종료되어도 자동 재시작된다.

### 사전 준비

```bash
# NSSM 설치 (Chocolatey)
choco install nssm -y
```

### 서비스 등록

```bash
# 서비스 설치 (관리자 권한 필요)
nssm install SprintLens "C:\Works\sprintlens\.venv\Scripts\python.exe" "C:\Works\sprintlens\app.py"
nssm set SprintLens AppDirectory "C:\Works\sprintlens"
nssm set SprintLens DisplayName "SprintLens"
nssm set SprintLens Description "SprintLens - Sprint Progress Report Web Service"
nssm set SprintLens Start SERVICE_AUTO_START

# 로그 설정 (logs 디렉토리 미리 생성 필요)
nssm set SprintLens AppStdout "C:\Works\sprintlens\logs\service_stdout.log"
nssm set SprintLens AppStderr "C:\Works\sprintlens\logs\service_stderr.log"
nssm set SprintLens AppRotateFiles 1
nssm set SprintLens AppRotateBytes 10485760
```

### 서비스 제어

```bash
nssm start SprintLens      # 시작
nssm stop SprintLens       # 중지
nssm restart SprintLens    # 재시작
nssm status SprintLens     # 상태 확인
```

`sc` 명령이나 Windows 서비스 관리자(`services.msc`)에서도 제어할 수 있다.

```bash
sc query SprintLens         # 상태 확인
sc stop SprintLens          # 중지
sc start SprintLens         # 시작
```

### 서비스 제거

```bash
nssm stop SprintLens
nssm remove SprintLens confirm
```

### 로그 확인

서비스 실행 로그는 `logs/` 디렉토리에 저장된다.

- `logs/service_stdout.log` — 표준 출력
- `logs/service_stderr.log` — 에러 출력

로그 파일은 10MB 단위로 자동 로테이션된다.

## Docker

```bash
docker-compose up --build
```
