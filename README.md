# Product Metrics Playbook

SQL (SQLite-compatible) and Python (pandas, matplotlib) recipes for three analyses
every product team ends up doing: **funnel**, **cohort retention** and
**conversion by acquisition source**. Each comes with the pitfalls that most often
produce a wrong answer.

All data is **synthetic**, produced by a seeded generator. Nothing here reflects a
real company or real users.

## Quick start

```bash
pip install -r requirements.txt
python -m playbook.generate_data      # builds data/playbook.db + CSVs
python -m playbook.analysis           # runs sql/*.sql, writes outputs/*.csv|png
pytest                                # sanity tests
```

Sample outputs from the default seed are committed in [`outputs/`](outputs/).

## Layout

| Path | What it is |
|---|---|
| `playbook/generate_data.py` | Seeded synthetic data: `users`, `events`, `activity` |
| `sql/funnel.sql` | Step-by-step funnel with a 14-day window |
| `sql/retention.sql` | Weekly cohort retention with a censoring guard |
| `sql/conversion_by_source.sql` | Conversion by source (aggregate) |
| `sql/conversion_by_source_device.sql` | Same, stratified by device |
| `playbook/analysis.py` | Runs the SQL, writes CSV and PNG outputs |
| `tests/test_metrics.py` | pytest sanity tests (SQL vs independent pandas check, invariants) |

## The metrics

### 1. Funnel conversion
**What:** share of users who reach each step (signup, view product, add to cart,
checkout, purchase) within a fixed window after signup, with step-to-step and
overall rates.
**Use when:** you need to find where in a flow users drop off, or to size the
upside of fixing one step.
**Pitfalls**
- *Unfixed windows.* Without a window, older users look better simply because they
  had more time. Fix the window (here 14 days) and exclude users who have not
  had the full window yet.
- *Non-nested steps.* If a user can skip steps, "users at step N" can exceed step
  N-1. This repo counts a user at a step only if they reached all earlier ones.
- *Averaging rates.* Overall conversion is the product of step rates; improving a
  large early step can matter less than a small late one. Read counts and rates together.

### 2. Cohort retention
**What:** for users grouped by signup week, the fraction active in each later week.
**Use when:** judging whether the product keeps users, or whether a release, channel
or onboarding change shifted behaviour for newer cohorts.
**Pitfalls**
- *Cohort censoring.* The newest cohorts have not lived long enough to be observed
  at later weeks. Treating "not yet observable" as "churned" makes recent cohorts
  look worse. `retention.sql` only counts a user for week N once week N has fully elapsed;
  the heatmap leaves those cells blank.
- *Survivorship.* Retention curves among survivors always look flat. Keep the
  denominator as everyone who joined, not only those still active.
- *Definition of active.* Retention depends heavily on what counts as activity.
  Pick an event that reflects real value, not just an app open.

### 3. Conversion by source
**What:** conversion rate of users grouped by acquisition source.
**Use when:** allocating acquisition effort or judging a channel.
**Pitfalls**
- *Simpson's paradox.* The dataset is built so that `partner` converts best on both
  desktop and mobile yet ranks below `organic` overall, because most partner users
  are on mobile, which converts lower for every source. The aggregate ranking
  reflects device mix, not channel quality. Always stratify by the main confounders
  (device, geography, plan) before acting on a ranking.
- *Small segments.* Rates from a few hundred users move a lot by chance. Report
  counts and confidence intervals before declaring a winner.
- *Attribution.* "Source" is a model (first touch here). Last-touch or multi-touch
  can reorder channels.

## Reading the sample outputs

| Output | Shows |
|---|---|
| `outputs/funnel.png` | Users remaining at each funnel step |
| `outputs/retention_heatmap.png` | Cohort x week retention; blanks are censored |
| `outputs/conversion_by_source.png` | Aggregate ranking vs per-device ranking (the paradox) |

## Adapting to your own data

Point the SQL at your tables: `users(user_id, signup_date, source, device)`,
`events(user_id, event_name, event_date)` and `activity(user_id, activity_date)`.
The queries use only standard SQLite date functions and window functions, and port
to Postgres or BigQuery with small date-syntax changes.

## License

MIT, see [LICENSE](LICENSE).
