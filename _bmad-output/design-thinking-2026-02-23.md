# Design Thinking Session: Smart Financial Intelligence & Literacy Coach

**Date:** 2026-02-23
**Facilitator:** Oleh
**Design Challenge:** How might we transform raw bank statement data into a personalized financial education experience that changes spending habits — serving both financially inexperienced users who need to learn and busy literate users who need clarity — starting with Ukraine-centric context, without external API dependencies, and framed as education rather than advice?

---

## Design Challenge

People have financial data but never learn from it. Bank statements pile up as numbers in CSVs and PDFs — never analyzed, never understood, never acted upon. Existing tools either show dashboards that assume financial literacy (Mint, YNAB) or offer generic advice disconnected from your actual data. Nobody connects *your specific transactions* to *plain-language financial education* that meets you where you are.

The Smart Financial Intelligence & Literacy Coach closes this gap. It ingests bank statements through a multi-agent AI pipeline that categorizes, detects patterns, and triages issues by severity — then wraps every insight in an educational layer. "Your discretionary spending is 45% of income" becomes a teaching moment: why it matters, what similar people do, and what your 3 months of data suggest. It doesn't just analyze — it teaches. And it gets smarter with every upload, building a cumulative financial profile that makes each insight more personal and each lesson more relevant.

**Primary users:** Anyone with income and spending — from people who genuinely lack financial understanding (primary focus) to financially literate users too busy to analyze their own data. MVP targets Ukrainian users with locale-specific content.

**Constraints:**
- No external API dependencies for MVP (CSV/PDF upload); bank API integration deferred
- Privacy-sensitive financial data — local-first, transparent data handling
- Web + mobile platforms
- Ukraine-centric MVP (currency, locale, financial norms, educational content)
- Framed as "insights and education," never "financial advice"

**Success criteria:** Users change their spending habits through increased financial literacy — measurable through behavior shifts in their uploaded data over time.

---

## EMPATHIZE: Understanding Users

### User Insights

**The Financially Inexperienced User ("Anya")**
- Checks balance only to see *what's left*, never to understand *what was spent*. The mental model is a shrinking pool, not a flow with patterns.
- Has vague awareness of future spending until next paycheck — lives in a fog between paychecks with no forward visibility.
- Struggles with foundational concepts: how saving works, how passive income works, how to plan a budget, how to control impulsive spending.
- Experiences a toxic emotional cocktail around money: stress, avoidance, guilt, and confusion — often all at once. This creates a cycle where the worse finances get, the less they want to look.
- Has tried simple manual logging tools but abandoned them. Financial illiteracy itself becomes a barrier to tool adoption — "I don't understand enough to use the tool that would help me understand."
- Distrusts third-party financial tools — worried about sharing sensitive data with unknown services.

**The Busy-but-Literate User ("Dmytro")**
- Overestimates their own financial judgment. Thinks they know where money goes, but data would tell a different story. Confidence creates blind spots.
- May incorrectly interpret financial patterns without proper analysis — gut feeling replaces data.
- Has the knowledge but not the time for proper analysis. Needs insights delivered, not discovered.
- Wants: spending patterns over time, forgotten subscriptions, areas for improvement, investment suggestions.
- Would open the tool regularly for short, concise, actionable insights — not dashboards to explore.

**Ukrainian Context**
- Primary interaction with finances is through mobile/web banking apps (Monobank, PrivatBank) — users see transaction lists, not analysis.
- Cultural orientation leans toward *increasing income* rather than *managing and reducing spending*. The product must respect this mindset — frame optimization as "making your money work harder," not "spending less."
- Fundamental gap: how money works in general. This isn't about advanced financial instruments — it's about basic financial mechanics that were never taught.

### Key Observations

1. **The Balance Trap**: Users relate to money as a single number (what's left) rather than a flow (where it comes from, where it goes, what patterns exist). The product must shift this mental model gradually.
2. **Literacy-Tool Paradox**: The people who need financial tools most are the least equipped to use them. Manual logging + occasional review = abandonment. The tool must require near-zero financial knowledge to deliver value.
3. **Emotional Barrier Wall**: Stress/avoidance/guilt creates a wall between users and their financial data. The product must feel safe, non-judgmental, and encouraging — never shaming.
4. **Overconfidence Blind Spot**: Literate users think they don't need help, but they do. Data-backed "did you know?" moments can crack this — showing them what they missed.
5. **Trust Deficit**: Ukrainian users are wary of sharing financial data. Privacy-first, local-data messaging is not just a feature — it's a prerequisite for adoption.
6. **Income-First Culture**: Framing matters. "Here's how to make your existing money go further" resonates more than "here's how to cut spending" in Ukrainian context.
7. **Mobile-First Reality**: Users live in Monobank/PrivatBank apps. The product must feel as natural as those apps — not like a spreadsheet or a western budgeting tool.

### Empathy Map Summary

| Dimension | Financially Inexperienced ("Anya") | Busy-but-Literate ("Dmytro") |
|---|---|---|
| **SAYS** | "I never have enough money" / "I don't know where it goes" / "I don't trust those apps with my data" | "I know my finances are fine" / "I don't have time to sit down and analyze" / "I should probably look at this more" |
| **THINKS** | "Money is stressful, I'll deal with it later" / "These tools are for people who understand finance" / "I'm bad with money" | "I have a general sense of my spending" / "I'd optimize if someone just showed me what to fix" / "I probably have subscriptions I forgot about" |
| **DOES** | Checks balance only / Uses mental math for "what's left" / Tries manual logging, abandons it / Avoids looking at statements | Glances at transaction lists / Makes gut-feel financial decisions / Occasionally reviews but doesn't deep-dive / Relies on memory for recurring expenses |
| **FEELS** | Stress, guilt, confusion, avoidance, shame, helplessness — "I should know this but I don't" | Mild guilt about not analyzing / Confident but vaguely uneasy / Time pressure / "It's probably fine" |
| **PAIN POINTS** | No financial education foundation / Tools assume knowledge they lack / Emotional barriers to engagement / Data trust concerns | No time for analysis / Overconfidence hides real issues / Wants concise answers not dashboards / Misses patterns only data reveals |
| **NEEDS** | Zero-knowledge-required insights / Non-judgmental tone / Education woven into every interaction / Privacy guarantees | Quick, high-signal summaries / Pattern detection they'd miss / "Aha moment" corrections to assumptions / Actionable next steps |

---

## DEFINE: Frame the Problem

### Point of View Statement

**Primary POV (Anya — financially inexperienced):**
Anya, a Ukrainian professional with a steady income, needs a way to understand where her money goes and learn basic financial mechanics from her own data, because she was never taught how money works, existing tools assume knowledge she doesn't have, and the emotional weight of financial confusion keeps her from even looking at her bank statements.

**Secondary POV (Dmytro — busy-but-literate):**
Dmytro, a financially literate Ukrainian professional, needs his financial data automatically analyzed and distilled into concise, prioritized insights he can act on immediately, because he has the knowledge but not the time to analyze properly, and his overconfidence in gut-feel judgment causes him to miss patterns, forgotten subscriptions, and optimization opportunities that only data reveals.

### How Might We Questions

**Core Experience:**
1. How might we make financial data *teach* rather than just *display* — so every insight is also a learning moment?
2. How might we break the emotional barrier that prevents financially inexperienced users from engaging with their own money data?
3. How might we deliver financial insights that require zero prior financial knowledge to understand and act on?

**Trust & Privacy:**
4. How might we make users feel safe sharing financial data with the tool — especially in a culture with high distrust of third-party financial services?
5. How might we demonstrate data privacy through product design rather than just policy statements?

**Engagement & Retention:**
6. How might we make the tool compelling enough that users return after every paycheck — not just once?
7. How might we frame financial optimization as "making your money work harder" rather than "spending less" to align with Ukrainian cultural attitudes?

**Personalization & Growth:**
8. How might we make each upload visibly smarter than the last — so users feel the cumulative intelligence building?
9. How might we serve both Anya (needs education) and Dmytro (needs efficiency) with the same product without overwhelming one or boring the other?

**Behavioral Change:**
10. How might we translate financial insights into actual spending habit changes — not just awareness?

### Key Insights

1. **Education IS the product, not a feature.** The core differentiator isn't better charts or smarter categorization — it's that every data point becomes a personalized lesson. The RAG-powered education layer isn't supplementary; it's the reason users come back.

2. **The onboarding moment is make-or-break.** Anya's first upload must deliver an immediate "aha" that requires zero financial knowledge. If the first screen looks like a finance tool, she'll leave. If it looks like a friendly teacher who just read her bank statement, she'll stay.

3. **Two personas, one product, different entry points.** Anya needs the education layer expanded by default with gentle, non-judgmental tone. Dmytro needs the same insights compressed, with education available on-demand via expandable sections. Same data pipeline, different presentation layer.

4. **Triage is the killer feature.** Neither persona wants to see everything equally. "Fix this first" (triage) is what separates this from a dashboard. Anya gets triage + explanation. Dmytro gets triage + action items.

5. **Trust must be demonstrated, not declared.** "Your data stays on your device" as a banner means nothing. Showing exactly what data was processed, allowing deletion, providing export — these are trust-building design decisions, not privacy policy bullet points.

6. **Cumulative intelligence is the retention hook.** The product must visibly get smarter: "Based on your 3 months of data, I can now tell you..." / "This is a new pattern I noticed this month." Users must feel the investment of each upload paying off.

7. **Ukrainian financial norms require localized framing.** Categories, merchant names, typical spending patterns, financial education content, and even the tone of insights must reflect Ukrainian financial reality — UAH currency, local merchants, local banking norms, culturally appropriate advice.

---

## IDEATE: Generate Solutions

### Selected Methods

**1. How Might We Ideation** — Take each HMW question and generate 3-5 solution ideas per question. Best for: structured exploration tied directly to defined problems.

**2. Analogous Inspiration** — Look at how other domains solve similar problems (healthcare patient education, language learning apps like Duolingo, fitness coaching). Best for: finding non-obvious patterns that can be transplanted.

**3. SCAMPER Design** — Apply Substitute/Combine/Adapt/Modify/Purpose/Eliminate/Reverse lenses to existing financial tool patterns. Best for: evolving beyond what exists rather than reinventing from scratch.

**4. Provotype Sketching** — Push ideas to extremes to find useful insights. "What if the app had zero UI?" "What if it only sent one message per month?" Best for: challenging assumptions about what the product must be.

### Generated Ideas

**From HMW Ideation:**

1. **"Story Mode" Insights** — Instead of showing numbers, wrap each insight in a narrative: "This month, your coffee habit told an interesting story. You spent 2,400 UAH across 47 visits — that's more than your electricity bill. Here's why this matters..."
2. **Progressive Disclosure Education** — Every insight has three layers: (1) the headline fact, (2) "why this matters" one-liner, (3) expandable deep-dive with financial literacy content from RAG. Anya reads all three. Dmytro reads one.
3. **"Financial Health Score"** — A single 0-100 number that summarizes overall financial health. Simple enough for Anya to track, nuanced enough for Dmytro to dig into the components. Changes with each upload.
4. **Triage Cards with Severity Colors** — Red/yellow/green insight cards sorted by impact. "Subscription creep: 1,800 UAH/month on services you rarely use [RED]" vs "Your grocery spending is stable and reasonable [GREEN]."
5. **Monthly "Paycheck Prep" Briefing** — Before each pay period, AI generates a one-page briefing: what's committed, what's discretionary, what to watch out for based on historical patterns.
6. **"Did You Know?" Nudges** — Bite-sized financial literacy facts contextualized to user data: "Did you know? You spent 12% of income on food delivery. The average Ukrainian household spends 8%. Here's how meal planning could help."
7. **Correction-Based Learning** — When AI miscategorizes a transaction, user corrects it. The correction moment becomes a teaching moment: "Got it — that's not entertainment, it's a gift. By the way, your gift spending is actually your 4th largest category."
8. **Privacy Dashboard** — A dedicated screen showing exactly what data the app has, when it was uploaded, what was processed, with one-click delete. Trust through radical transparency.

**From Analogous Inspiration:**

9. **Duolingo-Style Streaks** — Upload streak tracking. "You've uploaded 3 months in a row! Your insights are 3x more accurate than month one." Gamification of data contribution.
10. **Doctor's Visit Summary** — Like a post-appointment summary from a healthcare portal: structured, plain-language, actionable. "Your financial check-up found 3 items needing attention and 5 healthy habits."
11. **Fitness App Progress Photos** — Month-over-month visual comparisons: "Here's your spending in January vs March. Notice how your discretionary spending dropped 8% after we flagged subscription creep."
12. **Language Learning Vocabulary Model** — Track financial concepts the user has "learned" through exposure. First time seeing "discretionary spending" gets a full explanation. Fifth time gets a parenthetical. Tenth time gets nothing — they know it now.
13. **Coach, Not Calculator** — Tone modeled on a personal trainer: encouraging, directive, never shaming. "You overspent on dining this month — that happens. Here's a simple strategy for next month."

**From SCAMPER:**

14. **Eliminate the Dashboard** — What if there's no traditional dashboard at all? Just a feed of insight cards, newest first, like a social media feed but for your money. Anya never needs to navigate a complex UI.
15. **Reverse the Flow** — Instead of user exploring data, the AI pushes the single most important insight per upload. "If you only read one thing: your rent-to-income ratio is above 40%. Here's why that's a flag."
16. **Combine Upload + Education** — The upload processing screen itself becomes the education moment. While agents process, show contextual financial tips: "While we analyze your data, here's how categorization works and why it matters..."
17. **Substitute Graphs with Analogies** — Instead of pie charts Anya won't interpret, use everyday analogies: "Your subscription spending is like paying for a gym membership, Netflix, and a magazine subscription you never read — every single month."
18. **Adapt Monobank's Jar Concept** — Monobank users already understand "jars" (savings goals). Use the same mental model: "Your money flows into these jars each month. Here's which jars are overflowing and which are empty."

**From Provotype Sketching:**

19. **One Insight Per Month** — What if the app only sends one message per month? Forces extreme prioritization. The AI must decide: what is the single most impactful thing this person needs to know?
20. **Voice-Only Finance Coach** — No visual UI. User uploads statement, AI calls them (or sends voice memo) with a 2-minute verbal briefing. Tests whether the educational value is in the data or the presentation.
21. **Peer Comparison Only** — No absolute numbers. Everything is relative: "You spend more on transport than 70% of people in your income bracket in Kyiv." Tests social proof as motivation.
22. **Zero-Upload Mode** — What if the user just describes their spending verbally and the AI gives insights? Tests whether the barrier is upload friction, not analysis friction.

### Top Concepts

After evaluating all 22 ideas against our design challenge, personas, and constraints, these emerge as the core concepts to prototype:

**Concept 1: "The Teaching Feed"**
*Combines ideas: #2, #4, #14, #15*
A card-based insight feed (not a dashboard) where every card has triage severity, a headline insight, and progressive disclosure education layers. The AI pushes the most important insight first. No navigation required — just scroll. Anya sees it as a teacher explaining her money. Dmytro sees it as a prioritized action list.

**Concept 2: "Cumulative Intelligence Engine"**
*Combines ideas: #3, #8, #9, #11, #12*
The product visibly gets smarter with each upload. Financial Health Score evolves. Month-over-month comparisons appear after upload #2. Concept vocabulary tracking reduces explanations as literacy grows. Upload streaks reinforce the habit. Privacy dashboard builds trust through transparency.

**Concept 3: "Contextual Financial Literacy Layer"**
*Combines ideas: #1, #6, #7, #13, #16, #17, #18*
Every touchpoint is an education opportunity. Upload processing screens teach. Miscategorization corrections teach. Insights use analogies and stories, not charts and percentages. Monobank-familiar mental models (jars) make concepts accessible. Tone is coach, never calculator.

---

## PROTOTYPE: Make Ideas Tangible

### Prototype Approach

**Method: Wizard of Oz + Storyboarding + Paper Prototyping**

The product's core value is in AI-generated insights and education — not in UI mechanics. The best way to test whether the *content and framing* resonate is to simulate the AI output manually and put it in front of users, before building any pipeline.

**Approach:**
1. **Storyboard** the end-to-end user journey (upload -> processing -> insight feed -> education moment -> action) as a visual narrative for both personas
2. **Paper/digital prototype** of the insight feed UI — static screens showing what Anya and Dmytro would see after uploading a bank statement
3. **Wizard of Oz** the AI output — manually write 5-7 insight cards with triage severity, progressive disclosure, and educational layers using real (anonymized) transaction data. Test whether the *content* works before building the *pipeline*

**Why this approach:**
- The riskiest assumption isn't "can AI categorize transactions?" (it can) — it's "will users engage with AI-generated financial education?"
- Rough prototypes of *content and tone* test the core value proposition
- No code needed — we're testing the *teaching experience*, not the technology

### Prototype Description

**Prototype: "First Upload Experience" — 6 screens**

**Screen 1: Upload**
Clean drop zone. "Upload your bank statement (CSV or PDF). Your data stays on this device." Visual trust indicator. Monobank/PrivatBank format auto-detected.

**Screen 2: Processing (Wizard of Oz — Education During Wait)**
Animated progress: "Reading your transactions... Categorizing spending... Finding patterns..."
While processing, a rotating tip: "While we work: Did you know that tracking spending is the #1 habit of financially healthy people? You just started."

**Screen 3: Financial Health Score**
Large, friendly number (e.g., 62/100) with a brief label: "Room to grow."
Below: "This score is based on your spending balance, saving potential, and spending patterns. Each upload makes it more accurate."
No judgment. Just a starting point.

**Screen 4: Triage Feed (The Teaching Feed)**
Three insight cards, sorted by impact:

*Card 1 [RED — High Priority]:*
> **Subscription creep: 1,800 UAH/month on recurring charges**
> You have 7 active subscriptions. 3 of them had no related activity this month.
> [Why this matters] Recurring charges are the #1 silent budget drain. Unlike one-time purchases, they compound every month — 1,800 UAH/month = 21,600 UAH/year.
> [What you can do] Review these 3 subscriptions: [list]. Canceling unused ones could save 8,400 UAH/year.

*Card 2 [YELLOW — Worth Attention]:*
> **Food delivery is your 2nd largest category: 4,200 UAH**
> That's 15% of your income this month — above the typical 8-10% range.
> [Why this matters] Food delivery costs 2-3x more than home cooking for equivalent meals. This isn't about never ordering — it's about knowing the trade-off.
> [Quick tip] Even replacing 2 delivery orders per week with home cooking could redirect ~2,000 UAH/month.

*Card 3 [GREEN — Healthy]:*
> **Your utilities spending is stable and predictable**
> 2,100 UAH/month with less than 5% variation over 3 months. This is a well-managed fixed cost.
> [Learn more] Fixed costs like utilities are the easiest part of a budget to plan around. You're doing this well.

**Screen 5: Monthly Prep Briefing**
> **Your March Prep Station**
> Committed (fixed): 12,400 UAH (rent, utilities, subscriptions)
> Typical variable: ~8,600 UAH (food, transport, entertainment — based on your 3-month average)
> Remaining discretionary: ~7,000 UAH
> Watch out for: March historically has higher entertainment spending for you.

**Screen 6: What's Next**
> "Upload your next statement after your next paycheck. With 2 months of data, I can show you trends. With 3, I can predict patterns."
> [Your financial vocabulary this session: discretionary spending, fixed costs, subscription creep — you're already learning.]

### Key Features to Test

1. **Teaching Feed resonance** — Do users understand and engage with triage-sorted insight cards? Does progressive disclosure (headline -> why it matters -> what to do) work for both Anya and Dmytro?
2. **Tone and language** — Is the coaching tone (encouraging, non-judgmental) effective? Do users feel safe or lectured? Does it feel culturally appropriate for Ukrainian users?
3. **Education integration** — Do users actually expand and read the educational layers? Or do they skip them? Does the vocabulary tracker concept resonate?
4. **Financial Health Score** — Is a single number motivating or anxiety-inducing? Do users want to improve it or does it feel reductive?
5. **Trust signals** — Does "your data stays on this device" + visible processing steps + no login required build enough trust for the first upload?
6. **Prep Briefing value** — Is the monthly prep station useful? Do users understand the committed/variable/discretionary breakdown without prior knowledge?
7. **Cumulative promise** — Does "upload more for smarter insights" motivate future engagement or feel like a chore?

---

## TEST: Validate with Users

### Testing Plan

**Participants: 5-7 users across both personas**
- 3-4 "Anya" profile: limited financial literacy, Ukrainian, regular income, no current finance tools
- 2-3 "Dmytro" profile: financially literate, time-constrained, currently relies on gut-feel

**Testing Format: Think-Aloud Walkthrough (30 min per user)**

1. **Pre-test interview (5 min):** How do you currently manage your finances? What tools have you tried? How do you feel about your financial situation? (Baseline emotional state)

2. **Prototype walkthrough (15 min):** Show the 6-screen prototype with pre-written insight cards based on a sample Ukrainian bank statement. Ask them to think aloud as they go through each screen. Do NOT explain anything — observe where they pause, what they click, what confuses them.

3. **Specific task prompts:**
   - "What's the most important thing this tool is telling you?"
   - "What would you do differently after seeing this?"
   - "Would you upload your own bank statement to this? Why or why not?"
   - "Show me where you'd go to learn more about [a financial concept shown]"

4. **Post-test debrief (10 min):**
   - What surprised you?
   - What would make you come back next month?
   - What felt uncomfortable or confusing?
   - On a scale of 1-5, how much did you trust this tool with your financial data?
   - Did you learn anything new about money from this walkthrough?

**What to observe (not ask):**
- Do they read the educational expansion layers or skip them?
- Do they understand triage severity without explanation?
- How do they react emotionally to the Financial Health Score?
- Where do they hesitate or show confusion?
- Do they use financial vocabulary from the cards when discussing insights?

### User Feedback

*(Pre-populated framework for capturing test results)*

**Anya-Profile Users:**

| Question | User 1 | User 2 | User 3 | User 4 |
|---|---|---|---|---|
| Understood triage cards? | | | | |
| Read education layers? | | | | |
| Emotional reaction to score? | | | | |
| Trust level (1-5)? | | | | |
| Would upload own data? | | | | |
| Learned something new? | | | | |
| Would return next month? | | | | |

**Dmytro-Profile Users:**

| Question | User 1 | User 2 | User 3 |
|---|---|---|---|
| Found insights actionable? | | | |
| Wanted more/less detail? | | | |
| Skipped education layers? | | | |
| Trust level (1-5)? | | | |
| Would upload own data? | | | |
| Identified blind spot? | | | |
| Would return next month? | | | |

**Feedback Capture Grid:**

| Category | Findings |
|---|---|
| **Liked** | *(what users responded positively to)* |
| **Questions** | *(what confused them or prompted questions)* |
| **Ideas** | *(what users suggested or wished for)* |
| **Changes** | *(what clearly needs to change)* |

### Key Learnings

*(Framework for synthesizing test results)*

**Assumptions to Validate:**

| # | Assumption | Status | Evidence |
|---|---|---|---|
| 1 | Users will engage with progressive disclosure education | To validate | Do they tap/expand the "why this matters" sections? |
| 2 | Triage sorting (red/yellow/green) is intuitively understood | To validate | Can they identify the most important insight without prompting? |
| 3 | Non-judgmental coaching tone reduces financial shame | To validate | Emotional response during walkthrough — comfort vs. defensiveness |
| 4 | Financial Health Score motivates without causing anxiety | To validate | Reaction to the number — curiosity vs. stress |
| 5 | "Data stays on device" messaging builds sufficient trust | To validate | Trust score + willingness to upload own statement |
| 6 | Cumulative promise ("upload more = smarter") drives retention intent | To validate | "Would you come back?" responses |
| 7 | Ukrainian-localized content feels natural, not translated | To validate | Any friction with terminology, examples, or cultural references |

**Decision Framework Post-Testing:**
- If assumptions 1-3 validate: proceed with Teaching Feed as core UX pattern
- If assumption 4 fails: replace score with qualitative labels ("Getting Started" / "Growing" / "Thriving")
- If assumption 5 fails: add data processing transparency (show exactly what was read, offer line-by-line review)
- If assumption 6 fails: add immediate value without cumulative data (one-time analysis must stand alone)
- If assumption 7 fails: conduct focused Ukrainian UX writing session before development

---

## Next Steps

### Refinements Needed

1. **Validate prototype with real users before building** — The 6-screen Wizard of Oz prototype must be tested with 5-7 Ukrainian users across both personas. Without this, we're building on assumptions about tone, education engagement, and trust signals.

2. **Ukrainian financial literacy RAG corpus** — Curate or create a knowledge base specifically for Ukrainian financial context. Western financial literacy content won't land — it needs to reference UAH, Ukrainian banks, local spending norms, and culturally relevant examples.

3. **Bank statement format research** — Gather sample CSV/PDF exports from Monobank, PrivatBank, and other major Ukrainian banks. Map format variations before building the ingestion agent.

4. **Adaptive education depth** — Design the system to detect user literacy level from their interactions (do they expand education sections? correct categorizations? ask follow-up questions?) and adjust explanation depth over time. Anya's explanations get shorter as she learns; Dmytro's stay concise from the start.

5. **Privacy-first architecture decisions** — Determine early: is data truly local-only (PWA with IndexedDB)? Or server-stored with encryption? This is an architectural decision that shapes everything and must align with the trust signals promised in the UI.

### Action Items

| # | Action | Priority | Owner |
|---|---|---|---|
| 1 | Build 6-screen interactive prototype (Figma or HTML) with sample Ukrainian bank data | High | Oleh |
| 2 | Recruit 5-7 test users (3-4 Anya profile, 2-3 Dmytro profile) from personal network | High | Oleh |
| 3 | Conduct think-aloud usability tests and fill feedback capture grid | High | Oleh |
| 4 | Collect sample bank statement exports from Monobank, PrivatBank (anonymized) | High | Oleh |
| 5 | Curate initial Ukrainian financial literacy content for RAG corpus (20-30 core concepts) | Medium | Oleh |
| 6 | Define tech stack: frontend framework, backend, database, vector store, LLM provider | Medium | Oleh |
| 7 | Design data model: users, statements, transactions, categories, insights, education progress | Medium | Oleh |
| 8 | Decide privacy architecture: local-only vs. server with encryption | High | Oleh |
| 9 | Synthesize test results and iterate on prototype based on findings | Medium | Oleh |
| 10 | Begin MVP development with validated design direction | After testing | Oleh |

### Success Metrics

**Leading Indicators (Measurable in MVP):**

| Metric | Target | How to Measure |
|---|---|---|
| First-upload completion rate | >80% | User uploads statement and views at least 1 insight card |
| Education layer engagement | >40% of Anya-profile users expand at least 1 "why this matters" section | Click/tap tracking on progressive disclosure |
| Return upload rate | >50% of users upload a 2nd statement | Tracked by user account / session |
| Trust score | >3.5/5 average | Post-upload survey or in-app prompt |
| Financial Health Score engagement | Users check score after 2nd upload | Score view tracking |

**Lagging Indicators (Measurable over time):**

| Metric | Target | How to Measure |
|---|---|---|
| Spending behavior change | Detectable shift in at least 1 category after 3+ uploads | Compare spending patterns month-over-month in user's cumulative profile |
| Financial vocabulary growth | Users use financial terms in feedback/chat that were introduced by the education layer | Qualitative analysis of user language in feedback sessions |
| Subscription action rate | >20% of users act on subscription creep insights within 1 month | Compare recurring charges in subsequent uploads |
| Self-reported financial confidence | Improvement on 1-5 scale after 3 months of use | Periodic in-app survey |
| Retention at 3 months | >30% of users still uploading monthly | Upload frequency tracking |

**North Star Metric:**
**"Education-to-action conversion rate"** — The percentage of educational insights that result in a measurable behavioral change in subsequent uploads. This single metric captures whether the product is achieving its mission: not just showing data, not just teaching concepts, but actually changing how people manage money.

---

_Generated using BMAD Creative Intelligence Suite - Design Thinking Workflow_
