# Parked Idea: Smart Training Coach

**Status:** Parked for future development
**Origin:** Brainstorming session 2026-02-23
**Owner:** Oleh

## Product Vision

An AI-powered adaptive training coach that logs workouts, builds a cumulative training profile, generates personalized multi-week training protocols, and adapts them based on your actual performance data. Gets smarter the more you use it.

## Core Concept

You define a fitness goal (e.g., "gain 5kg lean mass", "improve deadlift to 150kg"). The AI generates a training protocol using RAG over an exercise science knowledge base. Each session, you log what you actually did (via voice, text, or form input). The AI compares protocol vs. reality, detects plateaus, identifies imbalances, and adjusts the plan — explaining *why* it's adjusting.

## Component Ideas (from brainstorming)

### From Cross-Pollination
- **Fitness Portfolio Tracker** — Track training balance across muscle groups, flag meaningful imbalances monthly (not daily noise)
- **AI Training Protocol Engine** — Living protocol that adapts based on accumulated data, not a static plan generator
- **Sensor-Augmented Training Logger** — Use phone accelerometer, HR strap, or Arduino sensors for auto-capture (V2+)
- **Meal-as-Fuel Planner** — Correlate eating habits with performance, suggest meals based on upcoming training (V2+)

### From SCAMPER
- **Manual-Log Protocol Engine** — Remove CV complexity, keep the intelligent protocol adaptation
- **Integrated Training & Nutrition Protocol** — Two agents collaborating: Training Agent + Nutrition Agent (V2+)
- **Spaced Progression Training** — Apply spaced repetition science to progressive overload scheduling
- **Voice-First Training Coach** — Minimal UI, talk to AI between sets, it logs and advises

## Technical Architecture (Preliminary)

### GenAI Patterns
- **RAG**: Exercise science knowledge base (program design, progressive overload theory, movement patterns)
- **Agent with Tool Use**: Protocol generation agent that queries the knowledge base + user history
- **Function Calling**: Voice/text -> structured workout data extraction
- **Structured Workflows**: Protocol generation -> session logging -> comparison -> adaptation cycle
- **Multi-Agent (V2)**: Training Agent + Nutrition Agent collaboration

### Data Model (Core)
- User profile (goals, experience level, available equipment)
- Exercise library (movements, muscle groups, equipment)
- Workout logs (exercise, sets, reps, weight, RPE, date)
- Training protocols (planned sessions over multi-week cycles)
- Protocol adherence history (planned vs. actual)

### Key Technical Challenges
- **Adaptive protocol logic**: Comparing planned vs. actual, detecting plateaus, adjusting volume/intensity
- **Voice input -> structured data**: Speech-to-text + LLM extraction of exercise parameters
- **Progressive overload optimization**: When to push, when to deload, based on accumulated data

## Constraint Analysis

| Constraint | Status | Notes |
|---|---|---|
| Computer vision | Eliminated | Use manual/voice logging |
| Exercise science RAG corpus | Achievable | Open content available |
| Voice input | Medium complexity | Whisper + LLM extraction |
| Adaptive protocols | Core challenge | The main intellectual problem |
| Nutrition integration | Defer to V2 | MVP works without it |
| IoT sensors | Defer to V2 | Cool but not needed |
| Frontend | Medium | Logging UI + protocol view + charts |

## MVP Scope Suggestion

1. Text/form-based workout logging (voice as stretch goal)
2. Goal setting + initial protocol generation via RAG
3. Session comparison (planned vs. actual)
4. Weekly adaptation suggestions with explanations
5. Progress visualization (charts over time)

## Why This Idea Is Strong

- Solves a real problem: most gym-goers follow static plans and plateau
- Clear cumulative value: more logged sessions = smarter coaching
- Not a ChatGPT wrapper: requires your personal training history for value
- Good demo story: show weeks of data and the AI adapting in response
- Bridges personal interest (gym) with technical skills (AI/software engineering)
