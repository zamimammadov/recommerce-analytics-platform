# Business Case and Metric Contracts

## Stakeholders and decisions

- Marketplace Operations reviews supply, completed sales and category health.
- Product Analytics reviews engagement and listing outcomes.
- Seller Experience reviews time-to-sale and observed seller performance.
- Data Platform reviews rejected records, freshness and reproducibility.

These outputs help formulate questions such as “which category has high
engagement but few completed sales?” Synthetic results demonstrate the method;
they do not establish facts about any real marketplace.

## Implemented metric definitions

Definitions below describe the actual SQL in `dbt/models/marts/`.

| Metric | Implementation and interpretation |
|---|---|
| New listings | Distinct current `listing_id` rows grouped by the original `created_at` date. Later price/status updates do not count as new supply. |
| Orders | One current row per `order_id`, grouped by the original `order_at` date. Includes cancelled/refunded orders in activity counts. |
| Completed orders | Current order state equals `completed`; completion is attributed to the order date, not a separate completion-event date. |
| GMV | Sum of item value for current states `paid`, `shipped`, or `completed`. Excludes shipping, cancelled/refunded orders and orders still `created`. It is transaction volume, not revenue. |
| Average order value | GMV divided by GMV-eligible order count. It does not use all orders as the denominator. |
| View-to-order activity ratio | All order count divided by view-event count in the selected period. It is not a user-level conversion probability, and unrelated daily flows should not be interpreted causally. |
| Listing sell-through | Observed listings with at least one currently completed order divided by all observed listings in that seller/funnel population. There is no N-day observation window in this version. |
| Hours to sale | First currently GMV-eligible order time minus original listing creation time. Seller mart averages this measure among listings that have reached the completed stage. |
| Median time to sale | Presentation SQL in `analysis/business_questions.sql` computes the median across observed completed listings by category/condition; this is not a maturity-adjusted cohort comparison. |
| Listing stage flags | Whether any view, favourite, message, order, or completed order is observed for the listing. Stages need not be sequential or performed by the same user. |
| Current active listings | Current `active` status count in the seller mart. It is not historical end-of-day inventory; `reserved` listings are not included in that field. |

The daily mart has one row per date. Seller performance has one row per seller
and seller country; listing funnel has one row per listing. Monetary values
use PostgreSQL `numeric`; source timestamps are UTC.

## Historical restatements

Current-state order updates can restate historical GMV and completed-order
counts. A later refund is reflected on the original order date after rebuilding
the marts. Late files preserve event time while recording their actual ingestion
time. The pipeline currently rebuilds the analytical tables in full; it does
not implement partition-scoped dbt incremental transformations.

Current dimensions are used for category and seller-country attribution. The
separate SCD2 snapshots preserve versions observed at successive runs, but
facts are not yet joined to the dimension version effective at the event time.

## Analyses that remain future work

- N-day cohort sell-through with a maturity cutoff, to compare cohorts fairly.
- A strictly ordered user/session funnel with defined attribution windows.
- Point-in-time active inventory from historical snapshots.
- Time-to-sale comparisons adjusted for comparable listing cohorts and observation maturity.
- Confidence intervals or A/B test analysis using a justified assignment design.

For example, “favourited within 24 hours predicts seven-day sell-through” is a
useful future hypothesis. It requires a new cohort query and appropriate
confounder handling; it is not an implemented causal finding.
