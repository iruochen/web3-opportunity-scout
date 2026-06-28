# Internal Source Onboarding Checklist

Use this checklist when integrating a new source:

1. Add source entry to `sources.example.yaml`
2. Add or enable source entry in local `sources.yaml`
3. Set `adapter`
4. Create `scripts/fetch-<adapter>.py`
5. Create `scripts/normalize-<adapter>.py`
6. Add auth env var to `.env.example` only if it is a public placeholder name
7. Run:
   - `python scripts/cli.py list-sources`
   - `python scripts/cli.py fetch --source <source_id> --dry-run`
   - `python scripts/cli.py run --source <source_id> --skip-fetch`
   - `make test`
8. Commit source runtime changes separately from README/docs changes when practical
