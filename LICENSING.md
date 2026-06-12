# Licensing

`embedded-sos-filters` is **dual-licensed**: free under copyleft open-source
terms, or under a separate **commercial license** for proprietary use.

## Open-source license (free)

| Part | What it covers | License |
|------|----------------|---------|
| Python tooling | `tools/`, `tests/`, and the repository as a whole | **AGPL-3.0-or-later** — see [`LICENSE`](LICENSE) |
| C runtime library | `lib/` (the generated/embedded SOS filter code) | **GPL-3.0-or-later** — see [`lib/LICENSE`](lib/LICENSE) |

Under these terms you may use, study, modify and redistribute the code for
free. In return, the copyleft requires that **derivative works be released
under the same license** — including:

- the **GPL** on the C library: linking or embedding it in a product makes the
  combined firmware subject to the GPL (you must offer your source);
- the **AGPL** on the tooling: offering it over a network (e.g. as a service)
  also triggers the source-disclosure obligation.

If you are building open-source, this is all you need — no cost, no contract.

## Commercial license (paid)

If you want to **embed the generated C code (or the library) in a proprietary
product**, or use the tooling in a closed/SaaS context **without** the copyleft
obligations above, a commercial license is available. It grants the same code
under proprietary-friendly terms (no source-disclosure requirement).

**Contact:** ramon.martins@uem.com.br  *(update with your preferred contact)*

## Contributions

Contributions are welcome. Because the project is offered under a commercial
license in addition to the open-source one, contributors must agree to a
Contributor License Agreement (CLA) granting the maintainer the right to
relicense their contributions under the commercial terms. (A CLA will be added
before accepting external contributions.)

## SPDX summary

```
tools/, tests/   AGPL-3.0-or-later OR LicenseRef-Commercial
lib/             GPL-3.0-or-later  OR LicenseRef-Commercial
```
