-- Signup-to-purchase funnel, 14-day window, matured users only.
-- A user counts at a step only if they also reached every earlier step, so the
-- funnel is monotonically non-increasing by construction.
WITH bounds AS (
  SELECT MAX(activity_date) AS data_end FROM activity
),
cohort AS (  -- right-censoring guard: only users with a full 14-day window
  SELECT u.user_id
  FROM users u, bounds b
  WHERE date(u.signup_date, '+14 days') <= b.data_end
),
flags AS (
  SELECT c.user_id,
    MAX(CASE WHEN e.event_name = 'view_product' THEN 1 ELSE 0 END) AS viewed,
    MAX(CASE WHEN e.event_name = 'add_to_cart'  THEN 1 ELSE 0 END) AS carted,
    MAX(CASE WHEN e.event_name = 'checkout'     THEN 1 ELSE 0 END) AS checked_out,
    MAX(CASE WHEN e.event_name = 'purchase'     THEN 1 ELSE 0 END) AS purchased
  FROM cohort c
  JOIN users u ON u.user_id = c.user_id
  LEFT JOIN events e
    ON e.user_id = c.user_id
   AND e.event_date <= date(u.signup_date, '+14 days')
  GROUP BY c.user_id
),
chain AS (
  SELECT user_id,
    1 AS s1,
    viewed AS s2,
    viewed * carted AS s3,
    viewed * carted * checked_out AS s4,
    viewed * carted * checked_out * purchased AS s5
  FROM flags
),
steps AS (
  SELECT 1 AS step_no, 'signup'       AS step, SUM(s1) AS users FROM chain UNION ALL
  SELECT 2, 'view_product', SUM(s2) FROM chain UNION ALL
  SELECT 3, 'add_to_cart',  SUM(s3) FROM chain UNION ALL
  SELECT 4, 'checkout',     SUM(s4) FROM chain UNION ALL
  SELECT 5, 'purchase',     SUM(s5) FROM chain
)
SELECT step_no, step, users,
       ROUND(1.0 * users / FIRST_VALUE(users) OVER (ORDER BY step_no), 4) AS pct_of_signups,
       ROUND(1.0 * users / LAG(users) OVER (ORDER BY step_no), 4)        AS pct_of_prev_step
FROM steps
ORDER BY step_no;
