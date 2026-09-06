# 11. Delivery Roadmap

MVP path (recommended): **discovery → matching → tailored resume → autofill →
user verification → submit**, with one ATS adapter at a time rather than all at once.

| Phase | Scope | State |
| --- | --- | --- |
| 1 | Auth, profile, resume upload + parsing, database + migrations, dashboard | **Implemented** |
| 2 | Job ingestion, normalization, dedupe, matching engine, preferences | Contracts + models landed |
| 3 | AI resume tailoring, cover letters, application question engine | Interfaces + prompts landed |
| 4 | Playwright engine, ATS detection, Greenhouse / Lever / Ashby adapters | Interfaces landed |
| 5 | Workday, iCIMS, SmartRecruiters, generic fallback adapter | Planned |
| 6 | Application queue, automation dashboard, human intervention | Models + states landed |
| 7 | Notifications, analytics, billing | Notifications + analytics partial |
| 8 | Production deployment, monitoring, security hardening | Terraform skeleton |

Gate between phases: `pytest -q` green, `npm run typecheck` clean, migrations applied
from scratch on an empty database.
