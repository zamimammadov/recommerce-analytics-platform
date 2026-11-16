# Dashboard

The optional Streamlit application reads only curated `analytics` marts. It
does not query raw tables, which keeps metric definitions in dbt rather than
duplicating business logic in a UI.

```bash
docker compose --profile dashboard up dashboard
```

Open <http://localhost:8501>. The app uses `DATABASE_URL`; no credential is
stored in source code.
