# Analytics walkthrough

The goal is not to show five arbitrary SQL queries. Each question represents
a decision a marketplace team might make.

1. **Liquidity activity:** Compare completed orders with new listing supply.
   These are separate flows; their ratio does not measure cohort sell-through.
2. **Funnel by category:** Categories with many views but few messages/orders
   may need better item information, trust signals, or pricing guidance.
3. **Seller performance:** Compare observed completed-listing fractions and GMV
   across sellers. Cancellation rates require an additional metric.
4. **Time-to-sale:** Long median time-to-sale can reveal inventory that is
   overpriced or difficult to match. Median is shown because the distribution
   is normally skewed.
5. **Reconciliation:** A business dashboard is not trustworthy until its GMV
   agrees with the underlying order fact.

## Important limitations

- The dataset is synthetic, so findings demonstrate analytical reasoning and
  engineering behaviour rather than real commercial performance.
- Correlation is not causation. A category's poor conversion does not prove a
  specific product change will improve it.
- GMV includes item value in paid, shipped, or completed orders. Shipping is
  separate; marketplace revenue/fees are not modelled.

To inspect run audit, row reconciliation, quarantine, price history, and late
events, execute `inspect_pipeline.sql` after the demo. For example:

```bash
docker compose exec -T postgres psql -U recommerce -d recommerce < analysis/inspect_pipeline.sql
```
