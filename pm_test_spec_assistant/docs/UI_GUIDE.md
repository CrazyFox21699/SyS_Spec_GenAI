# ALEX UI guide (Phase 2.5)

## Stack

- Vanilla HTML + CSS + JS (no React)
- Fonts: **Inter** (UI), **JetBrains Mono** (code/trees)
- CSS: `tokens.css` → `components.css` → `style.css`

## Layout

| Area | Role |
|------|------|
| Sidebar 240px | Workflow steps 1–5 |
| Topbar grid | Job stats (6 columns, no wrap on desktop) |
| Content max 1440px | Page body |

## Test spec I/O

See `docs/TEST_SPEC_IO_FORMAT.md` — **Expected input** / **output** use `Given:` / `Precondition:` / `Then:` lines.

## Logic workspace

Structure first (full width), then definitions. Jump-to-source chips replace raw evidence dumps.

## Borders

Adjust `--ui-border-width` and `--ui-border-width-strong` in `tokens.css`.

## Cache bust

After CSS/JS changes, bump `?v=` on links in `index.html`.
