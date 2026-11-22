# Campus Item Exchange checkpoint 1

Runnable cumulative checkpoint owned by Mohammed Siam. This checkpoint includes application foundation, login, scoped roles, accounts, departments and shared data contracts. Later modules are not implemented in this checkpoint. The complete reference and the team handoff describe the final integration.

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

## Validate

```bash
python -m pytest
```

Review your assigned files, make and explain your revisions, record actual checks in docs/phase6/REVIEW_LOG.txt, then commit and push using your own GitHub identity. AI assisted with preparing the reference; the prepared checkpoint is not evidence that a teammate has reviewed or committed it.

## Updated dates

22 November 2026 11:59 pm: screenshots, pushed code and presentation. 23 November 3:00 pm: demo and individual Q&A. 26 November: testing. See the supplied instructor announcement.

Checkpoint 1 establishes all shared schema/domain contracts. Checkpoint 2 adds assets/requests. Checkpoint 3 adds workflow/lifecycle. Checkpoint 4 adds AI/reports/recovery. Future navigation is disabled using STAGE. The selected final AI model is z-ai/glm-5.3-flash through OpenRouter. Never commit local .env, generated passwords or instance data.
