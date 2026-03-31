---
name: sprintlens-orchestrator
description: "SprintLens 에이전트 팀 오케스트레이터. 백엔드/프론트엔드/QA 에이전트를 팬아웃/팬인 패턴으로 조율하여 기능 개발, 버그 수정, 리팩토링을 수행. '팀으로 개발해줘', '에이전트 팀 실행', '하네스 실행', 'sprintlens 개발' 요청 시 이 스킬을 사용할 것."
---

# SprintLens Orchestrator

SprintLens 에이전트 팀을 조율하여 기능 개발, 버그 수정, 리팩토링을 수행하는 통합 스킬.

## 실행 모드: 에이전트 팀

## 에이전트 구성

| 팀원 | 에이전트 타입 | 역할 | 스킬 | 출력 |
|------|-------------|------|------|------|
| backend | backend-dev | 백엔드 서비스 개발 | backend-service | sprintlens/*.py |
| frontend | frontend-dev | 프론트엔드 UI 개발 | frontend-ui | templates/, routes.py |
| qa | qa-tester | 품질 검증 | quality-check | tests/*.py |

## 워크플로우

### Phase 1: 준비
1. 사용자 요청 분석 — 기능 추가 / 버그 수정 / 리팩토링 / 테스트 구분
2. 영향 범위 파악 — 백엔드만 / 프론트엔드만 / 풀스택
3. 작업 디렉토리에 `_workspace/` 생성
4. 요청 내용을 `_workspace/00_request.md`에 저장

### Phase 2: 팀 구성

1. 팀 생성:
   ```
   TeamCreate(
     team_name: "sprintlens-team",
     members: [
       {
         name: "backend",
         agent_type: "backend-dev",
         model: "opus",
         prompt: "SprintLens 백엔드 개발 담당. 작업 요청: [구체적 작업 내용]. Read('_workspace/00_request.md')로 상세 요청 확인. backend-service 스킬을 참조하여 기존 패턴을 따른다. 구현 완료 시 frontend와 qa에게 SendMessage로 알린다."
       },
       {
         name: "frontend",
         agent_type: "frontend-dev",
         model: "opus",
         prompt: "SprintLens 프론트엔드 개발 담당. 작업 요청: [구체적 작업 내용]. Read('_workspace/00_request.md')로 상세 요청 확인. frontend-ui 스킬을 참조하여 기존 패턴을 따른다. backend의 API 변경 알림을 대기하고, 완료 시 qa에게 알린다."
       },
       {
         name: "qa",
         agent_type: "qa-tester",
         model: "opus",
         prompt: "SprintLens 품질 검증 담당. 작업 요청: [구체적 작업 내용]. Read('_workspace/00_request.md')로 상세 요청 확인. quality-check 스킬을 참조. backend과 frontend의 구현 완료 알림을 받은 후 점진적으로 검증한다. 이슈 발견 시 해당 에이전트에게 SendMessage로 구체적 피드백 전달."
       }
     ]
   )
   ```

2. 작업 등록 (요청 유형에 따라 동적 구성):
   ```
   TaskCreate(tasks: [
     { title: "백엔드 구현", description: "[상세]", assignee: "backend" },
     { title: "프론트엔드 구현", description: "[상세]", assignee: "frontend", depends_on: ["백엔드 구현"] },
     { title: "테스트 작성", description: "[상세]", assignee: "qa" },
     { title: "통합 검증", description: "[상세]", assignee: "qa", depends_on: ["백엔드 구현", "프론트엔드 구현"] },
     { title: "린트 및 포매팅", description: "ruff check + format", assignee: "qa", depends_on: ["통합 검증"] }
   ])
   ```

   > 백엔드만 변경이면 frontend 작업 생략, 프론트엔드만 변경이면 backend 작업 생략.

### Phase 3: 개발 수행

**실행 방식:** 팀원들이 자체 조율

**팀원 간 통신 규칙:**
- backend이 API 변경 시 → frontend에게 SendMessage (엔드포인트, 응답 형식)
- backend 구현 완료 시 → qa에게 SendMessage (변경 파일 목록)
- frontend 구현 완료 시 → qa에게 SendMessage (변경 템플릿 목록)
- qa가 이슈 발견 시 → 해당 에이전트에게 SendMessage (코드 위치, 문제 설명)

**점진적 QA:**
- qa는 backend 완료 알림을 받으면 즉시 백엔드 코드 검증 시작
- frontend 완료를 기다리지 않고 백엔드 테스트를 먼저 작성/실행
- 양쪽 모두 완료 후 통합 정합성 검증 수행

### Phase 4: 최종 검증
1. 모든 팀원의 작업 완료 대기 (TaskGet으로 상태 확인)
2. qa의 검증 결과 확인
3. `ruff check .` 통과 확인
4. `pytest` 전체 통과 확인
5. 잔여 이슈 있으면 해당 팀원에게 수정 요청

### Phase 5: 정리
1. 팀원들에게 종료 요청 (SendMessage)
2. 팀 정리 (TeamDelete)
3. `_workspace/` 디렉토리 보존
4. 사용자에게 결과 요약:
   - 변경된 파일 목록
   - 추가/수정된 테스트 수
   - 린트/테스트 통과 여부

## 데이터 흐름

```
[리더] → TeamCreate → [backend] ←SendMessage→ [frontend]
                          │                        │
                          ↓ 완료 알림               ↓ 완료 알림
                          └────────→ [qa] ←────────┘
                                      │
                                      ↓ 이슈 피드백
                                [backend/frontend]
                                      │
                                      ↓
                               [리더: 최종 확인]
```

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| 팀원 1명 실패 | SendMessage로 상태 확인 → 재시작 또는 리더가 직접 처리 |
| qa 검증 실패 | 구체적 이슈를 담당 팀원에게 전달, 수정 후 재검증 |
| 린트/테스트 실패 | qa가 자동 수정 시도 (ruff --fix), 불가능하면 담당자에게 전달 |
| 경계면 불일치 | 양쪽 에이전트 모두에게 알림, 합의 후 수정 |

## 작업 유형별 팀 구성 가이드

| 유형 | backend | frontend | qa |
|------|---------|----------|----|
| 백엔드 기능 추가 | O | 필요시 | O |
| 프론트엔드 변경 | 필요시 | O | O |
| 풀스택 기능 | O | O | O |
| 버그 수정 | 원인에 따라 | 원인에 따라 | O |
| 테스트 보강 | - | - | O |
| 리팩토링 | O | 필요시 | O |

## 테스트 시나리오

### 정상 흐름: 새 API 엔드포인트 + UI 추가
1. 사용자가 "스프린트 목표를 대시보드에 표시해줘" 요청
2. Phase 1: 풀스택 변경으로 판단, 3명 모두 필요
3. Phase 2: 팀 구성 (backend + frontend + qa)
4. Phase 3:
   - backend이 report_service에 목표 데이터 추가 → frontend에게 알림
   - frontend이 dashboard.html에 목표 카드 추가 → qa에게 알림
   - qa가 테스트 작성 + 경계면 검증
5. Phase 4: ruff + pytest 통과 확인
6. Phase 5: 결과 요약 보고

### 에러 흐름: 경계면 불일치 발견
1. backend이 새 필드를 `sprint_goal`로 명명
2. frontend이 `goal` 변수로 참조
3. qa가 경계면 검증에서 불일치 발견
4. qa → backend + frontend 모두에게 SendMessage
5. 합의: `sprint_goal`로 통일
6. frontend이 수정 → qa 재검증 → 통과
