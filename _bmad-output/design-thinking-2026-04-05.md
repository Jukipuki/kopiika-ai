# Design Thinking Session: Kopiika User Feedback System

**Date:** 2026-04-05
**Facilitator:** Oleh
**Design Challenge:** How do we design a user feedback system for Kopiika that captures actionable signals to improve RAG-generated education quality, surfaces bugs and friction points, and helps prioritize future features — all without annoying weekly/monthly users who engage briefly and infrequently, and without adding backend complexity for a solo developer?

---

## 🎯 Design Challenge

Kopiika users interact with AI-generated educational content through a card-based Teaching Feed, but we currently have no mechanism to learn whether this content is accurate, relevant, or useful. Users visit weekly or monthly, engage briefly, and have varying financial literacy (three personas: Anya the learner, Viktor the optimizer, Dmytro the discoverer). We need lightweight feedback touchpoints woven naturally into the existing experience that: earn signal on education quality (to improve the RAG corpus), catch bugs and UX friction, and eventually inform the roadmap — all while respecting the trust-first, no-pressure ethos that defines Kopiika's brand. The system must be processable by a solo developer and technically lightweight.

---

## 👥 EMPATHIZE: Understanding Users

### User Insights

**Anya (The Learner) — Low financial literacy, weekly/monthly visitor:**
- Emotionally vulnerable when viewing financial insights — learning uncomfortable truths about spending
- Any explicit feedback prompt during the Teaching Feed feels like interrupting a student mid-lesson
- A quiet, zero-pressure thumbs up/down on cards is natural — mirrors her internal reaction ("oh, that's useful" or "meh")
- Most likely of the three personas to use thumbs up/down because it validates her learning journey
- Would never fill out a form or follow an external link for feedback

**Viktor (The Optimizer) — Moderate literacy, monthly ritual user:**
- Sessions are focused and efficient: upload, scan cards, check Health Score, done
- Feedback prompts are pure friction unless he's already finished his flow
- Might use thumbs up/down on a particularly surprising insight, but probably only 1 in 5 sessions
- Most receptive to feedback at the end, when there's nothing left to process
- Would tolerate an occasional "Why was this useful?" follow-up — but only after he's already opted in with a thumb

**Dmytro (The Discoverer) — High literacy, skims fast:**
- Skims quickly, doesn't engage with UI elements that aren't directly useful to him
- Bug reports are his ceiling for active feedback — and only if the mechanism is frictionless
- Thumbs up/down? Occasionally. Written feedback? Almost never unless something is factually wrong or broken
- Would appreciate a minimal bug/report mechanism but would never seek it out proactively

### Key Observations

- **The AI chat pattern is the gold standard**: never asks, always available. Thumbs up/down inline. Occasional contextual follow-up ("Why?") only after the user has already opted in
- **Hard no-go's**: mid-flow interruptions, external redirects (Google Forms), per-session asks
- **Frequency tolerance is very low**: weekly/monthly users treat each session as precious — even one misplaced prompt erodes trust
- **The moment matters**: after a card is consumed (not during), or after the session is "complete" (nothing left to process)
- **Implicit signals may outweigh explicit ones**: card expansion rates, time spent on cards, swipe-through speed, and which education layers get opened already reveal content quality without asking a single question
- **Feedback philosophy must match brand**: Kopiika is trust-first, no-pressure, education-focused — feedback mechanisms must embody the same values

### Empathy Map Summary

| Dimension | Anya (Learner) | Viktor (Optimizer) | Dmytro (Discoverer) |
|-----------|---------------|-------------------|---------------------|
| **Think** | "Is this right about me?" | "Show me what I missed" | "Anything new here?" |
| **Feel** | Vulnerable, curious, hopeful | Focused, efficient, validated | Confident, impatient, skeptical |
| **Do** | Read cards carefully, expand education layers | Scan headlines, check score, deep-dive on surprises | Skim fast, act on blind spots |
| **Say** | "Oh, I didn't know that" | "That's useful" / moves on | Reports a bug if something breaks |
| **Feedback tolerance** | Passive only during feed; maybe a prompt post-session | Only after flow is complete | Bug/report mechanism, nothing more |
| **Best channel** | Thumbs on cards | Thumbs on cards + optional end-of-session | Bug/report mechanism only |

---

## 🎨 DEFINE: Frame the Problem

### Point of View Statement

**POV 1 — Education Quality Signal:**
Kopiika users consuming AI-generated education cards **need** a way to silently signal whether content was relevant and useful **because** the RAG corpus quality can only improve if there's a closed feedback loop — and the solo developer has no other way to know which cards hit and which miss.

**POV 2 — Friction & Bug Detection:**
Kopiika users who encounter something broken or confusing **need** a frictionless way to report it without leaving their current context **because** low-frequency users who hit a bug and can't easily report it will simply leave and never come back — there's no habit loop strong enough to bring them back through friction.

**POV 3 — Engagement Deepening:**
Kopiika as a product **needs** to understand what users find valuable enough to act on **because** the north star metric (Education-to-Action Conversion Rate) is impossible to measure without understanding which insights resonated and why — implicit behavioral data alone can't distinguish "useful but didn't act" from "irrelevant."

### How Might We Questions

1. **HMW** let users rate education quality without it feeling like work or evaluation?
2. **HMW** capture the *why* behind a thumbs-down without forcing a multi-step flow?
3. **HMW** make bug reporting feel like a natural part of the card experience rather than a separate system?
4. **HMW** combine implicit signals (expansion rates, time spent) with explicit signals (thumbs) into a single quality score per card/topic?
5. **HMW** use feedback to automatically improve the RAG corpus without manual curation by a solo dev?
6. **HMW** ask for deeper feedback occasionally without training users to expect (and dread) it every session?
7. **HMW** distinguish between "this education content is bad" vs. "this insight doesn't apply to me" — two very different signals?
8. **HMW** make giving feedback feel like it *contributes to* the user's experience rather than *interrupts* it?

### Key Insights

**Insight 1: Two distinct feedback loops exist — and they have different urgencies.**
- **Quality loop** (thumbs on cards) improves the product gradually over time. Low urgency per-event, high value in aggregate.
- **Bug/friction loop** (report mechanism) needs to capture problems before the user churns. High urgency per-event.
- These should be separate mechanisms, not bundled into one "feedback" feature.

**Insight 2: Implicit behavioral data is your first and cheapest feedback layer.**
- Card expansion tracking from adaptive education depth (Story 3.8) already exists. Expansion rate, time-on-card, and swipe-through speed are free signals collectible without any UI changes.
- Explicit feedback (thumbs) should supplement this, not replace it.

**Insight 3: The "occasional follow-up" pattern solves the depth-vs-frequency tension.**
- Never ask every time. But when a user gives a thumb-down, a single optional "What was off?" with 3-4 preset choices (e.g., "Not relevant to me", "Already knew this", "Seemed incorrect", "Confusing") gives categorized signal with one tap.
- This mirrors the AI chat pattern — follow-up only after opt-in.

**Insight 4: Feedback data has a dual use — RAG quality AND content generation.**
- Thumbs-down on a topic cluster = that part of the corpus needs better source documents or different retrieval strategy.
- Thumbs-up on a topic cluster = generate more content in that direction for similar users.
- This closes the loop from feedback → corpus improvement → better cards → better feedback.

---

## 💡 IDEATE: Generate Solutions

### Selected Methods

**1. SCAMPER Design** — Applied to existing AI chat feedback patterns (thumbs up/down) to adapt them to a card-based, low-frequency financial education context. What can we substitute, combine, adapt, eliminate?

**2. Analogous Inspiration** — Drawing from apps with similar engagement patterns:
- *ChatGPT/Claude*: Thumbs on responses, optional follow-up categories on thumbs-down
- *Duolingo*: "Was this sentence useful?" after a lesson — not during
- *Spotify Discover Weekly*: Implicit signals (skips, saves, replays) tell more than any survey
- *Apple Health*: Zero feedback UI — all implicit signal from usage patterns

**3. Brainstorming** — Unconstrained idea generation across all feedback types (quality, bugs, roadmap), then filtered through constraints (solo dev, lightweight backend, non-intrusive, no external redirects).

### Generated Ideas

**Layer 0: Implicit / Zero-UI Feedback (no user action required)**
1. Track card expansion rate per topic cluster — low expansion = content too basic or irrelevant
2. Track time-on-card — very short = skimmed/irrelevant, moderate = consumed, very long = confusing
3. Track swipe-through velocity — fast swipes = low engagement batch
4. Track which education depth levels get opened (from Story 3.8 adaptive depth)
5. Track session completion rate — did they view all cards or abandon mid-feed?
6. Track return-to-card behavior — did they swipe back to re-read something?
7. Aggregate implicit signals into a per-card "engagement score" stored in the DB

**Layer 1: Passive Explicit Feedback (always available, never asked)**
8. Thumbs up/down on each Teaching Feed card — small, muted icons below card content
9. "Report an issue" icon (flag/exclamation) tucked into card overflow menu or corner
10. Long-press or swipe-action on a card to reveal feedback options (gesture-based, zero clutter)
11. "More like this" / "Less like this" as alternative to thumbs (feels less evaluative, more preference)
12. Emoji reaction set (useful / already knew this / confusing / wrong) — one-tap, no text
13. "Save this insight" bookmark — positive signal without explicit rating framing

**Layer 2: Contextual Follow-up (triggered only after opt-in)**
14. On thumbs-down: slide-up with 3-4 preset reasons ("Not relevant", "Already knew this", "Seems incorrect", "Confusing") — one tap, dismissible
15. On thumbs-up: occasionally (1 in 10) show "What made this useful?" with presets ("Learned something new", "Actionable for me", "Well explained")
16. On "Report issue": minimal form — dropdown category (Bug, Incorrect info, Confusing, Other) + optional one-line text field, all in-context
17. After a thumbs-down streak (3+ in a session): subtle banner "Insights not hitting the mark? We're learning from your feedback to improve"

**Layer 3: Session-Level / Periodic Feedback (rare, end-of-flow)**
18. End-of-feed summary card: "You reviewed 7 insights today. Anything we should know?" with optional text field — appears only when user has scrolled through all cards
19. After 3rd upload (milestone): one-time "How's Kopiika working for you?" with 3 emoji faces (happy/neutral/sad) + optional text — never repeated
20. After Financial Health Score changes significantly: "Your score went up 8 points! Is this feeling accurate?" — ties feedback to a moment of positive emotion
21. Quarterly NPS-style micro-survey (1 question max): "Would you recommend Kopiika to a friend?" — appears in the Teaching Feed as a card, skippable like any other card
22. "Suggestion box" in account settings — always there, never promoted, for power users who seek it out

**Layer 4: Structural / System-Level Ideas**
23. Feedback as a card type in the Teaching Feed itself — treated like any other card, can be swiped away, never blocks the flow
24. Aggregate feedback dashboard for the developer — topic clusters with avg thumbs ratio, engagement scores, bug report counts
25. Automatic RAG corpus flagging — when a topic cluster accumulates >30% thumbs-down rate, flag for review
26. A/B test card variants using feedback signals — serve two phrasings of the same insight, compare thumb ratios
27. Feedback-weighted card ranking — cards with high engagement scores get surfaced earlier in future feeds for similar user profiles

### Top Concepts

**Concept A: "Silent Quality Loop"** (Layer 0 + Layer 1)
- Combine implicit behavioral signals (expansion, time, velocity) with passive thumbs up/down on cards
- No follow-up, no prompts, no friction — just two small icons on every card
- Backend: simple `card_feedback` table (card_id, user_id, vote, timestamp) + implicit signals logged alongside existing card interaction events
- **Primary value:** RAG corpus quality scoring at scale with near-zero user effort

**Concept B: "Opt-in Depth"** (Layer 1 + Layer 2)
- Thumbs up/down as base, with contextual follow-up only on thumbs-down
- Slide-up panel with 3-4 preset reason chips, dismissible, one-tap
- Occasional (1 in 10) follow-up on thumbs-up to understand what works, not just what fails
- **Primary value:** Categorized negative signal that distinguishes "bad content" from "wrong audience" from "incorrect info"

**Concept C: "Feedback as a Card"** (Layer 3 + Layer 4)
- Milestone-triggered feedback appears as a card in the Teaching Feed — same UX as education cards
- Can be swiped away without guilt. Appears at end of feed, never interrupts.
- Examples: after 3rd upload, after significant Health Score change, quarterly micro-check
- Report-a-bug lives in card overflow menu, always accessible
- **Primary value:** Periodic deeper signal without introducing a new UI pattern or flow

---

## 🛠️ PROTOTYPE: Make Ideas Tangible

### Prototype Approach

**Recommended: Combine all three top concepts into a layered feedback system**, implemented incrementally. Rough prototyping isn't physical here — it's about defining the exact UI behaviors and data model before building. The prototype should be a detailed wireframe/spec of the feedback UX integrated into the existing Teaching Feed card component.

**Why layered:** Each layer can be built and shipped independently. Layer 0 (implicit) requires almost no UI work. Layer 1 (thumbs) is a small card component change. Layer 2 (follow-up) and Layer 3 (feedback cards) can come later once you have data on whether people actually use thumbs.

### Prototype Description

**The Kopiika Feedback System — 4 Layers**

**Layer 0: Implicit Signal Collection (no UI, backend only)**
- Extend existing card interaction tracking to log: time_on_card_ms, education_expanded (boolean), education_depth_reached (level), swipe_direction, card_position_in_feed
- Aggregate into a per-card `engagement_score` (0-100) using weighted formula
- Store alongside existing card data — no new tables needed, extend existing interaction events

**Layer 1: Thumbs Up/Down on Cards**
- Two small, muted icons (thumb-up, thumb-down) in the bottom-right of each Teaching Feed card
- Appear after the card has been visible for 2+ seconds (prevent accidental taps, reduce visual clutter on fast swipes)
- On tap: icon fills/highlights, brief haptic feedback, no modal or redirect
- A small "flag" icon in the card overflow menu (three-dot menu) for "Report an issue"
- State persists — if user returns to card, their vote is shown

**Layer 2: Contextual Follow-up on Thumbs-Down**
- On thumbs-down tap: after a 300ms delay, a compact slide-up panel appears below the card (not a modal — stays in feed context)
- Panel contains 4 preset chips: "Not relevant to me" | "Already knew this" | "Seems incorrect" | "Hard to understand"
- Optional: small text field labeled "Anything else?" (collapsed by default, expands on tap)
- Tapping a chip = done, panel auto-dismisses after 1s
- Dismissible by tapping outside or swiping down
- On thumbs-up: 1 in 10 times, a single-line prompt: "What made this useful?" with chips: "Learned something" | "Actionable" | "Well explained" — same compact format, same dismissibility

**Layer 3: Feedback Cards in the Feed**
- Milestone-triggered cards that appear at the END of the Teaching Feed (after all insight cards):
  - **After 3rd upload (one-time):** "How's Kopiika working for you?" — 3 emoji faces + optional text field. Card type: `feedback_milestone`. Swiped away = dismissed forever.
  - **After significant Health Score change (+/- 5 points):** "Your score changed! Does this feel accurate?" — Yes/No + optional text. Appears as the last card.
  - **Quarterly micro-check:** "Would you recommend Kopiika to a friend?" — 1-10 scale (NPS). Appears as a regular card in the feed, fully skippable.
- All feedback cards use the same card component and gestures as education cards — no new UI pattern
- "Report a bug" accessible from Account Settings page — simple form: category dropdown + text field. Always available, never promoted.

**Data Model (lightweight):**
```
card_feedback:
  id, user_id, card_id, card_type, vote (up/down/null), 
  reason_chip (nullable), free_text (nullable), created_at

feedback_responses:
  id, user_id, feedback_card_type, response_value, 
  free_text (nullable), created_at

card_interactions (extend existing):
  + time_on_card_ms, education_expanded, education_depth_reached
```

### Key Features to Test

1. **Do users actually tap thumbs?** — Track thumbs-interaction-rate per session. Target: >5% of cards viewed get a thumb (either direction). If <2%, the icons may be too hidden or users don't see value.
2. **Does thumbs-down follow-up get used?** — Track chip-selection-rate when the follow-up panel appears. Target: >40% select a chip (vs. dismiss). If low, the panel may feel intrusive despite opt-in.
3. **Distribution of thumbs-down reasons** — Is it mostly "Not relevant" (persona mismatch / adaptive depth issue) or "Seems incorrect" (RAG corpus quality issue)? This determines where to invest improvement effort.
4. **Do feedback cards get dismissed or engaged?** — Track swipe-away rate vs. response rate on milestone cards. Target: >20% response rate on the 3rd-upload milestone card.
5. **Does feedback correlate with retention?** — Do users who give feedback (especially positive) return more? Or does giving negative feedback correlate with churn? Critical for understanding if feedback itself affects engagement.
6. **Implicit vs. explicit signal alignment** — Do cards with high engagement scores (implicit) also get more thumbs-up (explicit)? If yes, implicit signals alone may suffice and you can reduce explicit asks.

---

## ✅ TEST: Validate with Users

### Testing Plan

Since Kopiika is pre-production, testing follows a phased approach that starts before public launch:

**Phase 1: Internal Dogfooding (Pre-Launch)**
- Upload your own Monobank statements and interact with the feedback UI
- Test all feedback paths: thumbs up, thumbs down + reason chips, dismiss behavior, feedback cards at milestones
- Verify data model captures all signals correctly
- Check that feedback icons don't clutter the card UI or interfere with swipe gestures
- Simulate all three personas: try the feed as Anya (expand everything, rate frequently), Viktor (scan fast, rate rarely), Dmytro (skim, only report if something's wrong)

**Phase 2: Friends & Family Alpha (5-7 users)**
- Recruit 5-7 real Monobank users across literacy levels
- Give them no instructions about feedback — observe if they discover and use thumbs naturally
- Tasks: upload a statement, browse the Teaching Feed, return after 1 week with a new statement
- Observe: Do they notice the thumbs? Do they use them? Do they engage with the follow-up panel?
- Post-session interview (5 min): "Did you notice anything on the cards besides the content?" / "Was there anything you wanted to tell us but couldn't?"

**Phase 3: Early Access Launch (first 50-100 users)**
- Ship Layer 0 (implicit) + Layer 1 (thumbs) only — hold back Layer 2 and 3
- Monitor: thumbs interaction rate, implicit engagement scores, any correlation
- After 2 weeks of data: ship Layer 2 (follow-up on thumbs-down) if thumbs-down rate is meaningful (>1% of viewed cards)
- After 1 month: ship Layer 3 (milestone feedback cards) for users hitting their 3rd upload

### User Feedback

*(Simulated expert-user responses for pre-launch planning)*

**Expected Anya-type feedback patterns:**
- Moderate thumbs-up usage on cards she finds enlightening (the "oh, I didn't know that" moments)
- Occasional thumbs-down with "Not relevant to me" on cards pitched at wrong literacy level
- Likely to engage with the 3rd-upload milestone card — she's invested in the relationship with the product
- Unlikely to use bug report unless something is visually broken

**Expected Viktor-type feedback patterns:**
- Sparse thumbs usage — maybe 1-2 per session on standout cards
- If he thumbs-down, likely to select a reason chip (he's efficient, not dismissive)
- May skip milestone feedback cards — he's already done with his ritual
- Might use bug report if data parsing produces an incorrect categorization

**Expected Dmytro-type feedback patterns:**
- Rarely uses thumbs at all
- If something is factually wrong, he'll use the flag/report mechanism
- Will never engage with milestone cards — swipe and move on
- His most valuable feedback is actually implicit: which cards he spends >5 seconds on vs. which he instantly swipes

### Key Learnings

*(Anticipated learnings to validate during testing)*

1. **Thumbs interaction rate will likely be low — and that's OK.** Industry benchmarks for inline rating on content cards are 3-8%. Even at 3%, with 5 cards per session and 100 monthly users, that's 15-40 data points per month — enough to spot trends in topic clusters.

2. **Implicit signals will likely be more reliable than explicit ones.** Expansion rate and time-on-card are honest signals — users can't "lie" with their behavior the way they can with a thumbs-up. The real value of explicit feedback is the *categorized thumbs-down reason* — implicit data can't tell you WHY a card failed.

3. **The follow-up panel is the highest-risk UI element.** It could feel intrusive even though it's opt-in (user already tapped thumbs-down). Key metric: if >30% of follow-up panels are dismissed without a chip selection, the panel is adding friction. Solution: make it appear slower (500ms delay) or only trigger on the 2nd thumbs-down in a session.

4. **Feedback cards as a feed item will feel natural — or not at all.** If the visual design matches education cards closely enough, users will treat them as just another card. If they look different (different background, different layout), they'll feel like ads/interruptions. Design parity is critical.

5. **The most actionable feedback loop is: thumbs-down + "Seems incorrect" → flag RAG source doc for review.** This is the highest-value signal for a solo dev — it directly points to corpus quality issues that affect all users, not just preference mismatches.

---

## 🚀 Next Steps

### Refinements Needed

1. **Thumbs icon placement and timing** — Need to validate that showing icons after 2-second delay doesn't feel "appearing out of nowhere." Alternative: always visible but very muted (gray, small), brighten on hover/focus.

2. **Follow-up panel trigger logic** — Consider: only show follow-up on the FIRST thumbs-down per session, not every one. Prevents it from feeling repetitive if a user thumbs-down multiple cards in a row (which may happen when adaptive depth misfires).

3. **Feedback card frequency caps** — Define hard rules: max 1 feedback card per session, max 1 per month, milestone cards never repeat. These caps should be in the backend, not just UI logic.

4. **Bilingual considerations** — Reason chips and feedback card copy need Ukrainian and English variants. Keep copy extremely short to avoid translation bloat ("Not relevant" / "Не актуально").

5. **RAG corpus auto-flagging threshold** — The >30% thumbs-down threshold for auto-flagging needs tuning. With low volume early on, a single topic cluster could get flagged from 2 out of 5 votes. Consider minimum sample size (e.g., at least 10 votes on a cluster before flagging).

6. **Privacy alignment** — Feedback data is user-generated content tied to their profile. Needs to be included in the "view my stored data" (Story 5-4) and "delete all my data" (Story 5-5) flows. Free-text feedback especially — users should see what they've written if they ask.

### Action Items

**Implementation order (layered, each shippable independently):**

| Priority | Layer | What | Depends On |
|----------|-------|------|------------|
| 1 | Layer 0 | Extend card interaction tracking with time_on_card, education_expanded, depth_reached | Existing card interaction events from Story 3.8 |
| 2 | Layer 1 | Thumbs up/down icons on Teaching Feed cards + `card_feedback` table | Card component, new DB migration |
| 3 | Layer 1 | "Report issue" in card overflow menu → simple in-context form | Card component |
| 4 | Layer 2 | Follow-up panel on thumbs-down with reason chips | Layer 1 thumbs |
| 5 | Layer 2 | Occasional follow-up on thumbs-up (1 in 10) | Layer 1 thumbs |
| 6 | Layer 3 | Milestone feedback card (3rd upload) | Feed card system, upload count tracking |
| 7 | Layer 3 | Health Score change feedback card | Epic 4 Health Score |
| 8 | Layer 3 | Quarterly NPS micro-survey card | Feed card system, frequency cap logic |
| 9 | — | Developer feedback dashboard (aggregate view of signals) | Layers 0-2 data |
| 10 | — | RAG corpus auto-flagging based on feedback aggregates | Layer 1 data + threshold tuning |

**Note:** Layers 0-1 can be scoped as a single epic/story. Layer 2 is a fast follow. Layer 3 depends partly on Epic 4 (Health Score). Dashboard and auto-flagging are operational tools, not user-facing.

### Success Metrics

| Metric | Target | When to Measure |
|--------|--------|----------------|
| **Thumbs interaction rate** | >5% of viewed cards receive a vote | After 1 month of Layer 1 |
| **Follow-up chip selection rate** | >40% of thumbs-down triggers result in a chip selection | After 2 weeks of Layer 2 |
| **Follow-up dismissal rate** | <30% of panels dismissed without action | After 2 weeks of Layer 2 |
| **Milestone card response rate** | >20% of 3rd-upload cards get a response | After 50 users hit milestone |
| **Bug report usage** | >0 (any reports = success for early stage) | Ongoing |
| **Implicit-explicit correlation** | >0.5 correlation between engagement_score and thumb ratio per topic cluster | After 3 months of data |
| **RAG quality improvement signal** | At least 1 corpus improvement action taken based on feedback data per quarter | Quarterly review |
| **Feedback-to-churn correlation** | Users who give negative feedback don't churn more than silent users (feedback doesn't hurt retention) | After 3 months |

---

_Generated using BMAD Creative Intelligence Suite - Design Thinking Workflow_
