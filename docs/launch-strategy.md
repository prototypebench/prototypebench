# Launch Strategy — PrototypeBench

> **상태**: pre-launch (private repo). Phase 4 공개 베타 직전 활성화.
> **목적**: AI 코딩 벤치마크 신규 진입자로서 신뢰와 채택을 동시에 확보.

## 0. Pre-launch — 지금 해야 할 일 (4월~6월)

### 메시지 위치 정하기 (positioning)

한 문장 정의 (모든 채널에 동일하게):

> "PrototypeBench evaluates AI coding agents on **full-stack feature shipping** — like SWE-Bench, but for the modern AI-native stack (React+Vite+Tailwind / FastAPI+SQLModel) and judged by real production tests."

차별화 표 (핵심 sound bite):

| Bench | 우리와의 관계 |
|---|---|
| SWE-Bench | 같은 패턴, 다른 스택 (성숙 라이브러리 vs 모던 풀스택 앱) |
| Terminal-Bench | 다른 카테고리 (CLI vs 풀스택 product) |
| LiveBench | 모델 평가 vs 에이전트 평가 — 층위 다름 |

핵심 buzzword: **"AI-native stack"**, **"PR-mined"**, **"execution-based judge"**, **"full-stack agent benchmark"**.

### Pre-launch 자산 구축

- [ ] **공개 사이트**: `prototypebench.org` 에 minimal landing page (Astro/static).
  - Hero: "Can your agent ship a full-stack AI-native prototype?"
  - 41 instances 통계 + 라이브 update 가능한 leaderboard 자리
  - GitHub link, methodology link, contact
- [ ] **Social preview image**: 1280×640 PNG. badge / 스택 로고 / "PROTOTYPEBENCH" 워드마크.
- [ ] **Methodology paper / blog draft**: arxiv 또는 blog 형태 5-7p.
  - 동기 (왜 SWE-Bench 만으로 부족한가)
  - 큐레이션 파이프라인 (multi-source SourceConfig)
  - 스코어링 (FAIL_TO_PASS / PASS_TO_PASS, contamination tier)
  - 한계 (테스트 강도 의존, frontend 자동화 어려움)
- [ ] **Demo video** (3min): 한 PR의 end-to-end (problem statement → agent patch → score=1).
- [ ] **첫 leaderboard run**: 3-5 frontier models (Claude Opus 4.7, Sonnet 4.6, GPT-5, Gemini 3) 실 점수.
  - 비용 추정 후 실행
  - "당사자에게 불리한 결과도 공개" 약속 — 공정성 신호
- [ ] **CONTRIBUTING.md** + **CODE_OF_CONDUCT.md** + **issue/PR templates**: GitHub Community Standards 100%.
- [ ] **GitHub Releases** v1.0.0 태그: 첫 공식 corpus + harness snapshot.

## 1. Audience 분석

| Audience | 무엇이 그들을 attracted 할까 | 채널 |
|---|---|---|
| AI/ML 연구자 | RLVR / verifiable rewards / synthetic data 시각, 새로운 eval split | Twitter (researcher 영향력자), arxiv, NeurIPS/ICLR 워크숍 |
| AI eng 실무자 (Cursor/Devin/Copilot 사용자) | "내 에이전트는 이 벤치 몇점인가?" 비교 욕구 | HN, Reddit r/AICoding, dev.to, twitter |
| OSS bench 커뮤니티 (SWE-Bench 따르는) | 같은 방법론 다른 도메인, leaderboard 호환성 | Hugging Face leaderboards, awesome-lists, GitHub |
| AI infra 회사 | 자사 모델/에이전트 마케팅 자료 (PrototypeBench 점수 인용) | 직접 outreach, partnership 가능성 |
| AI 미디어 (Latent Space 등) | "frontier models compared on a fresh benchmark" 스토리 | newsletter pitch |

## 2. Launch 채널별 전략

### A. Hacker News (Show HN)

- **시점**: 첫 leaderboard 결과 + 200+ instance 도달 후.
- **제목 (안)**:
  - "Show HN: PrototypeBench – an AI coding agent benchmark for full-stack feature shipping"
  - "Show HN: We built a SWE-Bench for the modern React/FastAPI stack"
- **본문 핵심** (첫 줄로 hook):
  - 우리가 누구이고 (개인/스타트업)
  - 왜 만들었는지 (1문장)
  - 핵심 차이 (1문장)
  - 5초 demo (gif/screenshot)
  - leaderboard 첫 결과 (frontier model 비교 표)
  - 한계 (스스로 honest)
- **시점 trick**: 화요일~목요일 미국 동부 오전 7-9 PT (~한국 시각 24-2시).
- **comment 대비**: 공정성 / 오염 / 스택 편향 질문 미리 답안 준비.

### B. Twitter/X 캠페인

- **launch tweet**: 핵심 thread (8-12 tweets):
  1. Hook: "AI coding agents 가 풀스택 PR을 ship 할 수 있나? 측정해봤다."
  2. 결과 표 (Claude vs GPT vs Gemini)
  3. 우리 방법론 한 문장씩
  4. 가장 흥미로운 fail case 한 개
  5. "한 번 시도해보기" CTA + repo link
- **태그 대상** (mentioning, 공정한 인용 한해서):
  - @swyx, @karpathy, @sama, @karinanguyen_, @teknium1, @abacaj, @swyx
  - SWE-Bench 저자, Princeton NLP
  - 평가된 모델 회사들 (Anthropic, OpenAI, Google) — 결과 인용해야 정중함
- **bot 의심 받지 않게**: 진짜 thread 형태, 이미지/그래프 풍부, 답글 활발.

### C. Reddit

- **r/MachineLearning**: "[R] PrototypeBench: a SWE-Bench-style benchmark for full-stack AI coding agents"
  - rule 따라 method/results 명시 형식
  - 공정성 disclosure 첫 단락에
- **r/LocalLLaMA**: "PrototypeBench eval results — local OSS coding models on full-stack PRs"
  - OSS 모델 점수 강조 (closed model 만 있으면 보통 차감)
- **r/AICoding** / **r/ChatGPTCoding**: 사용자 관점 ("which agent is best for full-stack work?")

### D. AI/ML Newsletter Pitch

리스트 (개인 outreach):
- **Latent Space** (swyx + Alessio): "we'd like to discuss PrototypeBench launch"
- **Import AI** (Jack Clark)
- **AlphaSignal**
- **The Rundown** (Rowan)
- **TLDR AI**
- **Ben's Bites**
- **Last Week in AI**
- **MLOps Community**

각 newsletter 마다 angle 차별화:
- Latent Space: 기술 deep-dive (RLVR, contamination tier 디자인)
- AlphaSignal: 결과 비교 표 중심
- TLDR AI: 한 문장 hook + 핵심 차이

### E. Hugging Face

- **leaderboard 호스팅**: HF Spaces 에 mirror leaderboard. HF 검색 발견성 큼.
- **Dataset card**: 우리 instances.jsonl 을 HF dataset 으로 publish (`prototypebench/prototypebench-v1`).
  - 다운로드 통계 = social proof.
- **Discord** 서버에 공유.

### F. awesome-lists 침투 (long-tail SEO)

PR 보내기:
- `awesome-llm-eval` (있으면), `awesome-coding-llm`, `awesome-ai-agents`
- `awesome-fastapi`, `awesome-react`, `awesome-shadcn` (스택 매칭)
- `awesome-software-engineering-agents` (Princeton SWE-Bench 진영)

## 3. GitHub SEO (이미 적용)

| 항목 | 적용 상태 | 효과 |
|---|---|---|
| Description (키워드 풍부) | ✅ | search snippet |
| Topics (20개) | ✅ | topic browse 트래픽 |
| Homepage URL | ✅ `prototypebench.org` | trust signal |
| LICENSE (MIT) | ✅ | distribution OK 신호 |
| README badges | ✅ phase / corpus / license / stack | credibility |
| Bilingual README (en/ko) | ✅ | 한국 커뮤니티 SEO |
| Social preview image | ⏳ 디자인 필요 | Twitter/Slack share 시 thumbnail |
| Releases | ⏳ Phase 4 직전 v1.0.0 tag | "Latest release" search-prominence |
| Discussion / Wiki | ⏳ 활성화 후 community 흔적 | 활성도 신호 |
| GitHub Pages | 옵션 | 사이트 호스팅 (Astro) |

추가 SEO 액션:
- README 첫 100자에 핵심 키워드 (LLM benchmark, coding agent, full-stack, SWE-Bench-style) 자연스럽게.
- Repo URL 을 sitemap.xml 에 등록 (사이트 만들 때).
- Markdown headings 가 곧 GitHub UI navigation — h2/h3 키워드 풍부하게.
- Code search SEO: 함수/변수 이름에 도메인 키워드 (이미 `pbench`, `extract`, `score` 등 잘 명명됨).

## 4. 타이밍 (sequencing)

```
지금 (Apr) ──┬─ 200+ instance, methodology v1
              ├─ 첫 leaderboard run (4-5 모델)
              ├─ 사이트 + 소셜 프리뷰 + 데모 영상
              │
[T-2 weeks]   ├─ Newsletter pitch (Latent Space, AlphaSignal 우선)
              ├─ awesome-list PR
              │
[Launch day]  ├─ HN Show HN (화요일 오전 PT)
              ├─ Twitter thread (동시)
              ├─ Reddit r/MachineLearning + r/LocalLLaMA
              │
[T+1 week]    ├─ HF dataset publish + Spaces leaderboard
              ├─ 인터뷰 / podcast outreach
              │
[T+1 month]   └─ Quarterly held_out 첫 로테이션 발표
```

## 5. KPI (성공 지표)

| 단기 (1 month) | 중기 (3 month) | 장기 (6 month) |
|---|---|---|
| GitHub stars 1k+ | 5k+ stars | 10k+ stars |
| HF downloads 1k+ | 10k+ downloads | mainstream papers cite |
| 외부 leaderboard submission 5+ | 20+ | OSS contribution PRs 활발 |
| Twitter mentions 100+ | 500+ | newsletter 정기 인용 |

stars 가 vanity metric 이지만 AI bench 도메인 진입에는 중요. SWE-Bench 가 5k 시점에 paper community 에서 "must-cite" 가 됐음.

## 6. 위험 + 완화

- **"too small" 비판**: 41 → 200+ 도달 후 launch.
- **"vendor benchmark" 의심**: 운영 조직 명시 + 자사 모델에 불리한 결과 강조.
- **오염 의심**: contamination_tier 설계 + held-out 셋 로테이션 정책 설명.
- **스택 편향**: "v1 의 의도된 좁힘 — modern AI-native" 명시. v2 부터 다른 스택 옵션.
- **테스트 품질 비판**: PR maintainer 가 작성한 production test 라는 점 강조.

## 7. 향후 추가 source / 차별화

- **shadcn 기반 frontend OSS**: frontend pool 확장 (현재 frontend instances 0).
- **MCP-A2A 통합 평가** (Phase 5+): MCP gateway 도메인 활용.
- **partial-credit 스코어링** (PLAN.md §9): "프런트만 통과" 같은 케이스를 보상.

---

*업데이트: 2026-04-20*
