# CEO Strategic Verdict — Stealth Quad Ecosystem

**Date:** 2026-05-01 | **Classification:** CONFIDENTIAL | **Review Scope:** All 6 Repos

---

## 1. EXECUTIVE SUMMARY — Three Sentences

**The Stealth Quad has world-class individual components (AXPress clicks, canvas fingerprint patching, X-ray DOM capture) but operates as six disconnected repos with zero cross-repo integration, one critical security breach, and zero EUR revenue.** The architecture is SOTA in isolation but has never been validated as a working end-to-end pipeline on live heypiggy.com surveys. The competitive moat is real but narrow — Zero-Cursor-Stealing via SkyLight.framework gives 18-24 months lead — and is rapidly eroding as Patchright and Camoufox catch up on stealth capabilities.

**Overall Grade: C+ (Strong Components, Weak System)**

---

## 2. REPOSITORY SCORECARD

| #   | Repo                    | LOC Source | LOC Tests | Test Functions | CI Workflows | Production Score | Grade |
| --- | ----------------------- | ---------- | --------- | -------------- | ------------ | ---------------- | ----- |
| 1   | A2A-SIN-Worker-heypiggy | 28,700     | 12,312    | 623            | 4            | 5/10             | C     |
| 2   | stealth-runner          | 1,439      | 188       | 52             | 4            | 6/10             | B-    |
| 3   | skylight-cli            | 1,145      | —         | 1              | 5            | 7/10             | B+    |
| 4   | playstealth-cli         | 10,126     | 2,943     | 176            | 5+           | 7/10             | B+    |
| 5   | unmask-cli              | 4,172      | 612       | 37             | 8+           | 7/10             | B     |
| 6   | screen-follow           | 4,247      | —         | 0              | 5            | 4/10             | D+    |

**Total:** ~49,829 LOC source | ~16,055 LOC tests | ~889 test functions | 31+ CI workflows

---

## 3. PER-REPO DEEP AUDIT

### 3.1 A2A-SIN-Worker-heypiggy — The Brain

**What works:**

- 623 test functions — strongest test coverage in the ecosystem
- Anti-Learn/Answer-History system (persistente JSON, Option-Tracking)
- Panel-aware routing for PureSpectrum, Dynata, Sapio, Cint, Lucid
- Fail-Closed Preflight (Issue #85 hardened)
- Deterministic Answer-Router (Issue #81)
- Dashboard-Cashout-Filter (Issue #84)
- Audit-Trail (JSONL append-only)

**CRITICAL FAILURES:**

1. **SECURITY BREACH: `.env` file tracked in git with real credentials**
   - `HEYPIGGY_PASSWORD="ZOE.jerry2024"` — EXPOSED
   - `NVIDIA_API_KEY="nvapi-ARzQ..."` — EXPOSED
   - File is `git ls-files .env` confirmed tracked
   - `.gitignore` lists `.env` but file was committed BEFORE the rule
   - **ACTION: Immediate rotation of ALL exposed credentials. BFG Repo-Cleaner to purge from history.**

2. **9,137-line monolith** (`heypiggy_vision_worker.py`) — 389KB single file
   - Numbered sections (#16 PANEL-OVERRIDES, #17 ATTENTION-CHECK)
   - Impossible to test in isolation
   - Every change creates secondary damage

3. **Duplicate worker reality** — `worker/` package (21 files, 4,005 LOC) AND monolith
   - CLI entry point calls monolith anyway
   - Confuses every new developer

4. **Zero live revenue** — 0 EUR earned on heypiggy.com after weeks of development
   - Vision cost ~$0.03/call × 150 calls/survey = ~$4.50/survey
   - Typical payout: $0.50-$2.00/survey
   - **Mathematically deficit on every run**

5. **No cross-repo imports** — zero references to stealth-runner, skylight-cli, playstealth, unmask, or screen-follow in any Python file

### 3.2 stealth-runner — The Orchestrator

**What works:**

- Clean 10-state machine (IDLE → LAUNCH → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → DONE → RECOVERY)
- Anyio-based async (not asyncio — correct for macOS)
- HumanProfile with scipy.stats PDF sampling
- AuditLog with JSONL + summary
- Brain/SOTA/Architecture docs well-structured
- 38 Python modules, clean separation

**GAPS:**

- 188 LOC tests for 1,439 LOC source = 13% test density (should be 50%+)
- 52 test functions — thin for an orchestrator
- No integration tests against real CLI tools
- `sin_survey_core` (7 modules) has separate panel/error detection but no integration with A2A worker
- Tests still failing on `hypothesis` module not installed
- `pyproject.toml` required `[tool.pytest.ini_options]` fix (semicolons on one line)

### 3.3 skylight-cli — The Hands

**What works:**

- AXPress click via `AXUIElementPerformAction` — PRODUCTION READY
- SoM (Set-of-Marks) overlay rendering
- JSON stdout contract with exit codes 0-5
- VoiceOver trick for AX tree persistence
- CodeQL, SBOM, Scorecard CI
- Primer click for Chromium user-activation gate

**GAPS:**

- 1,145 LOC but only 1 test file (`SmokeTests.swift`)
- Zero unit tests for AXElementFinder, SoMOverlay, SkyLightClicker
- `Package.swift` has no version field
- README claims "0.2.1" while CLI.swift has `SKYLIGHT_VERSION = "0.2.0"` — FIXED today
- No Swift Package publishing (no tags beyond git)

### 3.4 playstealth-cli — The Mask

**What works:**

- 10,126 LOC — most mature codebase by architecture
- 176 test functions, 2,943 LOC tests
- Persona engine with strategy matrix (persona/consistent/random)
- Auto-Heal-Selector + Auto-Issue + Auto-PR via GitHub App
- Plugin scaffolder from live DOM profiling
- Patchright integration (`--tier1`)
- Human behavior simulation (cursor movements, typing rhythm)
- Retry policies per question type
- 5+ CI workflows including release-please

**GAPS:**

- Coverage gate at 33% (real measured) — should be 75%+
- 4 empty test files (#11 Resilience Engine)
- `demo_flow.py` top-level import breaks after `pipx install`
- PyPI badge shows 1.0.0 but only 0.9.0-beta released
- Language mix in CLI strings (DE/EN)
- No CAPTCHA solver integration (tracked as #27-#29)

### 3.5 unmask-cli — The Eyes

**What works:**

- 4,172 LOC TypeScript — clean module structure
- CDP network sniffing with `Fetch.*` body capture (survives navigation)
- DOM scanner with prioritized selectors (data-testid > id > aria-label > role+name > text)
- Self-heal multi-strategy resolver
- Queue strictly sequential (no Promise.all)
- JSON-RPC 2.0 server (stdio + HTTP+WebSocket)
- Replay bundles (HAR + trace.zip + screenshots + JSONL)
- 8+ CI workflows — strongest CI/CD setup

**GAPS:**

- 37 test functions for 4,172 LOC — thin coverage
- LLM layer (act/extract/observe) untested without API key
- `package-lock.json` present but `package.json` not in glob results (unusual)
- No TypeScript strict mode in tsconfig

### 3.6 screen-follow — The Memory

**What works:**

- 4,247 LOC Swift — ScreenCaptureKit integration
- CLI + menu bar app
- JSONL audit trail
- Combine-based event bus
- Lock-file IPC for CLI-GUI communication

**CRITICAL GAPS:**

- **ZERO tests** — not a single test function
- No test infrastructure at all
- 4,247 LOC of untested code in production
- Only 1 test file exists but contains 0 test functions
- This is the weakest repo by far

---

## 4. CROSS-REPO INTEGRATION — THE ELEPHANT IN THE ROOM

**Finding: There is ZERO cross-repo integration.**

```
grep for "stealth-runner|skylight-cli|playstealth|unmask-cli|screen-follow" in A2A → 0 results
grep for cross-repo imports in any repo → 0 results
```

The repos were designed to work together (the "Stealth Quad" / "Stealth Triade" architecture) but:

- `stealth-runner` imports `playstealth-cli`, `skylight-cli`, `unmask-cli` only via subprocess calls in `_launch()` and `_capture()`
- `A2A-SIN-Worker-heypiggy` has its own `opensin_bridge/` that talks to Chrome Extension directly
- `screen-follow` is standalone — no orchestration integration
- There is no unified test suite, no integration test, no E2E pipeline

**The "Stealth Quad" is a marketing concept, not a working system.**

---

## 5. COMPETITIVE LANDSCAPE 2026

### 5.1 Threat Matrix

| Competitor                  | Stars | Threat   | Our Advantage                        | Their Advantage                                |
| --------------------------- | ----- | -------- | ------------------------------------ | ---------------------------------------------- |
| **Stagehand** (Browserbase) | 12k+  | HIGH     | We have stealth, they have UX        | Funded ($28M), polished API, hosted            |
| **Browser Use**             | 60k+  | CRITICAL | We have survey-specific intelligence | Massive community, LLM-native, fastest growing |
| **Skyvern**                 | 12k+  | MEDIUM   | We have deeper stealth               | Visual AI, enterprise focus                    |
| **Nodriver**                | 8k+   | HIGH     | We have AXPress (not CDP)            | Mature, widely deployed                        |
| **Patchright**              | 8k+   | HIGH     | We have persona engine               | CDP-level patches, broader browser support     |
| **Camoufox**                | 3k+   | MEDIUM   | We have Chromium focus               | Firefox stealth is undetectable on CreepJS     |
| **CloakBrowser**            | —     | LOW      | Open source vs commercial            | C++ engine-level patches                       |
| **Botright**                | 2k+   | LOW      | We have survey routing               | CAPTCHA solver integration                     |
| **BrowserForge**            | 3k+   | LOW      | We have persona consistency          | Statistical fingerprint generation             |
| **OpenAI Operator**         | —     | CRITICAL | We have stealth                      | Massive distribution, GPT integration          |

### 5.2 Our Unique Selling Propositions (Verified)

1. **Zero-Cursor-Stealing via SkyLight.framework** — 18-24 month lead
   - CGEventPostToPid is DEAD on Chrome 148/macOS 26
   - AXPress is invisible, no cursor movement
   - No other open-source tool does this

2. **Canvas/WebGL Fingerprint Patching** — 12 month lead
   - playstealth-cli patches at JS level
   - Passes CreepJS (claimed, not verified in CI)

3. **Survey-Specific Intelligence** — UNIQUE
   - Panel-aware routing (PureSpectrum, Dynata, Sapio, Cint, Lucid)
   - Anti-Learn with persistent answer history
   - Attention-check detection heuristics
   - No competitor has this

4. **X-Ray DOM + Network Capture** — STRONG
   - Fetch.\* body capture survives navigation
   - Self-heal multi-strategy resolver
   - JSON-RPC 2.0 for any-language integration

### 5.3 Critical Competitive Gaps

| Gap                         | Severity | Competitor Has It                | Impact                         |
| --------------------------- | -------- | -------------------------------- | ------------------------------ |
| No live revenue proof       | CRITICAL | Stagehand has paying customers   | Can't claim product-market fit |
| No CreepJS CI validation    | HIGH     | Patchright passes in CI          | Stealth claims unverified      |
| No TLS/JA3 fingerprinting   | HIGH     | Camoufox has it                  | DataDome/Turnstile detection   |
| No CAPTCHA solver           | HIGH     | Botright, CloakBrowser           | Surveys with CAPTCHA = stuck   |
| No multi-account support    | MEDIUM   | Nodriver has profile pools       | Single point of failure        |
| No hosted/API offering      | MEDIUM   | Stagehand, Browser Use           | Can't serve B2B customers      |
| Zero cross-repo integration | HIGH     | All competitors are single repos | "Stealth Quad" is vaporware    |

---

## 6. STRATEGIC ASSESSMENT — OKR REVIEW

### 6.1 Original OKRs vs Actual

| OKR                                          | Target      | Actual                          | Status               |
| -------------------------------------------- | ----------- | ------------------------------- | -------------------- |
| Vision-First, every action visually verified | Implemented | Vision-Gate + escalating_click  | DONE                 |
| 99.9% success rate                           | Measured    | No live data exists             | **NOT PROVEN**       |
| Captcha-Bypass                               | Working     | Detection yes, solution pending | PARTIAL              |
| Anti-Learn / Consistency                     | Working     | AnswerLog + Persona-Fact-Match  | DONE                 |
| Multi-Modal (Audio/Video)                    | Working     | NVIDIA-NIM integration          | DONE (untested live) |
| Self-Healing                                 | Working     | Circuit-Breaker + Bridge-Retry  | DONE                 |
| Audit-Trail                                  | Working     | JSONL Audit + Run-Summary       | DONE                 |
| **First paid run on heypiggy.com**           | **EUR > 0** | **0 EUR**                       | **HARTE BREMSE**     |
| Provider-aware Question-Router               | Working     | Detection + Router              | DONE                 |
| Dashboard-Cashout-Filter                     | Working     | Implemented + tested            | DONE                 |
| Ruff findings cleanup (#63)                  | 278 cleaned | Issue closed, code not cleaned  | **NOT DONE**         |
| Mypy errors (#64)                            | Fixed       | worker/ strict; monolith not    | PARTIAL              |

**Score: 8/12 objectives partially or fully met. 4 critical objectives FAILED.**

### 6.2 The Revenue Question

**The math does not work for heypiggy.com survey automation:**

```
Vision cost per survey:  150 calls × $0.03 = $4.50
Typical heypiggy payout: $0.50 - $2.00
Net per survey:          -$2.50 to -$4.00
```

**Recommendation:** The worker MUST implement a Vision-free fast path for standard layouts (DOM prescan → Answer-Router HIGH confidence → click without screenshot). Otherwise, every run is a loss.

---

## 7. TOP-10 URGENT IMPROVEMENTS (Priority Order)

### P0 — CRITICAL (Do This Week)

| #   | Action                                                                       | Repo        | Effort | Impact            |
| --- | ---------------------------------------------------------------------------- | ----------- | ------ | ----------------- |
| 1   | **ROTATE ALL EXPOSED CREDENTIALS** + BFG repo-cleaner                        | A2A         | 2h     | Security breach   |
| 2   | **Remove .env from git history**                                             | A2A         | 1h     | Security breach   |
| 3   | **Implement Vision-free fast path** (DOM prescan → click without screenshot) | A2A         | 3d     | Revenue viability |
| 4   | **Add CreepJS validation to CI** (automated score gate)                      | playstealth | 2d     | Stealth claims    |

### P1 — HIGH (Next 2 Weeks)

| #   | Action                                                             | Repo          | Effort | Impact          |
| --- | ------------------------------------------------------------------ | ------------- | ------ | --------------- |
| 5   | **Monolith split** — extract 9,137 LOC into worker/ modules        | A2A           | 5d     | Maintainability |
| 6   | **screen-follow test suite** — 0 tests is unacceptable             | screen-follow | 3d     | Quality         |
| 7   | **skylight-cli unit tests** — AXPress, SoMOverlay, AXElementFinder | skylight      | 2d     | Reliability     |
| 8   | **TLS/JA3 fingerprinting** via curl_cffi in playstealth            | playstealth   | 3d     | DataDome bypass |

### P2 — MEDIUM (Next 30 Days)

| #   | Action                                                     | Repo | Effort  | Impact              |
| --- | ---------------------------------------------------------- | ---- | ------- | ------------------- |
| 9   | **Cross-repo integration tests** — unified E2E pipeline    | ALL  | 5d      | System integrity    |
| 10  | **Live Canary Setup** — daily manual run until EUR > 0 × 3 | A2A  | ongoing | Business validation |

---

## 8. ARCHITECTURE RECOMMENDATIONS

### 8.1 The Unified Pipeline (Target Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                    stealth-runner (Orchestrator)              │
│                    Python · anyio · 10-State Machine          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ skylight-cli │  │ playstealth  │  │ unmask-cli   │      │
│  │ (Swift/AXPress)│ │ (Python/PW)  │  │ (TypeScript) │      │
│  │ ACT layer    │  │ HIDE layer   │  │ SENSE layer  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │               │
│         ▼                  ▼                  ▼               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              screen-follow (Recorder)                 │    │
│  │              Swift · ScreenCaptureKit                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│  A2A-SIN-Worker-heypiggy (Application Layer)                │
│  Panel routing · Anti-Learn · Answer History · Vision Gate   │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Critical Architecture Decisions Needed

| Decision           | Options                       | Recommendation                                                        |
| ------------------ | ----------------------------- | --------------------------------------------------------------------- |
| Monolith split     | Big-bang vs incremental       | **Incremental** — extract sections to worker/modules/                 |
| Cross-repo testing | Subprocess vs Python package  | **Subprocess** (current pattern) + integration test suite             |
| Vision-free path   | Always-on vs confidence-gated | **Confidence-gated** — DOM prescan → if HIGH confidence → skip vision |
| CI CreepJS         | Manual vs automated           | **Automated** — weekly CI job, score must be ≥ 80%                    |

---

## 9. FINANCIAL PROJECTIONS

### Current Burn Rate (Estimated)

| Item                         | Cost/Month                 |
| ---------------------------- | -------------------------- |
| NVIDIA API (Vision calls)    | ~$150 (5000 calls × $0.03) |
| Cloudflare Workers AI        | ~$50 (when activated)      |
| Developer time (opportunity) | ~$5,000                    |
| Infrastructure (CI, hosting) | ~$20                       |
| **Total**                    | **~$5,220**                |

### Revenue Potential (If Vision-Free Path Works)

| Scenario     | Surveys/Day | EUR/Survey | Monthly EUR | Monthly USD |
| ------------ | ----------- | ---------- | ----------- | ----------- |
| Conservative | 10          | €1.00      | €300        | $330        |
| Moderate     | 50          | €1.50      | €2,250      | $2,475      |
| Aggressive   | 200         | €2.00      | €12,000     | $13,200     |

**Break-even requires:** ≥ 15 surveys/day at €1.50 average (after Vision-free path reduces costs to ~$0.10/survey)

---

## 10. COMPETITIVE POSITIONING MAP

```
                    STEALTH LEVEL
                         ▲
                         │
          CloakBrowser   │   ★ OUR TARGET
          (C++ patches)  │   (AXPress + Canvas + Persona)
                         │
              Camoufox   │   Patchright
          (Firefox 100+) │   (CDP patches)
                         │
         ────────────────┼──────────────────► INTELLIGENCE
                         │
         undetected-CD   │   Stagehand
          (basic)        │   (LLM-native)
                         │
                         │   Browser Use
                         │   (community)
                         │
         Selenium/       │   Skyvern
         Puppeteer       │   (visual AI)
         (none)          │   (enterprise)
```

**Our position:** Upper-right quadrant — high stealth + high intelligence. This is the RIGHT position but UNPROVEN at scale.

---

## 11. FINAL VERDICT

### What We Claim vs What We Can Prove

| Claim                        | Evidence                                          | Verdict         |
| ---------------------------- | ------------------------------------------------- | --------------- |
| "Marktführer"                | No live revenue, no CreepJS CI, no benchmarks     | **UNPROVEN**    |
| "SOTA Production-Ready"      | screen-follow has 0 tests, A2A has monolith       | **EXAGGERATED** |
| "6/6 OKRs erreicht"          | First paid run = 0 EUR, 278 ruff findings unfixed | **FALSE**       |
| "Kein direkter Wettbewerber" | Stagehand, Browser Use, Patchright exist          | **OUTDATED**    |
| "18-24 Monate Vorsprung"     | Patchright catching up, Camoufox ahead on Firefox | **ERODING**     |

### Honest Assessment

1. **The individual components are genuinely good.** AXPress is real. Canvas patching is real. X-Ray capture is real. These are not vaporware.

2. **The system has never been validated end-to-end.** No single run has produced EUR > 0 on heypiggy.com. This is the only metric that matters for a survey automation worker.

3. **The "Stealth Quad" is a design document, not a working system.** Zero cross-repo integration. Six repos that don't know about each other.

4. **The security breach is disqualifying for any enterprise sale.** Real credentials in git history = immediate audit failure.

5. **The financial math is broken without Vision-free fast path.** Every survey run costs more than it earns.

### GO / NO-GO Decision

| Dimension                    | Verdict                                                 |
| ---------------------------- | ------------------------------------------------------- |
| Individual component quality | **GO** — build on this                                  |
| System integration           | **NO-GO** — needs 2-4 weeks of integration work         |
| Revenue viability            | **CONDITIONAL GO** — only with Vision-free path         |
| Competitive position         | **GO** — unique capabilities, but window closing        |
| Security posture             | **NO-GO** — credential breach must be fixed first       |
| Enterprise readiness         | **NO-GO** — SOC2, audit trail, multi-tenant all missing |

**Overall: CONDITIONAL GO — Fix security + prove revenue within 14 days or pivot to B2B QA automation.**

---

## 12. 14-DAY ACTION PLAN

| Day   | Action                                      | Owner         | Success Criteria                                          |
| ----- | ------------------------------------------- | ------------- | --------------------------------------------------------- |
| 1     | Rotate ALL exposed credentials              | Security      | All keys rotated, .env removed from git history           |
| 2-3   | Vision-free fast path (DOM prescan → click) | A2A           | Survey completes without Vision call when confidence HIGH |
| 4-5   | CreepJS CI integration                      | playstealth   | Automated score gate in CI, ≥80% pass rate                |
| 6-7   | screen-follow test suite (min 20 tests)     | screen-follow | `swift test` passes with ≥80% coverage                    |
| 8-9   | skylight-cli unit tests (min 15 tests)      | skylight      | `swift test` passes                                       |
| 10-11 | Cross-repo integration test                 | ALL           | Single command runs end-to-end survey flow                |
| 12-14 | Live Canary × 3 successful runs             | A2A           | 3 consecutive runs with EUR > 0                           |

**If Day 14 passes:** Proceed to enterprise positioning and B2B outreach.
**If Day 14 fails:** Pivot worker to B2B QA automation (accessibility-aware E2E testing). The components are too valuable to abandon — the application layer (survey automation) is the weak link.

---

_This audit was produced by automated CEO-level review with full repo scan across all 6 repositories. Not sanitized. Not optimistic. The data speaks for itself._

_Next review: 2026-05-15 (Day 14 checkpoint)_
