# Release Checklist

Run these checks before publishing the repository:

```bash
python -m ruff check .
python -m pytest
cd apps/web
npm audit --audit-level=moderate
npm run build
```

Check the repository for accidental secrets or local artifacts:

```bash
rg -n "password|secret|token|api[_-]?key|BEGIN (RSA|OPENSSH|PRIVATE)" .
```

Expected local-only files:

- `.env`
- `*.db`
- `apps/web/node_modules/`
- `apps/web/dist/`
- `__pycache__/`
- `.pytest_cache/`
- `.ruff_cache/`
