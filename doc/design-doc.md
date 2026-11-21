# Design document: Dirigera Qt dashboard

Version 1.0 · Scope: the desktop window only, light theme only.

This document is the single reference for the dashboard's look, layout, components
and behaviour. Facts about the `dirigera` library are in `dirigera-api.md`, Qt
pitfalls in `qt-gotchas.md`, and the exact token values in `theme.py`.

It defines no `req-` or `t-` IDs; it cites them from `doc/reqs.md` and
`agent-notes/todo.md`. It is the target design: where the code differs, the gap is
tracked in the "Design conformance gaps" section of `agent-notes/todo.md`, and the
document is not wrong. Where this document and `theme.py` disagree on a value, the
code wins and this document is the bug.

## 0. How to read this document

Tags mark the basis of non-obvious statements:

| Tag | Meaning |
| --- | --- |
| `[decided]` | Chosen by the owner |
| `[verified]` | Checked in a PyQt 6.12.1 offscreen render, a computed contrast ratio, or a test in `tests/` |
| `[lib]` | Taken from the installed `dirigera` 1.6.1 source or its README |
| `[known]` | General Qt knowledge, not re-tested |
| `[proposed]` | Designer's proposal, open to change |

Anything that still needs a decision or data is listed in section 14, not inline;
inline text points there.

Known limit: the verified renders used Linux with DejaVu Sans. The target is
Windows 10/11 with Segoe UI (section 14, item 11).

## 1. Purpose and principles

The dashboard is a calm control panel for a smart home. The user opens it to check
state and make small changes, not to explore.

Four adjectives govern every decision: `[decided]` calm, precise, honest, unfussy.

Principles, in priority order:

1. **Show real state.** Every displayed value comes from the hub or is marked as stale.
   Never show a hopeful or inferred state (`req-1`, `req-3`).
2. **Make the state readable first.** A user should identify each device's condition
   from the card header before reading its control.
3. **One accent per view.** Blue marks on-state and the focused control. Everything
   else is neutral.
4. **Never rely on colour alone.** Each state has a colour, an icon or a word; the word
   is what a screen reader reads.
5. **Density is the default.** Many devices per screen; no decoration that takes space.
6. **Stable layout.** Refresh and events never reorder cards or move controls.

Anti-goals: no neon, gloss, skeuomorphic bulbs or dials, no gamification, no
stock imagery, no animation for its own sake.

## 2. Naming and trademark

1. Do not use IKEA's logo, wordmark, product imagery, or its yellow and blue as a brand
   palette. `[proposed]`
2. "Dirigera" is an IKEA product name. Use it only descriptively in running text. The
   `dirigera` library describes itself as an unofficial client `[lib]`. Show an
   "unofficial" notice in About and the README. `[proposed]`
3. The application name is undecided (section 14, item 1). Check it is free to use before
   creating icons.

## 3. Information architecture

### 3.1 Views

| # | View | Purpose | Content |
| --- | --- | --- | --- |
| 1 | Rooms (default) | Check and control devices | All devices, grouped by room, one page |
| 2 | Scenes | Activate scenes | Scene tiles |
| 3 | Energy | See live power use | Outlets and electrical sensors with metering |

`[decided]` Views are switched by a segmented control in the header. There is no
navigation rail; room sections are labelled within the page. `[decided]` If the number
of rooms grows, add a row of room chips under the header, not a rail. `[proposed]`

### 3.2 Connection states

| # | State | Header chip | Content |
| --- | --- | --- | --- |
| 1 | Not connected | Grey "Not connected" | Connect block (section 9.1) |
| 2 | Connecting | Grey "Connecting…" | Connect block with controls disabled |
| 3 | Connected | Green "Hub online · <ip>" | Views with data |
| 4 | Refresh failed | Amber "Hub unreachable" | Last good data, with caption "Showing data from <time>" |

The chip shows "online" only after an authenticated probe succeeds (`req-1`).

## 4. Layout

### 4.1 Window

1. Default size 1080 × 700 px. `[verified]`
2. Minimum size 640 × 480 px. `[proposed]`
3. Structure, top to bottom: header bar (56 px), content area (fills, scrolls
   vertically). `[verified]`

### 4.2 Header bar

Left to right: app title (18 px, semibold); hub status chip; flexible space; search
field (260 px); segmented view switcher; Refresh button. `[verified]`

Padding: 20 px horizontal, 12 px vertical. Bottom border 1 px `border` token. `[verified]`

Below 900 px window width the header has two 48 px rows: row 1 as above (search field
fills the free width), row 2 the view switcher, left-aligned. `[verified]`

### 4.3 Content area

1. Padding 24 px horizontal, 20 px top, 24 px bottom. `[verified]`
2. Room sections stacked vertically; gap between sections 24 px. `[verified]`
3. Each section: label (13 px, medium, `text-2`), 12 px gap, card grid. `[verified]`
4. Card grid: width-driven, cards 280 px minimum, gaps 16 px horizontal and vertical.
   Column count = the largest number that fits. `[verified]`

### 4.4 Spacing scale

Base unit 4 px. Use only these values: 4, 8, 12, 16, 20, 24. `[proposed]`

| Use | Value |
| --- | --- |
| Card padding | 16 |
| Gap between card zones | 12 |
| Gap between controls in a row | 8 |
| Gap between cards | 16 |
| Gap between sections | 24 |

## 5. Colour

### 5.1 Tokens

Light theme only. Values live in `theme.py` (one constant per token, upper-cased:
`ACCENT`, `TEXT2`, ...); this table gives the role of each.

| # | Token | Use |
| --- | --- | --- |
| 1 | `window` | Window background |
| 2 | `surface` | Cards, header, content areas |
| 3 | `sunken` | Slider tracks, offline cards, search field, hover |
| 4 | `border` | Card and header outlines (decorative, not text) |
| 5 | `text` | Primary text |
| 6 | `text-2` | Captions, units, types, labels |
| 7 | `accent` | On-state, primary action, focus ring, slider fill |
| 8 | `accent-hover` | Primary button hover |
| 9 | `on-accent` | Text on accent |
| 10 | `accent-soft` | Selected segment, selected room |
| 11 | `off` | Switch track when off |
| 12 | `ok` | Ok chip text |
| 13 | `ok-bg` | Ok chip background |
| 14 | `warn` | Warning chip text |
| 15 | `warn-bg` | Warning chip background |
| 16 | `danger` | Danger chip text, error text |
| 17 | `danger-bg` | Danger chip background |

### 5.2 Contrast requirements

Every text pairing must meet 4.5:1. Non-text indicators (switch track, focus ring,
slider handle) must meet 3:1 against their background. `[verified]` (test)

The pairings are listed in `tests/test_theme_contrast.py`, which asserts both
thresholds on every run. Add a pairing there when a new token is used.

### 5.3 Colour rules

1. Use `accent` for one thing per view: the on-state of the focused control or the
   primary action. `[decided]`
2. `warn` and `danger` are reserved for conditions the user should notice. An ordinary
   "off" is neutral `text-2`. `[proposed]`
3. Never put coloured text on a coloured card. Use chips for status text. `[proposed]`
4. The only gradient in the app is the colour-temperature track (warm to cool), since
   it encodes a real scale. `[proposed]`

## 6. Typography

### 6.1 Typeface

1. Windows: `Segoe UI Variable`, falling back to `Segoe UI`. `[proposed]` Availability of
   the Variable face is unchecked (section 14, item 11).
2. Other platforms: system UI sans-serif. `[proposed]`
3. Numeric values should use tabular figures where available so changing values do not
   shift layout. Whether Qt applies this on Windows is unchecked (section 14, item 11); if not, give numeric
   labels a fixed minimum width.

### 6.2 Scale

| # | Role | Size | Weight | Used for |
| --- | --- | --- | --- | --- |
| 1 | Metric | 28 px | 600 | Key sensor readings |
| 2 | App title | 18 px | 600 | Header title |
| 3 | Title | 16 px | 600 | Card names |
| 4 | Body | 14 px | 400 | Controls and values |
| 5 | Label | 13 px | 500 | Section labels, slider labels |
| 6 | Caption | 12 px | 400 | Types, units, footers, chips |

Rules:

1. No more than three sizes in one card. `[proposed]`
2. Sentence case everywhere. No all-caps labels. `[decided]` in spirit; `[proposed]`
   as a rule.
3. Units are smaller and secondary, placed beside the number, never on their own line.
   `[verified]`

## 7. Shape, depth and icons

### 7.1 Shape

| # | Element | Radius |
| --- | --- | --- |
| 1 | Card | 10 px |
| 2 | Button, search field, segment group | 6 px |
| 3 | Chip | Fully rounded (half the 20 px chip height; `theme.RADIUS_CHIP`) |
| 4 | Switch | Fully rounded |
| 5 | Slider track and thumb | Fully rounded |

### 7.2 Depth

No shadows, no elevation. Separation is by background (`surface` on `window`) and the
1 px `border`. Qt drop shadows are costly inside scroll areas and clip. `[proposed]`

### 7.3 Icons

1. Monoline, 24 px grid, 1.5 px stroke, round caps and joins. `[proposed]`
2. Rendered from SVG strings in code (`widgets/icons.py`) via `QtSvg`, recoloured
   by substituting `currentColor` with the token.
3. Required set: one per device category, status (ok, warn, danger, offline, moving,
   battery 0 to 4), actions (scene play, undo, refresh, settings), and a generic scene
   glyph.
4. Scene icons: the hub has 38 values `[lib]`. Map common ones; use the generic glyph
   for the rest in version 1.
5. Licence of any icon set used must allow redistribution in a desktop app
   (section 14, item 6).

## 8. Components

Each component lists its anatomy, states and rules. "Verified" means it rendered
correctly in the mockup.

### 8.1 Device card

Anatomy, top to bottom, 16 px padding, 12 px gaps:

1. Header row: name (title) over type (caption, `text-2`) on the left; status chip on
   the right. `[verified]`
2. Control zone: zero to three controls. `[verified]`
3. Footer: one caption line (battery, last change, hint, or "Last seen …"). `[verified]`

Size: 280 px minimum width, height determined by content. Border 1 px `border`,
radius 10 px, background `surface`. `[verified]`

States:

| # | State | Appearance | Behaviour |
| --- | --- | --- | --- |
| 1 | Normal | As above | All controls enabled |
| 2 | Offline | Background `sunken`; chip "Offline"; footer "Last seen <relative time>" | Controls disabled; card keeps grid position |
| 3 | Pending command | Changed control stays in place; footer "Sending…" | Resolves to hub value or reverts on failure (`req-3`) |
| 4 | Attention | Chip in warn or danger colour with the specific fact | No other change |
| 5 | Read-only | No control zone | Shorter card; no disabled control placeholder |

Rules:

1. A card is not clickable as a whole; only its controls are. `[proposed]`
2. Device name never wraps. If it does not fit, truncate with an ellipsis and show the
   full name in a tooltip. `[proposed]`; check with Windows fonts (section 14, item 11).
3. The card's order within its room is type, then name, using the order: lights,
   outlets, blinds, air and environment, sensors, remotes. A stable order prevents
   layout shifts on refresh. `[proposed]`

### 8.2 Status chip

| # | Property | Value |
| --- | --- | --- |
| 1 | Height | 20 px |
| 2 | Padding | 2 px vertical, 9 px horizontal |
| 3 | Font | Caption, 12 px |
| 4 | Text | One or two words; never a value or percentage |
| 5 | Max per card | One |

Variants:

| # | Variant | Text colour | Background |
| --- | --- | --- | --- |
| 1 | ok | `ok` | `ok-bg` |
| 2 | warn | `warn` | `warn-bg` |
| 3 | danger | `danger` | `danger-bg` |
| 4 | neutral | `text-2` | `sunken` |

### 8.3 Switch

1. Size 44 × 24 px. Thumb: 18 px diameter, white, 3 px inset. `[verified]`
2. Track on: `accent`. Track off: `off`. Disabled: muted tones of the same. `[verified]`
3. Thumb moves over 120 ms, out-cubic easing. `[verified]`
4. Focus: 2 px accent ring, inset. `[verified]`
5. Accessible name set on each instance, for example "Bookshelf power". `[proposed]`
6. Implemented as a custom `QAbstractButton` subclass with a `thumb` property
   (`widgets/switch.py`; property naming in `qt-gotchas.md`).

### 8.4 Slider

1. Fixed label column on the left (13 px label), so sliders align across cards.
   `[verified]`
2. Track 6 px high, rounded; filled part `accent`; unfilled part `sunken`. Thumb 18 px
   white with a 2 px `accent` border. `[verified]`
3. Slider minimum height 24 px so the thumb is not clipped. `[verified]`
4. Value on the right in a fixed-width column, right aligned, body size. `[verified]`
5. Value updates live while dragging. The command is sent on release or after a short
   pause (`req-6`). `[verified]` (test)
6. Minimum on light brightness is 1 %, not 0 (the library rejects 0) `[lib]`.
7. Colour-temperature slider: warm-to-cool gradient track (`TEMP_WARM` to `TEMP_COOL`).
   `[verified]` (test for behaviour; the rendering itself is not asserted)
8. Disabled state: track and thumb in muted tones of the enabled colours (see
   `qt-gotchas.md`, item 4).

### 8.5 Metric

1. Value at metric size (28 px, semibold); unit beside it at caption size, `text-2`,
   baseline aligned. `[verified]`
2. Caption beneath the value naming the reading ("Temperature", "Humidity"). `[verified]`
3. A metric group places 2 to 3 metrics side by side with 20 px gaps. `[verified]`
4. Use metrics only for numbers. Words such as "Closed" are a title or a chip, not a
   metric. `[verified]` (a correction made during the mockup review)

### 8.6 Segmented control

1. Segments joined; outer corners rounded 6 px; inner corners square. `[verified]`
2. Selected segment: `accent-soft` background, `accent` text and border.
   `[verified]`
3. Exclusive selection; keyboard arrows move between segments. `[proposed]`
4. Used for the view switcher and fan modes. `[proposed]`

### 8.7 Buttons

| # | Variant | Look | Use |
| --- | --- | --- | --- |
| 1 | Primary | `accent` fill, `on-accent` text, 6 px radius, semibold, 7 × 16 px padding | Activate scene, Connect |
| 2 | Ghost | Transparent, 1 px `border`, `text` label, 6 px radius | Refresh, secondary actions |

States: hover moves background one step toward `sunken` (ghost) or `accent-hover`
(primary). Disabled: primary fill `#C9CFDA` with `text-2` text. `[verified]` for
the primary and ghost styles; disabled colour `[proposed]`.

### 8.8 Search field

1. 260 px wide, 6 px radius, `sunken` background, 1 px transparent border. `[verified]`
2. On focus: `surface` background and 1 px `accent` border. `[verified]`
3. Placeholder "Search devices and scenes". Filters both devices and scenes as you type.
   `[verified]` — case-insensitive on the full name, in the Rooms and Scenes views.
   A room section hides when none of its cards match; hidden cards keep their
   position so clearing the query restores the previous order. `[verified]`

### 8.9 Section label

Label size, medium weight, `text-2`, sentence case. Placed above each room's card grid.
`[verified]`

### 8.10 Scene tile

1. Minimum width 240 px; same card surface as device cards. `[proposed]`
2. Anatomy: glyph, name (title), primary button "Activate" aligned right or bottom. `[proposed]`
3. After activation, the button area shows "Activated" in `ok` text for about two
   seconds, then returns. No modal dialog. `[proposed]`
4. No undo after activation (section 14, item 12).
5. Automatic scenes are those the IKEA app creates itself: every scene whose type is not
   `userScene` (on the test hub, the `customScene` "Smart Notifications@…" entries). They
   are hidden by default and shown when "Show automatic scenes" is enabled; the choice is
   remembered (section 14, item 3; t-90).

### 8.11 Energy card

1. Metric: live power in W. Captions: current in A and voltage in V. Footer: total in
   kWh. `[lib]`
2. Plugs without metering: footer reads "No energy data"; no empty metric row. `[proposed]`
3. No history graphs. `[proposed]`

### 8.12 Connection block (not-connected state)

Centred in the content area: heading "Connect to your hub", one help line, IP field,
token field, Discover and Connect buttons. No grid behind it. `[proposed]`

### 8.13 Skeleton

Used only on first load: shapes at card size in `sunken`, no animation. `[proposed]`

### 8.14 Inline status

Status messages appear inline, in the affected area, with text and an icon. Toast
notifications and modal dialogs are not used for routine outcomes. Modal dialogs remain
for destructive confirmations and for choices the user must make. Today the only
modal is the hub chooser (`HubSelectionDialog`). `[proposed]`

## 9. Screens

### 9.1 Not connected

Header: title, grey chip "Not connected", search and view switcher disabled. Content:
connection block (8.12). `[proposed]`

### 9.2 Rooms

Header as in 4.2 with the Rooms segment selected. Content: room sections in order, each
with its label and card grid. Sections are ordered alphabetically (section 14, item 2). `[verified]`

### 9.3 Scenes

Same header with the Scenes segment selected. Content: scene tiles in a width-driven
grid, with a "Show automatic scenes" toggle above the grid (off by default; t-90).

### 9.4 Energy

Same header with the Energy segment selected. Content: energy cards grouped by room.
Whether totals are shown per home or per room is undecided (section 14, item 5).

## 10. Behaviour

### 10.1 Commands

1. Every command runs off the GUI thread (`req-4`); one shared hub session
   (`dirigera-api.md`).
2. Slider commands are coalesced; the latest value wins (`req-6`). `[proposed]`
3. On failure, the control is resynchronised with the device's real state (`req-3`).
   `[verified]` (test)
4. A command in flight shows "Sending…" in the card footer. `[proposed]`

### 10.2 Refresh

1. Refresh runs in a worker. The Refresh button shows "Refreshing…" and is disabled
   during the run. `[proposed]`
2. The current view is only rebuilt after all data has been fetched successfully
   (`req-2`). `[verified]` (test)
3. On failure, the last good data stays and the hub chip turns amber (3.2). `[proposed]`
4. Card order, scroll position and focus are preserved across refresh (`t-19`). Cards
   are updated in place, matched by device id; new ids add a card, vanished ids remove
   it, and a slider being dragged or focused keeps its value. A fetch identical to the
   last one changes nothing. `[verified]` (test)
5. Polling (`req-13`, `t-56`): the dashboard refreshes by itself every 30 s while a hub
   is connected. A poll is skipped, not queued, while a fetch is in flight and while the
   window is minimised; restoring the window polls at once. `[verified]` (test)
6. The status row shows `Updated HH:MM · every 30 s`; it turns warn when the last success
   is older than two intervals. `[verified]` (test)
7. A failed background poll shows no modal dialog: the hub chip turns amber and the
   stale caption appears (3.2). A failed manual refresh still reports in a dialog until
   `t-66` replaces it. `[verified]` (test)
8. A scene activation triggers a background refresh after a short delay (1.5 s). `[verified]` (test)

### 10.3 Live updates

1. Live updates are planned (`t-16`). The design must work without them: values update
   on refresh.
2. The event listener is blocking and the hub closes idle connections; the design
   assumes it may stop and must be restarted, and that events during a reconnect are
   lost, so a full refetch follows reconnection `[lib]`.

### 10.4 Motion

1. Switch and segment changes animate over 120 ms. `[verified]`
2. Section expansion is not used. `[proposed]`
3. Values updating several times a second do not animate. `[proposed]`
4. Skeletons do not animate. `[proposed]`
5. No reduced-motion setting: the only animations are the 120 ms switch and segment
   changes (section 14, item 7).

### 10.5 Keyboard

1. Every control reachable by Tab in the order it appears. `[proposed]`
2. Segments: arrow keys move selection. `[proposed]`
3. Switches: Space toggles. `[proposed]`
4. Sliders: arrow keys step, Page keys step larger. `[proposed]`
5. Focus ring always visible on the focused control. `[verified]`

## 11. Responsive behaviour

| # | Window width | Layout |
| --- | --- | --- |
| 1 | 1080 px and wider | Three card columns at 280 px minimum |
| 2 | About 760 px | Two columns; search field shrinks to about 180 px |
| 3 | Under 640 px | One column |
| 4 | Under 900 px | View switcher moves to a second header row |

Minimum window size 640 × 480 px. `[proposed]`

Check that slider label and value columns still fit at 150 % scaling on Windows (section 14, item 11).

## 12. Accessibility

1. Every state carries a word or icon, not only a colour (section 1, principle 4).
   `[proposed]`
2. Contrast per section 5.2. `[verified]`
3. Every interactive control has an accessible name. `[proposed]`
4. Focus indicator is never removed. `[verified]`
5. Text scales with the system font size where Qt honours it on Windows (section 14,
   item 11).
6. Grayscale screenshots must still show each device's state. `[proposed]`

## 13. Implementation guidance

### 13.1 Structure

1. Put every token in one module as data, and generate the stylesheet from it. Do not
   hard-code colours in widgets. `[proposed]`
2. Theme module, icon module (SVG strings), and widget modules per component. Keep the
   flat module layout described in `AGENTS.md`. `[proposed]`
3. Each card is a widget built from its device type; the mapping from device type to
   controls is in `dirigera-api.md`, section 3. `[proposed]`

### 13.2 Qt pitfalls

See `qt-gotchas.md`.

### 13.3 Performance

1. Build cards once per refresh and update in place where possible (`t-10`, `t-19`).
   `[proposed]`
2. Avoid drop shadows and per-widget effects inside scroll areas. `[known]`
3. Refresh makes many hub calls, one per device class, each with a 10 s timeout
   `[lib]`. Measure before optimising (section 14, item 13).

## 14. Decisions

| # | Decision | Status |
| --- | --- | --- |
| 1 | Application name | Decided: keep "Dirigera Dashboard" |
| 2 | Room section order | Decided and implemented: alphabetical, case-insensitive |
| 3 | Show automatic scenes by default | Decided: no; non-`userScene` scenes are hidden behind a toggle (t-90) |
| 4 | Low-battery threshold | Decided and implemented: 20 % (`LOW_BATTERY_PERCENT`) |
| 5 | Energy totals per home or per room | Decided: a total per room and one home total (t-87) |
| 6 | Icon source | Decided and implemented: icons drawn in code (`widgets/icons.py`) |
| 7 | Reduced-motion behaviour on Windows | Decided: no setting; animations stay as they are |
| 8 | Colour-temperature gradient rendering | Decided and implemented: groove gradient between `TEMP_WARM` and `TEMP_COOL`, no fill |
| 9 | Air-quality colour bands | Decided: WHO-style PM2.5 bands, good ≤ 15, moderate ≤ 35, poor above (µg/m³), shown with a word, never colour alone (t-88) |
| 10 | Disabled control colours | Decided and implemented: muted tones of enabled colours, checked by `tests/test_theme_contrast.py` |
| 11 | Windows verification: Segoe UI Variable, tabular figures, name truncation, 150 % scaling, text scaling | Checked by the owner on Windows (2026-11-21): looks fine |
| 12 | Scene undo | Decided: no undo |
| 13 | Refresh cost | Checked on a real hub (2026-11-21): fast enough, no optimisation |

## 15. Acceptance checklist

Items marked A are asserted by tests in `tests/`; M items are checked by hand.

1. A: every text pairing in section 5.2 is at or above 4.5:1; every indicator at or
   above 3:1.
2. M: a grayscale screenshot shows every device's state.
3. M: no card has more than one accent item, apart from its own switch on-state.
4. M: no raw `device_type`, enum repr, bare check mark, or unexplained icon appears on
   screen.
5. M: spacing and radii use only the values in sections 4.4 and 7.1.
6. M: long names truncate with a tooltip and never wrap.
7. M: every control is reachable by keyboard, with a visible focus ring.
8. M: offline cards keep their grid position after refresh.
9. M: layout is correct at 1080, 760 and 640 px widths.
10. M: verified on Windows at 100 % and 150 % scaling with Segoe UI, in the light
    theme.
