# Upstream proposal for `dirigera`

Material for opening pull requests against the `dirigera` library
(`Leggin/dirigera`), prepared from what this dashboard found on a real hub.
Tracked as `t-101`. Nothing here has been posted; the hub facts are also in
`../dirigera-api.md` (§2.5, §5 items 2 and 7).

## What is proposed

| # | Change | Library today | Verified on the real hub |
| --- | --- | --- | --- |
| 1 | `Light.leave_adaptive_profile()` | `activate_adaptive_profile()` only | yes, one light (2026-11-22) |
| 2 | `Outlet.reset_energy_counter()` and `ElectricalSensor.reset_energy_counter()` | read-only energy attributes | outlet only, one INSPELNING plug (2026-11-21 and 2026-11-22) |

Upstream was searched on 2026-11-22: no open issues or PRs, and no closed ones
cover either change.

## Files

| File | Content |
| --- | --- |
| `pr-text.md` | Draft texts for two issues and the PR |
| `dirigera-1.6.1.patch` | The change against tag `v1.6.1`: three methods and six tests; `git apply --check` passes on a fresh clone and the upstream suite passes (106 tests) |
| `traces/leave-adaptive-profile.json` | Requests and observed states for item 1, IDs replaced by placeholders |
| `traces/energy-reset.json` | Same for item 2 |
| `scripts/measure_hub.py` | Reproduces both measurements; reads freely, writes only with `--yes` |

How this app does the same today: `leave_profile` in `adaptive.py` and
`reset_energy` in `dashboard.py` (raw `patch` calls).

## Applying the patch

```bash
git clone --branch v1.6.1 https://github.com/Leggin/dirigera.git
cd dirigera
git switch -c leave-adaptive-and-energy-reset
git apply /path/to/doc/upstream-pr/dirigera-1.6.1.patch
pip install pytest pydantic websocket-client requests
python -m pytest
```

Before posting, rebase onto upstream's current `main`, and run the project's own
formatting: its pinned `black` differs from a current one (a current `black`
reformats unrelated files, so format only the six touched files).

## Open points before posting

- Check upstream issues and PRs again.
- Real-hub check of the dashboard's Reset button and the "Off" adaptive choice.
- Decide on item 2 for split plugs (GRILLPLATS): untested, the capability guard
  would refuse the reset there.
- Add the README sentences listed in `pr-text.md`.
- Decide whether to send one PR or two; the changes are independent.
- No real IPs, tokens, device IDs or serial numbers in any text. The traces use
  placeholders.
