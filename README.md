# Campus Item Exchange checkpoint 4

Runnable cumulative checkpoint including foundation, assets, requests, approvals, transfers, maintenance and lifecycle, plus advisory AI, impact reports and isolated backup/restore.

## Run

Use Python 3.12 or 3.13.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m flask --app run init-demo
python run.py
```

Open http://127.0.0.1:5000. Generated local demo credentials are in ignored instance/demo-credentials.txt. The initializer preserves existing data. Usernames include sysadmin, custodian, receiver, approver, requester2, requester, representative, maintenance, procurement, finance and sustainability. Use requester2 for the seeded Engineering inventory.

For Windows PowerShell, create the environment with `python -m venv .venv` and activate it with `.\.venv\Scripts\Activate.ps1`. The pinned timezone data supports Dubai dates on Windows.

## Validate

```bash
python -m pytest
```

Review your assigned files, make and explain your revisions, record actual checks in docs/phase6/REVIEW_LOG.txt, then commit and push using your own GitHub identity. Record only work and checks that actually occurred.

## Updated dates

22 November 2026 11:59 pm: screenshots, pushed code and presentation. 23 November 3:00 pm: demo and individual Q&A. 26 November: testing. See the supplied instructor announcement.

Checkpoint 1 establishes all shared schema/domain contracts. Checkpoint 2 adds assets/requests. Checkpoint 3 adds workflow/lifecycle. Checkpoint 4 adds AI/reports/recovery. Only Mohammed configures the AI key locally; manual workflows remain available without it. The selected final AI model is z-ai/glm-5.3-flash through OpenRouter. Never commit local .env, generated passwords or instance data.

Stage 2 verification on Windows with Python 3.12.14: 32 automated tests passed. Browser interaction and document layout checks remain pending. This branch depends on foundation PR #4, which remains open.

Stage 3 adds independent approvals, evidence-based collection and receipt, service and disposition workflows, and audit history. A request reserves units from one source custodian; if eligible stock is split across custodians, submit smaller requests. The stage-three branch depends on the open stage-two PR #5 and foundation PR #4. Stage 4 depends on open draft PR #6 and its upstream PRs #5 and #4.

## Recovery
Use `python -m flask --app run snapshot /path/to/new-snapshot` to create a database and evidence snapshot. Use `python -m flask --app run restore-isolated /path/to/snapshot /path/to/new-restore` to verify and restore outside the active instance. Secure these files: they contain application data.
