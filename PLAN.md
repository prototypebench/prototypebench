# PrototypeBench — 프로젝트 인수인계 문서

> 이 문서는 신규 프로젝트 디렉토리로 옮겨 cold start 로 이어받을 수 있도록 작성됨.
> 생성 일자: 2026-04-20

---

## 0. TL;DR

**PrototypeBench** 는 AI 에이전트의 **full-stack 제품 개발 능력** 을 평가하는 공개 벤치마크다.
타깃 스택은 **React + Vite + Tailwind + shadcn/ui (프런트)** + **FastAPI + SQLModel + Postgres (백엔드)**.
주 목적은 **Banya 에이전트의 내부 품질 개선 루프**, 공개 리더보드는 부산물.
베이스 태스크 소스는 [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template) (MIT, 42.7k stars).

**현재 상태**: 네이밍 확정, GitHub org 확보, `.org` 도메인 확보. 엔지니어링 미착수.
**다음 작업**: 태스크 큐레이션 파이프라인 (§8 Phase 1).

---

## 1. 프로젝트 정체성

| 항목 | 내용 |
|---|---|
| 이름 | **PrototypeBench** |
| 태그라인 | *"Can your agent ship a full-stack AI-native prototype?"* |
| 포지션 | AI-native full-stack agent benchmark |
| 벤치마크 이름 컨벤션 | SWE-Bench / Terminal-Bench 계열 (`-Bench` 접미사) |
| 브랜드 중립성 | Banya 이름은 의도적으로 배제 (공정성 확보) |

---

## 2. 배경 / 존재 이유

### 2.1 왜 이 스택인가

4개 컴포넌트 **모두 각 카테고리 1위** (2024 업계 서베이 기준):

| 컴포넌트 | 지표 | 출처 |
|---|---|---|
| Vite | 사용률 **78.1%**, Webpack 추월 | State of JS 2024 |
| React | 사용률 **82%** (독보적 1위) | State of JS 2024 |
| Tailwind | 사용률 **62%**, 만족도 **81%**, Bootstrap 첫 추월 | State of CSS 2024 |
| FastAPI | 사용률 **38%** (Django 35%/Flask 34% 첫 추월) | JetBrains Python Survey 2024 |
| FastAPI (ML) | **ML 엔지니어 42% 사용** | JetBrains 2024 |

Indeed "fastapi react" 직무 공고 **16,209건** (2025).

### 2.2 왜 이 포지션("AI-native full-stack")인가

- FastAPI 가 ML/AI 엔지니어 사실상 기본값 → "AI-native" 내러티브가 **데이터로 자동 정당화**.
- Next.js+tRPC 진영 (JS 단일언어 풀스택) 과 세그먼트 분리. 경쟁 아님.
- "AI 프로덕트를 만드는 사람들의 스택으로 AI 에이전트를 평가한다" — 서사적 일관성.

### 2.3 차별화 축 (기존 벤치와의 경계)

| 기존 벤치 | 측정 대상 | 한계 (PrototypeBench 가 채움) |
|---|---|---|
| SWE-Bench / SWE-Bench Lite | Django/sympy/flask 등 **성숙 라이브러리 버그픽스** | 모던 스택(FastAPI/Vite/Tailwind) 미커버, 기능 추가/풀스택 통합 평가 부재 |
| FullStackBench (ByteDance, arxiv 2412.00535) | 11개 도메인 일반 코드 품질 | 특정 모던 스택 최적화 X, 프로덕트-레벨 "ship" 평가 X |
| Terminal-Bench | 터미널 CLI 태스크 | 풀스택 제품 빌드 X |
| Web-Bench / WebArena | 브라우저 에이전트 | 코드-생성 에이전트 X |

**PrototypeBench 의 고유 축**: "모던 AI-native 스택" × "프런트↔백 통합 기능 shipping".

---

## 3. 기술 기반

### 3.1 타깃 스택 (v1)

**Frontend**:
- React + TypeScript
- **Vite** (빌드)
- **Tailwind CSS + shadcn/ui**
- TanStack Router / TanStack Query
- Axios (auto-generated OpenAPI client)
- Biome (lint/format) · Bun (pkg mgr)
- **Playwright** (E2E)

**Backend**:
- **FastAPI** + Pydantic v2
- SQLModel · SQLAlchemy
- PostgreSQL + Alembic
- **pytest**
- uv (pkg mgr)

### 3.2 태스크 베이스 repo

**[fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template)**

| 속성 | 값 |
|---|---|
| Stars | 42,731 (2026-04 기준) |
| License | MIT (재배포·가공·상업 이용 가능) |
| 최근 커밋 | 2026-04-19 (매우 활발) |
| 스택 일치도 | **완벽** (3.1 과 동일) |
| bug label merged PR | 21개 |
| feature label merged PR | ~66개 (실질 코드변경 ~30개 추정) |
| CI 테스트 | `test-backend.yml` (pytest) + `playwright.yml` (Playwright) |

**마이닝 가능 태스크 예상: 40~60개** (v1 충분).

### 3.3 대안 태스크 소스 (없음)

같은 스택(React+Vite+Tailwind+FastAPI) 으로 stars>500 인 대안 템플릿 **부재**. 사실상 유일한 현실적 베이스.

---

## 4. 확보된 자산 / 확보 필요

| 자산 | 상태 |
|---|---|
| `github.com/prototypebench` | ✅ 확보 |
| `prototypebench.org` | ✅ 확보 |
| `prototypebench.ai` | ⏳ 방어 확보 권장 (~$80/년) |
| `prototypebench.com` | ⏳ 방어 확보 권장 (~$12/년) |
| `prototypebench.dev` | 옵션 |
| `prototypebench.io` | 옵션 |
| Hugging Face org (리더보드 호스팅 시) | 미정 |
| X `@prototypebench` | 미정 (론칭 전 확보) |

---

## 5. 설계 원칙 (타협 불가)

### 5.1 공정성 (Fairness-first)
- Banya 에이전트에 **불리한 태스크도 필수 포함**. 자사 에이전트가 잘 푸는 것만 넣으면 리더보드 신뢰 즉사.
- 브랜드(Banya) 이름이 벤치에 들어가지 않음 (§1).

### 5.2 오염 대응 (Contamination mitigation)
- 베이스 repo 가 MIT 공개라 **프런티어 모델이 PR diff 를 훈련 데이터로 봤을 가능성 매우 높음**.
- 완화책:
  - (a) **cutoff 이후 PR 만** 공개 held-out 셋으로 사용
  - (b) 전체셋은 **내부 dev loop** 전용
  - (c) 버그 주입 / 스펙 변형으로 파생 태스크 생성 (v2)
- 리더보드 제출자의 모델 cutoff 날짜 공개 요구.

### 5.3 투명성
- SWE-Bench / Terminal-Bench 수준의 methodology 문서 v1 론칭 시 필수.
- 오염 대응 · 재현성 · 스코어링 로직 전부 공개.

### 5.4 주 목적 우선순위
1. **내부**: Banya 에이전트 버전 간 상대 시그널 측정
2. **외부**: 공개 리더보드 (부산물)

우선순위가 역전되면 설계 편향 발생. 내부 가치 먼저.

---

## 6. 기각된 네이밍 (재조사 방지)

모두 2026-04-20 조사, **AI eval 도메인 직접 충돌** 확인:

| 이름 | 충돌 원인 |
|---|---|
| `AINative-Bench` | arxiv 2601.09393 (CUHK, Jan 2026) + `AINativeOps/AINativeBench` GitHub + "AI-native" 최상위 버즈워드로 SEO 절망 |
| `StackBench` | [NapthaAI/openstackbench](https://github.com/NapthaAI/openstackbench) (stackbench.ai 활성) + ByteDance FullStackBench |
| `ForgeBench` | arxiv 2504.15185 (Georgia Tech) + ForgeCode (forgecode.dev, Terminal-Bench 2.0 상위) |
| `CraftBench` | craftbench.ai 활성 SaaS (2023-10~), `.com/.ai/.dev/.io` 전부 선점 |
| `FeatureBench` | arxiv 2602.10975 "FeatureBench: Benchmarking Agentic Coding" (ICLR 2026) — **완벽 동명이인** |
| `BlueprintBench` | arxiv 2509.25229 "Blueprint-Bench" (VLM 공간지능 벤치) |
| `DeliveryBench` | arxiv 2512.19234 "DeliveryBench" (VLM 에이전트 벤치, 2025-12) |
| `MissionBench` | arxiv 2504.02623 "Multi-Mission Tool Bench" 인접 + 가구 SEO 노이즈 |
| `ShipBench` | (충돌 미조사, 비영어권 어감 문제로 기각 — "ship=배" 오해) |
| `Banya-Bench` / `Banya-Stack` | 공정성 원칙 위배 (벤더명 포함) |

---

## 7. 경쟁 환경 지도

| 프로젝트 | 도메인 | 우리와의 관계 |
|---|---|---|
| SWE-Bench / SWE-Bench Lite | Python 라이브러리 버그픽스 | 상위 카테고리 내 **보완재** (다른 축) |
| Terminal-Bench | 터미널 CLI | 카테고리 다름, 네이밍 컨벤션만 참고 |
| LiveBench | LLM 멀티태스크 | 모델 평가 vs 에이전트 평가 — 층위 다름 |
| FullStackBench (ByteDance) | 일반 풀스택 코드 품질 | **가장 가까운 경쟁**, 차별점은 "모던 특정 스택 + 프로덕트 ship" |
| AINativeBench | 에이전틱 시스템 + MCP/A2A | 추상화 레벨 다름 (인프라 vs 제품) |
| NapthaAI StackBench | AI 에이전트의 라이브러리/문서 사용 능력 | 과업 유형 다름 |
| WebArena / WebBench | 브라우저 에이전트 | 카테고리 다름 |

---

## 8. 다음 작업 (Phase 별)

### Phase 1 — 태스크 큐레이션 파이프라인 ⏱ 우선 착수 권장

**목표**: `full-stack-fastapi-template` PR 40~60개를 재현 가능한 태스크 번들로 변환.

- [ ] `github.com/prototypebench/prototypebench` 메인 repo 생성 (public 예정이나 초기엔 private)
- [ ] 태스크 스키마 설계 (참고: SWE-bench 의 `instances.jsonl` 포맷):
  - `instance_id`
  - `repo` / `base_commit` / `head_commit`
  - `problem_statement` (이슈 본문 또는 PR description 에서 추출)
  - `patch` (정답 diff)
  - `test_patch` (테스트 파일 diff)
  - `FAIL_TO_PASS` / `PASS_TO_PASS` (테스트 분류)
  - `environment_setup_commit` / `uv_lock` / `bun_lockb`
- [ ] PR 크롤러 스크립트 (`gh pr list --repo fastapi/full-stack-fastapi-template --state merged --json`):
  - dependabot / chore / docs PR 필터링
  - 테스트 파일 수정 포함 PR 우선
  - closing issue 자동 링크 (취약한 경우 PR description 파싱 fallback)
- [ ] 10개 seed 태스크 수동 큐레이션 — 파이프라인 end-to-end 검증용
- [ ] 남은 30~50개 반자동 확장

**산출물**: `tasks/` 디렉토리 + `instances.jsonl`.

### Phase 2 — 하네스 (runner)

**목표**: 태스크를 실제로 에이전트에게 주고 채점하는 자동화.

- [ ] Banya-framework 의 `agent-evaluation/` SWE-bench adapter 를 참고로 **PrototypeBench 전용 runner** 작성 (코드 복사 OK, 의존성 분리 필수 — 이 프로젝트는 독립)
- [ ] 차이점 대응:
  - 이중 테스트 (pytest + Playwright) 실행
  - docker-compose 기반 DB/백/프런트 동시 기동
  - 프런트 빌드 타임 이슈 (Vite HMR, Playwright 웹서버 대기)
- [ ] 스코어링: `FAIL_TO_PASS` 전체 통과 + `PASS_TO_PASS` 미회귀 → 1점, 그 외 0점 (SWE-bench 컨벤션)
- [ ] 태스크당 trace (에이전트 행동 로그) 저장 — **실패 triage 에 필수**

### Phase 3 — 내부 베타

- [ ] Banya 에이전트 v N / v N-1 비교 평가
- [ ] 3~5개 프런티어 모델 평가 (Claude Opus 4.7, Sonnet 4.6, GPT-5, Gemini 3, 등)
- [ ] 비용 추정 필요 (40~60 태스크 × 5 모델 × 에이전트 루프 ≈ 수백~수천 달러/회차)
- [ ] 태스크별 실패 분석 → 태스크 품질 개선 (너무 쉬움/모호함/테스트 부실 제거)

### Phase 4 — 공개 베타

- [ ] `.ai` / `.com` 도메인 방어 확보
- [ ] 리더보드 사이트 (`prototypebench.org`) — 기술 선택 필요 (단순 static 이면 Astro + GitHub Pages 무난)
- [ ] Methodology 문서 공개
- [ ] 제출 양식 / 재현성 요구사항 정의
- [ ] Hacker News 론칭 포스트

### Phase 5 — 지속 운영

- [ ] 분기별 태스크 셋 업데이트 (오염 방지 + 신규 PR 반영)
- [ ] held-out 셋 로테이션
- [ ] 기여 가이드 (외부 태스크 제안 수용)

---

## 9. 열린 결정 사항 (다음 세션에서 판단)

- **태스크 스키마 최종형**: SWE-bench 포맷 그대로 vs full-stack 전용 확장 (테스트 이중화 필드 등).
- **스코어링 모델**: pass/fail 이진 vs partial credit (프런트만 맞고 백엔드 실패 같은 케이스).
- **cutoff 날짜**: 어느 모델 cutoff 기준으로 held-out 셋 나눌지. Claude Opus 4.7 cutoff (2026-01) 기준 제안.
- **리더보드 제출 방식**: fork + PR (SWE-bench 방식) vs 중앙 API (편의성).
- **에이전트 평가 비용 budget**: 회차당 예산 상한.
- **Hugging Face 리더보드 호스팅 여부**: 노출 크지만 자체 사이트 통제성 희생.
- **공개 홍보 타이밍**: 20개 태스크 beta 시 공개 vs 전체 완성 후.

---

## 10. 레퍼런스

### 주 소스
- [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template)
- [State of JS 2024 — Build Tools](https://2024.stateofjs.com/en-US/libraries/build_tools/)
- [State of JS 2024 — Front-end Frameworks](https://2024.stateofjs.com/en-US/libraries/front-end-frameworks/)
- [State of CSS 2024 — Usage](https://2024.stateofcss.com/en-US/usage/)
- [JetBrains Python Developers Survey 2024](https://lp.jetbrains.com/python-developers-survey-2024/)

### 경쟁 벤치마크
- [SWE-bench](https://www.swebench.com/) / [SWE-bench Lite](https://www.swebench.com/lite.html)
- [Terminal-Bench](https://www.tbench.ai/)
- [FullStackBench (ByteDance, arxiv 2412.00535)](https://arxiv.org/abs/2412.00535)
- [LiveBench](https://livebench.ai/)

### 기존 Banya 하네스 (참고용, 독립 프로젝트로 분리 예정)
- `banya-framework/agent-evaluation/` — SWE-bench adapter, LCB adapter

---

## 11. 인수인계 체크리스트 (다음 세션 시작 시)

- [ ] 이 문서를 신규 프로젝트 root 에 `README.md` 또는 `PLAN.md` 로 배치
- [ ] `github.com/prototypebench/prototypebench` repo 생성 및 이 문서 첫 커밋
- [ ] §8 Phase 1 에서 태스크 큐레이션 착수
- [ ] 열린 결정사항 (§9) 중 Phase 1 에 필요한 것부터 확정: 태스크 스키마

---

*Generated from Banya-framework planning session, 2026-04-20. Authoritative context lives here.*
