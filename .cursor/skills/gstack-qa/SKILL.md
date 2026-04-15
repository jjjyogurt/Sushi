---
name: gstack-qa
description: Runs a Garry Tan-style founder QA review to pressure-test product requests and uncover the highest-leverage version of the product. Use when the user asks for gstack QA, founder mode, strategic product critique, or wants to validate whether a feature request solves the real user problem.
---

# GSTACK QA

Use this skill to review product ideas with a high bar for taste, user empathy, and long-term leverage. Do not execute the ticket literally until the core user job is clear.

## Core Principle

Start with the more important question:

`What is this product actually for?`

Then decide whether the requested feature is the real product or only a surface implementation.

## When to Apply

Apply this skill when the user:
- Mentions "gstack qa", "Garry Tan", "founder mode", or strategic product review.
- Asks for a high-level feature review before implementation.
- Requests a better version of a feature, not just a literal build.

## Workflow

### 1) Reframe the Job to Be Done

Identify:
- Primary user segment.
- High-stakes moment where they need this product.
- Current workaround and why it fails.

Write a one-line product job statement before proposing solutions.

### 2) Run the GSTACK Questions

Use these six checks:

- `G - Goal Clarity`: Is the user outcome explicit and measurable?
- `S - Speed to Value`: Can users get to first success in under 60 seconds?
- `T - Trust and Quality`: What could make this feel unreliable, low-trust, or confusing?
- `A - Acquisition Fit`: How does this feature improve retention, referrals, or distribution?
- `C - Compounding Advantage`: What data, workflow, or UX loop gets better over time?
- `K - Kill Criteria`: What evidence would prove this direction is wrong?

For each letter, include:
1. Current request weakness.
2. Stronger product direction.
3. Fast validation step.

### 3) Design the 10-Star Version

Propose the smallest version that still feels premium and inevitable.

Use this ladder:
- `Now`: 1-2 week implementation with clear user value.
- `Next`: Follow-on improvements that remove major friction.
- `Later`: Compounding features that create defensibility.

### 4) Force Specificity

Always define:
- Key metric to move (activation, retention, conversion, or NPS).
- Success threshold and review window.
- Main failure risks and mitigations.

If information is missing, ask up to 3 focused questions and state assumptions explicitly.

## Output Format

Use this exact structure:

```markdown
## Real User Job
[One sentence job-to-be-done]

## Why the Literal Request Is Not Enough
- [Gap 1]
- [Gap 2]

## GSTACK QA
### G - Goal Clarity
- Weakness:
- Better Direction:
- Fast Validation:

### S - Speed to Value
- Weakness:
- Better Direction:
- Fast Validation:

### T - Trust and Quality
- Weakness:
- Better Direction:
- Fast Validation:

### A - Acquisition Fit
- Weakness:
- Better Direction:
- Fast Validation:

### C - Compounding Advantage
- Weakness:
- Better Direction:
- Fast Validation:

### K - Kill Criteria
- Weakness:
- Better Direction:
- Fast Validation:

## 10-Star Plan
- Now:
- Next:
- Later:

## Metrics and Decision Rule
- Primary metric:
- Success threshold:
- Review window:
- Stop/continue rule:
```

## Quality Bar

- Be decisive; do not hedge with generic advice.
- Prefer robust, stable solutions over clever complexity.
- Tie recommendations to user behavior, not internal preferences.
- Keep it concrete: examples, flows, and measurable outcomes.
