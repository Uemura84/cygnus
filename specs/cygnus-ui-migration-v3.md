# Cygnus UI Migration to v3 Visual Identity

Migrate the Cygnus product UI from the v1 visual system (DM Serif Display / DM Sans / JetBrains Mono + Signal Blue `#1e90ff`) to the v3 visual system (IBM Plex Serif / Sans / Mono + Cygnus Teal `#0e8f9a`). This is a single coordinated pass covering the React frontend, the PDF report generator, and the Google Fonts imports.

The authoritative design reference is the `Cygnus Product Vision` document Section 13 (already updated to v3 as of April 21, 2026). The visual-identity-content.md v3 spec at `/mnt/user-data/outputs/visual-identity-v3/visual-identity-content.md` is the content-layer sibling spec. Read Section 13 if you need to resolve any ambiguity; this prompt covers everything you need for the product UI specifically.

## Objectives

1. **Typography:** Replace DM Sans / DM Serif Display / JetBrains Mono with IBM Plex Sans / IBM Plex Serif / IBM Plex Mono across the entire product UI.
2. **Color:** Replace Signal Blue `#1e90ff` with Cygnus Teal `#0e8f9a` across the entire product UI, including all derived rgba values.
3. **CSS custom properties:** Update tokens in `frontend/src/index.css` (or equivalent) to match the v3 palette.
4. **PDF report generator:** Update font-family and color constants in `backend/report_pdf.py`.
5. **Extend palette:** Add three new derived tokens (`--navy-soft`, `--gridline-gray`, `--divider-gray`) used in the v3 system.
6. **Preserve one exception:** The DVA Shareholders color `#7EC8E3` (Light Blue) stays as-is — it is the documented DVA-specific variant and must not be changed.

## Explicit value mappings

Typography (every occurrence across the frontend and PDF generator):

| Old | New |
|---|---|
| `DM Serif Display` | `IBM Plex Serif` |
| `DM Sans` | `IBM Plex Sans` |
| `JetBrains Mono` | `IBM Plex Mono` |
| `'DM Serif Display'` | `'IBM Plex Serif'` |
| `'DM Sans'` | `'IBM Plex Sans'` |
| `'JetBrains Mono'` | `'IBM Plex Mono'` |
| `"DM Serif Display"` | `"IBM Plex Serif"` |
| `"DM Sans"` | `"IBM Plex Sans"` |
| `"JetBrains Mono"` | `"IBM Plex Mono"` |

Colors (every occurrence, including all derivations):

| Old | New |
|---|---|
| `#1e90ff` | `#0e8f9a` |
| `#1E90FF` | `#0E8F9A` |
| `rgba(30, 144, 255, <A>)` | `rgba(14, 143, 154, <A>)` |
| `rgba(30,144,255,<A>)` (no spaces) | `rgba(14,143,154,<A>)` |

The alpha value `<A>` in each rgba mapping is preserved — only the RGB triplet changes.

Google Fonts import (in `frontend/src/index.html` or wherever the `<link rel="stylesheet" ...>` is, and in any equivalent import in the PDF generator):

**Old:**
```
https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap
```

**New:**
```
https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;700&display=swap
```

CSS custom properties block in `frontend/src/index.css` (replace the entire `:root { ... }` design-token block):

**Old:**
```css
:root {
  --navy: #0b1f3a;
  --gray: #4a5568;
  --blue: #1e90ff;
  --offwhite: #f5f7fa;
  --charcoal: #2b2b2b;
  --blue-dim: rgba(30, 144, 255, 0.08);
  --blue-line: rgba(30, 144, 255, 0.25);
}
```

**New:**
```css
:root {
  --navy: #0b1f3a;
  --navy-soft: #1c2f4a;
  --gray: #4a5568;
  --teal: #0e8f9a;
  --gridline-gray: #9aa5b4;
  --divider-gray: #e2e6ec;
  --offwhite: #f5f7fa;
  --charcoal: #2b2b2b;
  --teal-dim: rgba(14, 143, 154, 0.08);
  --teal-line: rgba(14, 143, 154, 0.25);
}
```

CSS variable names used throughout the codebase (`var(--blue)`, `var(--blue-dim)`, `var(--blue-line)`) must be renamed to `var(--teal)`, `var(--teal-dim)`, `var(--teal-line)` respectively. There will be many call sites.

## Work plan (follow exactly in this order)

### Step 1 — Discovery pass (do not edit anything yet)

Run searches across the repo to map the scope of the change. Do all of the following and report findings before any edits:

1. Find every file that contains `#1e90ff` or `#1E90FF` (case-insensitive).
2. Find every file that contains `rgba(30` (this catches all Signal Blue rgba derivations regardless of spacing).
3. Find every file that contains `DM Sans`, `DM Serif Display`, or `JetBrains Mono`.
4. Find every CSS file that references `var(--blue`, `var(--blue-dim)`, or `var(--blue-line)`.
5. Find every file that contains the Google Fonts URL from the old mapping above.
6. Identify `backend/report_pdf.py` font and color constants (look for any font-name strings and hex color literals near chart-related or header-related code).
7. Confirm `#7EC8E3` (DVA Shareholders Light Blue) is present somewhere in the frontend chart code — this is the color that must **not** be changed.

Summarize the discovery as a file-by-file list: path, count of old-value occurrences, and a note on whether the file is frontend, backend, or config. Stop and present this summary before proceeding to Step 2.

### Step 2 — Edit frontend CSS tokens first

Edit `frontend/src/index.css` (or whatever file holds the `:root` token block):
- Replace the `:root { ... }` block wholesale with the new version above.
- Add the three new tokens (`--navy-soft`, `--gridline-gray`, `--divider-gray`) if they don't already exist.
- Rename `--blue` → `--teal`, `--blue-dim` → `--teal-dim`, `--blue-line` → `--teal-line` in this file.

### Step 3 — Update Google Fonts imports

- In `frontend/src/index.html` (or wherever the `<link rel="stylesheet">` imports DM Sans / DM Serif Display / JetBrains Mono), replace with the IBM Plex import URL above.
- If the fonts are imported via `@import` in a CSS file instead of a link tag, update that too.
- If `backend/report_pdf.py` uses reportlab's font registration (`pdfmetrics.registerFont(...)` or similar), update those registrations as well. If the PDF uses locally bundled font files rather than Google Fonts, note this for me — don't try to download or substitute font files yourself.

### Step 4 — Rename CSS variables across the frontend

Search-and-replace across all `.css`, `.jsx`, `.tsx`, `.js`, `.ts` files in `frontend/`:
- `var(--blue)` → `var(--teal)`
- `var(--blue-dim)` → `var(--teal-dim)`
- `var(--blue-line)` → `var(--teal-line)`

Be explicit about the parentheses — don't match `--blue` bare, as it could appear in comments, string literals, or hypothetical future code. Match only the `var(--blue)` pattern.

### Step 5 — Update hard-coded hex colors

Across every file in `frontend/` and `backend/`:
- Replace `#1e90ff` with `#0e8f9a`
- Replace `#1E90FF` with `#0E8F9A`
- **Do NOT touch** `#7EC8E3` or any derivation of it. This is the DVA Shareholders color and is preserved per the v3 spec.

For the rgba values:
- Replace the RGB triplet `30, 144, 255` with `14, 143, 154`
- Replace the RGB triplet `30,144,255` (no spaces) with `14,143,154`
- Preserve whatever alpha value follows

### Step 6 — Update hard-coded font-family strings

Across every file in `frontend/` and `backend/`:
- Replace `DM Serif Display` with `IBM Plex Serif` (preserving surrounding quotes)
- Replace `DM Sans` with `IBM Plex Sans` (preserving surrounding quotes)
- Replace `JetBrains Mono` with `IBM Plex Mono` (preserving surrounding quotes)

Watch for font-family CSS declarations that list a full stack (e.g., `font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif`). Only replace the branded family name; leave the fallback stack unchanged.

### Step 7 — Verify PDF report generator

Look specifically at `backend/report_pdf.py` (or wherever the PDF is built):
- Ensure font registration uses IBM Plex fonts (if the PDF uses reportlab, it likely registers TTF files by name — those names need to match the `IBM Plex *` strings now referenced in the code).
- Ensure chart color constants use `#0e8f9a` not `#1e90ff`.
- Ensure any section-header or cover-page color uses the new teal.
- The `#7EC8E3` DVA Shareholders color in PDF stakeholder charts must remain unchanged.

If the PDF generator uses locally bundled font files (not Google Fonts CDN), flag this. You will need to download the IBM Plex TTF files from Google Fonts and place them wherever the project's fonts directory is. Do not invent a path — check the existing DM Sans TTF location and mirror it.

### Step 8 — Visual QA checklist

After all edits, run the app locally and verify each of the following in the browser:

- [ ] Step 1-3 views render without any blue-on-blue or blue-on-teal mismatches
- [ ] Step 4 charts (margin trajectory, etc.): primary series is teal, not blue
- [ ] Step 5 quality scan badges: correct teal accent
- [ ] Step 6 finding cards: left-border accent is teal, finding code tag is teal-on-teal-dim
- [ ] Step 6 risk gauge: any arc fill in the relevant color uses teal
- [ ] Step 7 AI agent streaming text: renders in IBM Plex Sans
- [ ] Step 8 executive summary metric callout cards: left-border accent is teal, metric values in IBM Plex Mono
- [ ] Step 9 Q&A: suggested question chips are teal-on-teal-dim background
- [ ] DVA stakeholder chart: Shareholders is still `#7EC8E3` Light Blue (this is the preserved exception)
- [ ] PDF export: generate a report and verify fonts are IBM Plex and chart colors are teal
- [ ] Chart axis labels: IBM Plex Mono, readable (note that Plex Mono has different character widths than JetBrains Mono; tabular data may need column-width adjustment)
- [ ] Finding code tags (`COGS_DRIFT`, `AUD_GC`, etc.): IBM Plex Mono, no truncation

### Step 9 — Run existing tests

Run the full test suite:
- `npm test` (or `yarn test` / `pnpm test` — check `package.json` for the script name)
- Any Python tests (`pytest backend/tests/`)
- Report any failures. Color and font changes should not break functional tests, but visual regression tests or snapshot tests may fail. For snapshot tests, if the only difference is a hex color or font-family name change, regenerate the snapshot and include it in the commit. For anything else, stop and report.

## Out of scope (do NOT do any of the following)

- Do not touch `#7EC8E3` or any DVA Shareholders color. This is the documented DVA-specific variant.
- Do not add the stacked signals motif to the product UI. The motif is for content visuals (articles, posts, diagrams). In the product UI it has specific placement rules that I haven't decided yet.
- Do not change chart layouts, axis ranges, or any non-color / non-font visual element.
- Do not reorganize CSS file structure.
- Do not refactor components or rename files.
- Do not touch `cvm-demo-app-spec.md` or `product-vision-architecture.md` — these are design docs, already updated separately.
- Do not add new dependencies. IBM Plex fonts load from Google Fonts CDN; no npm package needed.

## Commit message

After all edits pass Visual QA and the test suite, create one commit with this message:

```
Migrate Cygnus UI to v3 visual identity

- Typography: DM Serif Display / DM Sans / JetBrains Mono → IBM Plex Serif / Sans / Mono
- Accent color: Signal Blue #1e90ff → Cygnus Teal #0e8f9a
- CSS custom properties: added --navy-soft, --gridline-gray, --divider-gray
- Renamed --blue / --blue-dim / --blue-line → --teal / --teal-dim / --teal-line
- Google Fonts import updated (frontend + PDF generator)
- DVA Shareholders #7EC8E3 preserved as documented DVA-specific variant

Spec references:
- visual-identity-content.md v3 (content layer)
- product-vision-architecture.md Section 13 (product layer)
```

## If you get stuck

Stop and ask rather than guessing. Specifically:
- If the PDF generator uses locally bundled font files and you don't find IBM Plex TTFs in the repo, stop and ask — do not try to download fonts or substitute.
- If a test fails in a way that seems unrelated to color or typography, stop and report.
- If you find a Signal Blue reference that seems intentional (e.g., embedded in an icon SVG that's part of a brand partner's logo), stop and ask before changing it.
- If you find the `:root` token block in more than one CSS file (suggesting duplicated or scattered definitions), stop and report before editing — this indicates a consolidation opportunity I'd want to review.

## Expected total scope

Based on the documented design system, a rough estimate of the affected surface area:
- ~1 CSS token file (the `:root` block in `frontend/src/index.css`)
- ~10-30 component files with inline color references or font-family declarations
- ~1 PDF report generator (`backend/report_pdf.py`)
- ~1 HTML import file for fonts
- ~1-5 test snapshots that need regeneration

If your discovery pass in Step 1 shows significantly more than this (e.g., 100+ files with hard-coded colors), stop and report — that suggests the existing code doesn't use the CSS token system consistently and would benefit from a refactor pass first.
