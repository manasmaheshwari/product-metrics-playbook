-- Weekly cohort retention (cohort = signup week, offset = whole weeks since signup).
-- Censoring guard: a user only counts in the denominator for week N if week N
-- has fully elapsed in the data. Otherwise young cohorts look like they churn.
WITH RECURSIVE bounds AS (
  SELECT MAX(activity_date) AS data_end FROM activity
),
weeks(n) AS (
  SELECT 0 UNION ALL SELECT n + 1 FROM weeks WHERE n < 8
),
cohorts AS (
  SELECT user_id, signup_date,
         date(signup_date, '-' || ((CAST(strftime('%w', signup_date) AS INTEGER) + 6) % 7) || ' days') AS cohort_week
  FROM users
),
eligible AS (  -- (user, week) pairs whose week window is fully observed
  SELECT c.user_id, c.cohort_week, w.n
  FROM cohorts c
  CROSS JOIN weeks w
  CROSS JOIN bounds b
  WHERE date(c.signup_date, '+' || (7 * (w.n + 1) - 1) || ' days') <= b.data_end
),
active AS (
  SELECT DISTINCT c.user_id,
         CAST((julianday(a.activity_date) - julianday(c.signup_date)) / 7 AS INTEGER) AS n
  FROM cohorts c
  JOIN activity a ON a.user_id = c.user_id
)
SELECT e.cohort_week,
       e.n AS week_offset,
       COUNT(*) AS cohort_users,
       COUNT(a.user_id) AS retained_users,
       ROUND(1.0 * COUNT(a.user_id) / COUNT(*), 4) AS retention
FROM eligible e
LEFT JOIN active a ON a.user_id = e.user_id AND a.n = e.n
GROUP BY e.cohort_week, e.n
ORDER BY e.cohort_week, e.n;
