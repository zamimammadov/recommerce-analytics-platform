# Reproducible demonstration outputs

`demo-results/` contains generated analytics outputs from a two-batch run with
seed `20261115`, logical dates `2026-10-01` and `2026-10-02`, 100 user versions
and 200 listing versions per batch. Each day's ingestion is followed by a dbt
build so observed changes create snapshot history.

The source generator includes historical entity creation dates and late facts;
the metrics' business-date range therefore starts before the file delivery dates.
The 400 incoming listing versions represent 385 distinct listings and 15 updates.

These records are synthetic. Findings describe this simulation and must not be
presented as conclusions about a real marketplace. Reproduce with:

```bash
make demo-local DEMO_USERS=100 DEMO_LISTINGS=200
recommerce export-metrics --output-dir examples/demo-results
```

The independent processing invariants were: six malformed records quarantined,
15 closed listing snapshot versions, all six DQ checks passed, and replay of
the second partition skipped four files and inserted zero rows.
