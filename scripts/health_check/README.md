# Health Check

Quick manual check that both services are running, useful right after
`npm run dev` / `uvicorn app.main:app --reload`.

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/v1/health
```

Then open http://localhost:5173/ and confirm the System Status panel
shows "Backend: Online".

A scripted version of this (e.g. `check.sh`) can be added once there's
more than one dependency to check (database, cache, etc.) in a later
step — a single curl command doesn't need its own script yet.
