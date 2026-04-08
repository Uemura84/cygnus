# Sprint 4 — Brand Assets Installation + Design System Alignment

> **What this is:** Build spec for Claude Code. Final sprint of Phase 3. This sprint
> installs pre-built Cygnus brand assets (logomark SVGs, favicon, brand kit HTML),
> aligns the Step 6 module color scheme with the Cygnus design system, and performs
> a visual polish pass across the full 9-step pipeline.
>
> **Branch:** Continue on `phase3-common-model`.
>
> **Depends on:** Sprints 1–3 complete. All detection modules operational, signal
> stacking working, AI agent prompts updated.
>
> **Success criteria:**
> 1. Pre-built Cygnus logomark SVGs installed in the correct locations
> 2. Favicon replaced with Cygnus mark on navy background
> 3. Logo + wordmark appears in the app navigation header
> 4. Step 6 module section colors aligned with Cygnus design system
> 5. Visual polish pass: typography, spacing, and component consistency across all steps
> 6. Brand kit HTML installed and accessible
> 7. All regressions still pass, full pipeline works end-to-end
>
> **Reference:** `product-vision-architecture.md` (Section 13 — Design System)

---

## 1. Install Pre-Built Brand Assets

### 1.1 SVG files

Four SVG files are provided alongside this spec. They are final and approved.
Copy them to their correct locations:

```
frontend/public/
  cygnus-logo-dark.svg       ← mark + "CYGNUS" wordmark, blue on transparent (for navy bg)
  cygnus-logo-light.svg      ← mark + "CYGNUS" wordmark, navy on transparent (for light bg)
  cygnus-mark.svg            ← standalone accretion disk mark, no wordmark, 64×64 viewBox
  cygnus-favicon.svg         ← simplified 2-ring mark on navy rounded-square, 32×32 viewBox
```

**SVG construction (for reference only — do not modify):**

The accretion disk mark consists of:
- Three concentric ellipses (outer rx=28/ry=9, middle rx=21/ry=7, inner rx=14/ry=4.8)
  with increasing opacity (0.12 → 0.22 → 0.38)
- A solid Signal Blue core circle (r=5.5)
- A navy void circle inside the core (r=2.2)
- Dark variant: blue strokes/fill on transparent (for navy backgrounds)
- Light variant: navy strokes/fill on transparent (for white backgrounds)
- Favicon: only 2 rings, thicker strokes, larger core, on navy rounded rect

### 1.2 Favicon replacement

Update `index.html`:

```html
<link rel="icon" type="image/svg+xml" href="/cygnus-favicon.svg" />
```

Remove any reference to the Vite default favicon (`vite.svg` or similar).
Delete the Vite SVG file from `frontend/public/` if it exists.

### 1.3 Brand kit HTML

Copy `cygnus-brand-kit.html` to `frontend/public/cygnus-brand-kit.html`.

This is a standalone HTML file that loads Google Fonts and renders all brand
assets inline. Accessible at `/cygnus-brand-kit.html` when the frontend runs.

### 1.4 Do NOT modify the SVG files or brand kit

These files are final. Do not alter proportions, colors, opacities, stroke widths,
SVG structure, or any content in the brand kit HTML. They have been manually
reviewed and approved.

---

## 2. Navigation Header Update

### 2.1 Current state

The app header shows "Cygnus" as plain text on the navy navigation bar.

### 2.2 Target state

Replace the text with `cygnus-logo-dark.svg` (mark + wordmark for dark backgrounds).
Size the SVG so the mark height is roughly 28–32px, fitting within the nav bar.

**Implementation options (pick whichever works cleanly):**
- Inline the SVG contents in the React component
- `<img src="/cygnus-logo-dark.svg" />` with appropriate height
- CSS background-image

The wordmark in the SVG replaces the current text title — don't show both.
The rest of the header (company selector, language toggle, etc.) stays as-is.

---

## 3. Step 6 Module Colors — Design System Alignment

### 3.1 The problem

Sprint 3 introduced module section colors in Step 6:
- Profitability: Blue (#1d4ed8) header + #eff6ff accent
- Balance Sheet: Green (#065f46) header + #ecfdf5 accent
- Cash Flow: Purple (#7c3aed) header + #f5f3ff accent
- Diagnoses: Blue-dim

The green and purple are outside the Cygnus five-color palette.

### 3.2 Target: stay within the Cygnus palette

Replace the module section styling. All module headers should use navy (#0b1f3a)
background with white text. Differentiate modules through one of these approaches:

**Option A — Opacity-based left border (recommended):**
- Profitability: 4px left border, Signal Blue (#1e90ff) at full opacity
- Balance Sheet: 4px left border, Signal Blue at 60% opacity
- Cash Flow: 4px left border, Signal Blue at 40% opacity
- Diagnoses: 4px left border, Signal Blue at full opacity + blue-dim card background

**Option B — Badge differentiation:**
- All sections use the same navy header
- Each module gets an identifier badge in JetBrains Mono on blue-dim background:
  P (profitability), BS (balance sheet), CF (cash flow), DX (diagnoses)

Either option works. The hard constraint: **no colors outside navy, signal blue,
slate, off-white, charcoal** plus severity colors (amber #EF9F27, red #E24B4A).
Use CSS custom properties (--navy, --blue, etc.), not hardcoded hex values.

### 3.3 Diagnosis cards

DiagnosisCard from Sprint 3 uses blue-dim background — already within the design
system, keep it. Ensure contributing signals panel uses design system colors
(slate text, blue-line borders).

### 3.4 Module count badges

The module count badge row (finding counts per module) should also use design
system colors if it currently uses green/purple.

---

## 4. Visual Polish Pass

### 4.1 Audit checklist

Walk through every step (1–9) in the browser and fix deviations from Section 13
of `product-vision-architecture.md`.

**Typography checks:**
- [ ] DM Serif Display appears ONLY in Step 8 (Executive Summary narrative)
- [ ] DM Sans for all product UI headings, buttons, body text
- [ ] JetBrains Mono for finding codes, metric values, section labels, severity badges
- [ ] No fallback fonts visible (Google Fonts loading correctly)
- [ ] Font weights: DM Sans 400 body, 500 headings, 600 buttons

**Color checks:**
- [ ] Navy (#0b1f3a) for nav bar, sidebar, footer
- [ ] Off-white (#f5f7fa) for content area background
- [ ] Signal Blue (#1e90ff) for accents, interactive elements, chart lines
- [ ] Slate (#4a5568) for body text, secondary information
- [ ] Charcoal (#2b2b2b) for headlines on light backgrounds
- [ ] All colors via CSS custom properties (--navy, --blue, etc.)
- [ ] Severity: amber (#EF9F27) for MEDIUM, red (#E24B4A) for HIGH/CRITICAL

**Card and panel checks:**
- [ ] Off-white background, 1px border at rgba(11,31,58,0.07), 6px border-radius
- [ ] Hover: border to rgba(30,144,255,0.25) with subtle box-shadow
- [ ] Finding cards: monospace code tag in blue on blue-dim, severity left border
- [ ] Metric displays: blue left-border accent (2px solid at 30% opacity)

**Section label checks:**
- [ ] JetBrains Mono, 10-11px, uppercase, letter-spacing 0.12-0.15em, Signal Blue

**Chart checks:**
- [ ] Chart lines/fills use blue ramp at varying opacities
- [ ] Grid lines at rgba(11,31,58,0.06)
- [ ] Axis labels in JetBrains Mono 11px
- [ ] Annotations in JetBrains Mono
- [ ] Step 4 BS + CF charts match profitability chart styling

**Step-specific checks:**
- [ ] Steps 1–3: Minimal UI, monospace for account codes
- [ ] Steps 4–5: Charts dominate, DM Sans labels, JetBrains Mono values
- [ ] Step 6: Finding cards with severity borders, risk gauge, module sections
- [ ] Step 7: Streaming text in DM Sans, hypothesis cards
- [ ] Step 8: DM Serif Display for narrative ONLY
- [ ] Step 9: Chat interface, suggested question chips in blue-dim

### 4.2 Cross-statement warnings display (Step 5)

Sprint 2 showed high warning counts (Braskem 21, Vale 19, Votorantim 11).
Review the Step 5 cross-statement warnings section and consolidate if overwhelming:
- Group by check type ("D&A consistency: 5 periods, minor differences")
- Show HIGH severity expanded, MEDIUM collapsed by default
- Add summary count at top ("3 checks, 21 periods examined, 0 critical")
- Goal: "data quality validated" at a glance, not a wall of warning rows

### 4.3 Step 4 chart consistency

Verify the 8 Sprint 2 charts match the profitability chart styling:
- Same chart height and responsive behavior
- Same tooltip formatting
- Same axis label fonts (JetBrains Mono 11px)
- Same grid line opacity and legend style
- Reference lines (y=0, y=1.0) styled consistently

---

## 5. What Does NOT Change

- **Backend:** No backend changes. Detection, stacking, AI agent code untouched.
- **API responses:** No changes to any response shapes.
- **Detection algorithms:** No threshold changes, no new finding codes.
- **Steps 7–9 prompts:** No changes.
- **SVG files and brand kit HTML:** Do not modify (provided as final assets).

---

## 6. Testing Checklist

### 6.1 Brand assets
- [ ] All 4 SVG files present in `frontend/public/`
- [ ] `cygnus-brand-kit.html` present in `frontend/public/`
- [ ] Favicon shows Cygnus mark in browser tab (not Vite logo)
- [ ] Vite default favicon file removed
- [ ] Nav header shows Cygnus logo + wordmark SVG
- [ ] Brand kit page loads at `/cygnus-brand-kit.html`

### 6.2 Design system alignment
- [ ] Step 6 module sections use Cygnus palette only (no green, no purple)
- [ ] Module sections still visually distinguishable
- [ ] Diagnosis cards use blue-dim background
- [ ] Module count badges use design system colors
- [ ] Severity colors correct throughout

### 6.3 Visual polish
- [ ] Typography audit passes
- [ ] Color audit passes
- [ ] Card styling consistent across all steps
- [ ] Section labels consistent across all steps
- [ ] Charts consistent between profitability, BS, and CF
- [ ] Step 5 warnings display clean and not overwhelming

### 6.4 Regression
- [ ] Sprint 1 regression tests pass
- [ ] Sprint 2 regression tests pass
- [ ] Full pipeline works end-to-end for Braskem
- [ ] Full pipeline works end-to-end for Vale
- [ ] Full pipeline works end-to-end for Votorantim
- [ ] No console errors in frontend

---

## 7. Definition of Done

- [ ] 4 Cygnus SVG files + brand kit HTML installed in `frontend/public/`
- [ ] Favicon replaced (Vite default removed)
- [ ] Nav header shows Cygnus logo + wordmark
- [ ] Step 6 module colors aligned with Cygnus design system
- [ ] Visual polish pass completed
- [ ] Step 5 warnings display reviewed and cleaned up
- [ ] All regressions pass
- [ ] All 3 test companies work end-to-end
- [ ] Code committed and pushed to `phase3-common-model` branch
- [ ] Branch ready for merge to master
