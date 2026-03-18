# SprintLens 개발 가이드

이 파일은 해당 리포지토리의 코드를 사용하여 작업할 때 Claude Code(claude.ai/code)에 지침을 제공하기 위한 문서입니다.

## 프로젝트 개요
프로그램팀 스프린트 일정 진행상황 리포트를 웹 페이지로 출력하는 서비스.
지라/컨플루언스에서 데이터를 가져와 실시간 웹 리포트 + 매일 아침 슬랙 리포트를 제공한다.


## 언어 규칙 (Language Rules)

- 모든 설명, 계획, 답변, 코드 주석은 **반드시 한국어로 작성**합니다.
- 영어로 질문받았더라도 **기본 출력 언어는 한국어**입니다.
- 전문 용어는 영어를 그대로 사용하되, 설명은 한국어로 합니다.
- 한국어 지침을 명시하지 않은 경우에도 한국어로 답변합니다.
- 위 규칙은 Codex, Claude Code 등 모든 AI 에이전트에게 **공통 적용**합니다.



## 기술 스택
- **언어:** `Python 3.13 / Flask`
- **개발 환경:** `macOS / Windows`
- **AI 모델:** `Google Gemini` (`google-genai` SDK) , `Claude Code` (`claude-api` SDK)
- **테스트 프레임워크:** `pytest`
- **린터/포매터:** `Ruff`
- **패키지 관리:** `pyproject.toml` (PEP 621)
- Jira & Confluence (사내 구축, atlassian-python-api)
- Slack Bot (보조 기능)
- Docker 배포

## Development Principles
이 프로젝트는 다음 원칙을 따릅니다:

### 핵심 개발 원칙
 - 개발 전반에 걸쳐 높은 코드 품질을 유지하세요
 
### 코드 작성 규칙
- **절대 모킹하지 않기:** 테스트 코드가 아닌 경우는 실제 동작하는 코드만 작성. 유닛 테스트에서는 모킹 허용.
- **모듈식 설계**: 설정, 서비스, 컨트롤러 등을 별도 파일로 분리
- **환경 변수 기반 설정**: 모든 민감한 정보는 환경 변수로 관리
- **포괄적인 로깅**: 구조화된 로그 출력 및 외부 라이브러리 로그 레벨 조정
- **타입 힌트**: 모든 함수에 타입 힌트 적용
- **오류 처리**: 각 레이어에서 적절한 예외 처리
- **한국어 지원**: 사용자 메시지 및 로그 메시지
- **테스트 우선:** 유닛 테스트 커버리지 80% 이상 유지
- **PEP 8 준수:** Python 공식 스타일 가이드 PEP 8을 따라 일관된 코드 작성

### 코드 품질 표준
 - 중복을 무자비하게 제거하세요
 - 명명과 구조를 통해 의도를 명확하게 표현하세요.
 - 종속성을 명시적으로 만듭니다
 - 방법을 작게 유지하고 단일 책임에 집중하세요.
 - 상태 및 부작용 최소화
 - 가능한 가장 간단한 솔루션을 사용하세요.
 - 다음 설계 윈칙 준수 : DRY(Don't Repeat Yourself), SRP(Single Responsibility Principle), OCP(Open/Closed Principle), LSP(Liskov Substitution Principle), ISP(Interface Segregation Principle), DIP(Dependency Inversion Principle)

### 좋은 코드를 위한 지침
 - 좋은 코드를 만들기 위해 최대한 노력하세요.
 - 좋은 코드의 조건은 다음과 같습니다.
   - 정확히 동작하고, 버그 없이 목적을 달성함
   - 검증 절차를 거쳐 코드가 신뢰할 수 있음을 입증함
   - 적절한 문제 해결에 초점을 맞추며, 오류 상황을 예측 가능하게 처리함
   - 단순하고 최소한의 구조로 유지보수성과 이해도를 높임
   - 테스트와 문서화가 최신 상태로 유지되어야 함
   - 미래 변경 가능성을 고려하되 불필요한 복잡성을 추가하지 않음
   - 접근성, 보안성, 확장성, 유지보수성 등 비기능적 품질 속성을 충족함

### 리팩토링 가이드라인
 - 테스트가 통과할 때만 리팩토링합니다. ("Green" 단계)
 - 적절한 이름을 사용하여 확립된 리팩토링 패턴을 사용하세요.
 - 한 번에 하나의 리팩토링 변경을 수행하세요
 - 각 리팩토링 단계 후에 테스트를 실행합니다.
 - 중복을 제거하거나 명확성을 개선하는 리팩토링을 우선시합니다.



## 개발 워크플로우 (증강 코딩 + TDD)

### Kent Beck의 증강 코딩 원칙(Augmented Coding Principles)
 - **증강 코딩(Augmented Coding) vs 바이브 코딩:** 코드 품질, 테스트, 단순성을 중시하되 AI와 협업
 - **중간 결과 관찰:** AI가 반복 동작, 요청하지 않은 기능 구현, 테스트 삭제 등의 신호를 보이면 즉시 개입
 - **설계 주도권 유지:** AI가 너무 앞서가지 않도록 개발자가 설계 방향 제시

## 특별 주의사항

### 1. 절대 하지 말 것
 - 유닛 테스트를 위한 코드가 아닌 곳에 Mock 데이터나 가짜 구현 사용

### 2. 권장사항
 - 실제 API 호출하는 코드 작성
 - 재사용 가능한 코드 설계
 - 성능 최적화 적용

### 3. 문제 해결 우선순위
 1. 실제 동작하는 해결책 찾기
 2. 기존 코드 패턴 분석 후 일관성 유지
 3. 타입 안정성 보장
 4. 테스트 가능한 구조로 설계


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


## 실행 방법

### 가상환경 설정
```bash
# 가상환경 생성
python -m venv .venv

# 활성화 (macOS/Linux)
source .venv/bin/activate

# 활성화 (Windows)
.venv\Scripts\activate
```

### 의존성 설치
```bash
pip install -e ".[dev]"
```

### 앱 실행
```bash
python app.py
```

### 테스트
```bash
pytest
```

### 린팅 및 포매팅
```bash
ruff check .                # 린트 검사
ruff check --fix .          # 린트 자동 수정
ruff format .               # 코드 포매팅
ruff format --check .       # 포매팅 검사만
```


### Docker 배포
docker-compose up --build

