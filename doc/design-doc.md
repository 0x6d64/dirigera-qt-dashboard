# Design document: Dirigera Qt dashboard

Version 1.0 · Scope: the desktop window only, light theme only.

This document is the single reference for the dashboard's look, layout, components
and behaviour. An implementer should be able to build from it without the earlier
working documents. It consolidates `visual-language-identity.md`, `look-and-feel.md`
and `qt-device-widget-mapping.md`. Where this document and those disagree, this one
wins and the disagreement is a bug to report.

It changes no project file and defines no `req-` or `t-` IDs. Existing IDs are cited
from `doc/reqs.md` and `agent-notes/todo.md`.

## 0. How to read this document

Tags mark the basis of non-obvious statements:

| Tag | Meaning |
| --- | --- |
| `[decided]` | Chosen by the owner |
| `[verified]` | Checked in a PyQt 6.12.1 offscreen render or a computed contrast ratio |
| `[lib]` | Taken from the installed `dirigera` 1.6.1 source or its README |
| `[proposed]` | Designer's proposal, open to change |
| `[open]` | Needs a decision or data before it can be finalised |

Known limits:

1. The verified renders used Linux with DejaVu Sans. The target is Windows 10/11 with
   Segoe UI. Re-check layout and truncation on Windows before release.
2. No live hub data was used. Device values in the mockup are invented.
3. The app name is a placeholder ("Home") until decided (section 15).

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
3. The application name is `[open]` (section 15). Check it is free to use before
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

Light theme only. Values were contrast-checked `[verified]`.

| # | Token | Value | Use |
| --- | --- | --- | --- |
| 1 | `window` | `#F4F5F7` | Window background |
| 2 | `surface` | `#FFFFFF` | Cards, header, rail-free content |
| 3 | `sunken` | `#ECEEF1` | Slider tracks, offline cards, search field, hover |
| 4 | `border` | `#D5D9E0` | Card and header outlines (decorative, not text) |
| 5 | `text` | `#1A1D23` | Primary text |
| 6 | `text-2` | `#505968` | Captions, units, types, labels |
| 7 | `accent` | `#1F5FD1` | On-state, primary action, focus ring, slider fill |
| 8 | `accent-hover` | `#1A50B3` | Primary button hover |
| 9 | `on-accent` | `#FFFFFF` | Text on accent |
| 10 | `accent-soft` | `#E6EEFC` | Selected segment, selected room |
| 11 | `off` | `#7C8696` | Switch track when off |
| 12 | `ok` | `#17753A` | Ok chip text |
| 13 | `ok-bg` | `#E3F4EA` | Ok chip background |
| 14 | `warn` | `#8F4A00` | Warning chip text |
| 15 | `warn-bg` | `#FBE9D7` | Warning chip background |
| 16 | `danger` | `#B3261E` | Danger chip text, error text |
| 17 | `danger-bg` | `#FBE4E2` | Danger chip background |

### 5.2 Contrast requirements

Every text pairing must meet 4.5:1. Non-text indicators (switch track, focus ring,
slider handle) must meet 3:1 against their background. `[verified]`

| # | Pairing | Ratio |
| --- | --- | --- |
| 1 | `text` on `window` | 15.5 |
| 2 | `text` on `surface` | 16.9 |
| 3 | `text-2` on `surface` | 7.1 |
| 4 | `on-accent` on `accent` | 5.8 |
| 5 | `accent` on `surface` (non-text) | 5.8 |
| 6 | `off` on `surface` (non-text) | 3.7 |
| 7 | `ok` on `ok-bg` | 5.1 |
| 8 | `warn` on `warn-bg` | 5.6 |
| 9 | `danger` on `danger-bg` | 5.4 |
| 10 | `text-2` on `sunken` | 6.1 |

Add a test that asserts these thresholds if the palette changes (`req-9`).

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
   the Variable face is `[open]`; detect it with `QFontDatabase.families()` at start-up.
2. Other platforms: system UI sans-serif. `[proposed]`
3. Numeric values should use tabular figures where available so changing values do not
   shift layout. Whether Qt applies this on Windows is `[open]`; if not, give numeric
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
| 3 | Chip | Fully rounded (9 px for a 18 px chip) |
| 4 | Switch | Fully rounded |
| 5 | Slider track and thumb | Fully rounded |

### 7.2 Depth

No shadows, no elevation. Separation is by background (`surface` on `window`) and the
1 px `border`. Qt drop shadows are costly inside scroll areas and clip. `[proposed]`

### 7.3 Icons

1. Monoline, 24 px grid, 1.5 px stroke, round caps and joins. `[proposed]`
2. Rendered from SVG strings in code via `QtSvg` (available `[verified]`), recoloured
   by substituting `currentColor` with the token.
3. Required set: one per device category, status (ok, warn, danger, offline, moving,
   battery 0 to 4), actions (scene play, undo, refresh, settings), and a generic scene
   glyph.
4. Scene icons: the hub has 38 values `[lib]`. Map common ones; use the generic glyph
   for the rest in version 1.
5. Licence of any icon set used must allow redistribution in a desktop app. `[open]`

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
   full name in a tooltip. `[verified]` in the failure case (section 14, item 3).
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
6. Implemented as a custom `QAbstractButton` subclass with a thumb property
   (appendix A of `qt-device-widget-mapping.md`).

Implementation note: do not name the animated property `pos`; it collides with
`QWidget.pos` `[verified]`.

### 8.4 Slider

1. Fixed label column on the left (13 px label), so sliders align across cards.
   `[verified]`
2. Track 6 px high, rounded; filled part `accent`; unfilled part `sunken`. Thumb 18 px
   white with a 2 px `accent` border. `[verified]`
3. Slider minimum height 24 px so the thumb is not clipped. `[verified]`
4. Value on the right in a fixed-width column, right aligned, body size. `[verified]`
5. Value updates live while dragging. The command is sent on release or after a short
   pause (`req-6`). `[proposed]`
6. Minimum on light brightness is 1 %, not 0 (the library rejects 0) `[lib]`.
7. Colour-temperature slider: warm-to-cool gradient track. `[proposed]` Not yet rendered
   in the mockup.
8. Disabled state: track and thumb in muted tones of the enabled colours. Implement by
   setting colours from a property or a separate rule, not by `QSlider:disabled::sub-page`;
   that selector painted the whole groove grey in Fusion `[verified]`.

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
4. Undo: appears for the allowed window after activation. Duration is `[open]`;
   `undo_allowed_duration` has no documented unit `[lib]`.
5. Automatic (non-user) scenes are hidden by default, shown when "Show automatic scenes"
   is enabled. `[proposed]`

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
for destructive confirmations only. `[proposed]`

## 9. Screens

### 9.1 Not connected

Header: title, grey chip "Not connected", search and view switcher disabled. Content:
connection block (8.12). `[proposed]`

### 9.2 Rooms

Header as in 4.2 with the Rooms segment selected. Content: room sections in order, each
with its label and card grid. Section order is `[open]`. `[verified]`

### 9.3 Scenes

Same header with the Scenes segment selected. Content: scene tiles in a width-driven
grid, with an optional "Show automatic scenes" toggle above the grid. `[proposed]`

### 9.4 Energy

Same header with the Energy segment selected. Content: energy cards grouped by room.
Whether totals are shown per home or per room is `[open]`. `[proposed]`

## 10. Behaviour

### 10.1 Commands

1. Every command runs off the GUI thread (`req-4`). `[lib]` one shared hub session.
2. Slider commands are coalesced; the latest value wins (`req-6`). `[proposed]`
3. On failure, the control is resynchronised with the device's real state (`req-3`).
   `[verified]` in the existing code's approach.
4. A command in flight shows "Sending…" in the card footer. `[proposed]`

### 10.2 Refresh

1. Refresh runs in a worker. The Refresh button shows "Refreshing…" and is disabled
   during the run. `[proposed]`
2. The current view is only rebuilt after all data has been fetched successfully
   (`req-2`). `[verified]` in the existing code's approach.
3. On failure, the last good data stays and the hub chip turns amber (3.2). `[proposed]`
4. Card order, scroll position and focus are preserved across refresh (`t-19`). `[proposed]`

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
5. Reduced motion: provide an in-app setting; use the OS setting if Qt exposes it on
   Windows `[open]`.

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
| 3 | Under 640 px | One column; view switcher moves to a second header row |

Minimum window size 640 × 480 px. `[proposed]`

Check that slider label and value columns still fit at 150 % scaling on Windows. `[open]`

## 12. Accessibility

1. Every state carries a word or icon, not only a colour (section 1, principle 4).
   `[proposed]`
2. Contrast per section 5.2. `[verified]`
3. Every interactive control has an accessible name. `[proposed]`
4. Focus indicator is never removed. `[verified]`
5. Text scales with the system font size where Qt honours it on Windows `[open]`.
6. Grayscale screenshots must still show each device's state. `[proposed]`

## 13. Implementation guidance

### 13.1 Structure

1. Put every token in one module as data, and generate the stylesheet from it. Do not
   hard-code colours in widgets. `[proposed]`
2. Theme module, icon module (SVG strings), and widget modules per component. Keep the
   flat module layout described in `AGENTS.md`. `[lib, AGENTS.md]`
3. Each card is a widget built from its device type; the mapping from device type to
   controls follows `qt-device-widget-mapping.md`, section 4. `[proposed]`

### 13.2 Qt pitfalls found during prototyping

Each was reproduced, not guessed `[verified]`:

1. **Property name clash.** A dynamic property named `pos` does not match in QSS
   selectors, and a `pyqtProperty` named `pos` shadows the `pos()` method. Use prefixed
   names such as `segpos` and `thumb`.
2. **Disabled sub-page rule.** `QSlider:disabled::sub-page` paints the whole slider
   groove, including when enabled, in Fusion. Do not use that selector.
3. **Handle clipping.** An 18 px slider handle is clipped unless the slider has a
   minimum height of 24 px.
4. **Progress bar height.** QSS `height` on `QProgressBar` did not apply in testing; use
   `setFixedHeight`.
5. **Dynamic property changes.** After changing a property that drives a QSS selector,
   call `unpolish` then `polish` on the widget, or the new style does not appear.
   `[known]`
6. **Noise.** The offscreen platform prints "does not support propagateSizeHints()".
   Ignore it when asserting that no real warnings occurred. `[verified]`

### 13.3 Performance

1. Build cards once per refresh and update in place where possible (`t-10`, `t-19`).
   `[proposed]`
2. Avoid drop shadows and per-widget effects inside scroll areas. `[known]`
3. Refresh makes many hub calls, one per device class, each with a 10 s timeout
   `[lib]`. Measure before optimising `[open]`.

## 14. Known issues and mockup defects (resolved)

1. **Grey slider track.** Cause found by bisecting the stylesheet: the disabled sub-page
   rule (13.2, item 2). Resolved by removing it. `[verified]`
2. **Metric misuse.** A door's state was shown as a big number. Resolved: states are
   words. `[verified]`
3. **Truncated name.** A long name clipped in a card. Resolved in the mockup by a
   shorter sample name; the truncation rule in 8.1 governs real data. `[verified]` the
   clip; truncation behaviour itself `[open]` until tested with Windows fonts.

## 15. Open decisions

| # | Decision | Default proposed |
| --- | --- | --- |
| 1 | Application name | Neutral name, checked for availability. Placeholder "Home" in the mockup |
| 2 | Room section order | Alphabetical |
| 3 | Show automatic scenes by default | No |
| 4 | Low-battery threshold | 20 % |
| 5 | Energy totals per home or per room | Per room, with a home total |
| 6 | Icon source | Hand-drawn, or a licence-checked set |
| 7 | Reduced-motion behaviour on Windows | In-app setting |
| 8 | Colour-temperature gradient rendering | Implement and verify |
| 9 | Air-quality colour bands | None until a standard is chosen |
| 10 | Disabled control colours | Muted tones of enabled colours; verify |

## 16. Acceptance checklist

1. Every text pairing in 5.2 is at or above 4.5:1; every indicator at or above 3:1.
2. A grayscale screenshot shows every device's state.
3. No card has more than one accent item, apart from its own switch on-state.
4. No raw `device_type`, enum repr, bare ✓, or unexplained icon appears on screen.
5. Spacing and radii use only the values in sections 4.4 and 7.1.
6. Long names truncate with a tooltip and never wrap.
7. Every control is reachable by keyboard, with a visible focus ring.
8. Offline cards keep their grid position after refresh.
9. Layout is correct at 1080, 760 and 640 px widths.
10. Verified on Windows at 100 % and 150 % scaling with Segoe UI, in the light theme.
11. Contrast assertions run in the test suite (`req-9`).

## 17. Change log

| Version | Change |
| --- | --- |
| 1.0 | First consolidated design document from the visual language, look-and-feel and widget mapping documents |
