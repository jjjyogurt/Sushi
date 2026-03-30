# Design System

## Overview

A focused, minimal interface with a Notion-like tone: calm neutrals, clear hierarchy, and low visual noise.

The system prioritizes readability, predictable interactions, and subtle affordances over decorative effects.

## Colors

- **Primary** (`#2665FD`): CTAs, active states, key interactive elements
- **Secondary** (`#475569`): Supporting UI, chips, secondary actions
- **Background** (`#F7F7F5`): App/page background
- **Surface** (`#FFFFFF`): Cards, panels, form containers
- **Surface-muted** (`#F1F1EF`): Hover/soft container backgrounds
- **Border** (`#E6E8EB`): Inputs, cards, dividers
- **On-surface** (`#1F2937`): Primary text on light backgrounds
- **On-surface-muted** (`#6B7280`): Secondary/help text
- **Error** (`#D14343`): Validation errors, destructive actions

> Notes:
> - No purple hues.
> - Keep brand blue usage sparse (primary actions only).

## Typography

- **Headlines**: Inter, semi-bold (`600`)
  - H1: `32px/38px`
  - H2: `24px/30px`
  - H3: `18px/24px`
- **Body**: Inter, regular (`400`), `14–16px`, line-height `1.45–1.6`
- **Labels**: Inter, medium (`500`), `12px`, uppercase for section headers, letter spacing `0.04em`
- **Meta/Captions**: Inter, regular (`400`), `12px`, muted color

## Spacing & Layout

- Base spacing unit: `4px`
- Common rhythm: `8 / 12 / 16 / 24 / 32`
- Panel padding: `24–32px`
- Vertical section spacing: `24–40px`
- Keep long forms in grouped blocks with clear headings and separators

## Interaction Principles

- Prioritize clarity: one dominant CTA per view
- Keep feedback immediate: loading, success, and error states always visible
- Maintain consistent radius and border patterns across all surfaces
- Avoid excessive animation; use quick, subtle transitions (`120–180ms`)

## Accessibility

- Maintain minimum contrast ratio `4.5:1` for body text
- Ensure keyboard focus is visible on all interactive elements
- Keep tap targets at least `36px` high
- Avoid color-only status communication (pair with labels/icons)

## Do's and Don'ts

- Do use the primary color sparingly, only for the most important action
- Do keep corners consistent (`8px` standard, pills only for chips/badges)
- Do maintain at least `4.5:1` contrast ratio for text
- Do keep backgrounds neutral and clean
- Don’t mix rounded and sharp corners in the same view
- Don’t use purple hue or “AI-generated” glossy gradients
- Don’t overuse shadows, motion, or decorative effects