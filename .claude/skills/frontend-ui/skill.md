---
name: frontend-ui
description: "SprintLens 프론트엔드 UI 개발 가이드. Jinja2 템플릿, HTMX 파셜 렌더링, Tailwind CSS + DaisyUI 컴포넌트, Chart.js 시각화, 반응형 레이아웃 개발 시 반드시 이 스킬을 사용할 것. templates/, static/, routes.py 파일을 수정할 때 참조."
---

# SprintLens 프론트엔드 UI 개발 가이드

## 레이아웃 구조

```
templates/
├── base.html              # 공통 레이아웃 (Navbar + Sidebar + Main)
├── index.html             # 메인 페이지 (base.html 상속, 파셜 로딩)
└── partials/              # HTMX 파셜 템플릿
    ├── home.html          # 홈 (바로가기 카드)
    ├── dashboard.html     # 대시보드 (스프린트 현황)
    ├── dashboard_loading.html  # 대시보드 로딩 상태
    ├── schedule.html      # 프로그램팀 일정
    ├── schedule_loading.html   # 일정 로딩 상태
    └── settings.html      # 설정 화면
```

## HTMX 패턴

### 비동기 데이터 로딩 (2단계)

```html
<!-- 1단계: 로딩 화면 즉시 표시 -->
<div id="content-area"
     hx-get="/partials/dashboard/data"
     hx-trigger="load"
     hx-swap="innerHTML">
  {% include 'partials/dashboard_loading.html' %}
</div>

<!-- 2단계: 데이터 로드 완료 후 교체 -->
<!-- /partials/dashboard/data 라우트가 dashboard.html 파셜 반환 -->
```

### 사이드바 내비게이션

```html
<a hx-get="/partials/dashboard"
   hx-target="#main-content"
   hx-push-url="/dashboard"
   class="...">
  대시보드
</a>
```

### 자동 갱신

```html
<div hx-get="/partials/schedule/data"
     hx-trigger="every 300s"
     hx-swap="innerHTML">
```

### API 호출 (POST/DELETE)

```html
<button hx-post="/api/slack/test"
        hx-swap="none"
        hx-on::after-request="handleResponse(event)">
```

## DaisyUI 컴포넌트 사용

### 카드

```html
<div class="bg-base-100 rounded-2xl shadow-sm border border-base-300 p-6">
  <h3 class="text-lg font-semibold mb-4">제목</h3>
  <!-- 내용 -->
</div>
```

### 통계 (stat)

```html
<div class="stats shadow">
  <div class="stat">
    <div class="stat-title">전체 이슈</div>
    <div class="stat-value">{{ total }}</div>
    <div class="stat-desc">스프린트 내 전체 이슈</div>
  </div>
</div>
```

### 진행률 (progress)

```html
<progress class="progress progress-primary w-full"
          value="{{ percent }}" max="100"></progress>
```

### 테이블

```html
<table class="table table-sm">
  <thead><tr><th>열1</th><th>열2</th></tr></thead>
  <tbody>
    {% for item in items %}
    <tr><td>{{ item.field1 }}</td><td>{{ item.field2 }}</td></tr>
    {% endfor %}
  </tbody>
</table>
```

### 배지 (badge)

```html
<span class="badge badge-success badge-sm">완료</span>
<span class="badge badge-warning badge-sm">진행중</span>
<span class="badge badge-ghost badge-sm">대기</span>
```

## 반응형 디자인

```html
<!-- Sidebar: 모바일 숨김, 데스크톱 표시 -->
<aside class="hidden lg:block w-60">...</aside>

<!-- 그리드: 모바일 1열, 태블릿 2열, 데스크톱 3열 -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
```

## 로딩 상태 패턴

```html
<!-- 로딩 스피너 + 단계별 메시지 -->
<div class="flex flex-col items-center justify-center min-h-[400px]">
  <span class="loading loading-spinner loading-lg text-primary"></span>
  <p id="loading-msg" class="mt-4 text-base-content/60">데이터를 불러오는 중...</p>
</div>

<script>
const messages = [
  { delay: 0, text: "스프린트 조회 중..." },
  { delay: 3000, text: "이슈 수집 중..." },
  { delay: 6000, text: "리포트 생성 중..." }
];
messages.forEach(m => {
  setTimeout(() => {
    document.getElementById('loading-msg').textContent = m.text;
  }, m.delay);
});
</script>
```

## Chart.js 사용 (번다운 차트)

```html
<canvas id="burndown-chart"></canvas>
<script>
new Chart(document.getElementById('burndown-chart'), {
  type: 'line',
  data: {
    labels: {{ burndown.labels | tojson }},
    datasets: [
      { label: '이상적', data: {{ burndown.ideal | tojson }}, borderDash: [5, 5] },
      { label: '실제', data: {{ burndown.actual | tojson }} }
    ]
  }
});
</script>
```

## 새 페이지 추가 절차

1. `templates/partials/new_page.html` — 데이터 표시 파셜 생성
2. `templates/partials/new_page_loading.html` — 로딩 상태 파셜 생성
3. `sprintlens/routes.py` — 3개 라우트 추가 (페이지/파셜/데이터)
4. `app.py` — 메뉴 항목 추가 (MENU_ITEMS)
5. CSS 변경 시 `npm run css:build` 실행
