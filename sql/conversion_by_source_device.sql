-- Same metric, stratified by device. Reading this next to the aggregate view
-- exposes Simpson's paradox when the device mix differs between sources.
WITH bounds AS (SELECT MAX(activity_date) AS data_end FROM activity),
cohort AS (
  SELECT u.* FROM users u, bounds b
  WHERE date(u.signup_date, '+14 days') <= b.data_end
),
buyers AS (
  SELECT DISTINCT c.user_id
  FROM cohort c
  JOIN events e ON e.user_id = c.user_id AND e.event_name = 'purchase'
   AND e.event_date <= date(c.signup_date, '+14 days')
)
SELECT c.source, c.device,
       COUNT(*) AS users,
       COUNT(b.user_id) AS converted,
       ROUND(1.0 * COUNT(b.user_id) / COUNT(*), 4) AS conversion
FROM cohort c
LEFT JOIN buyers b ON b.user_id = c.user_id
GROUP BY c.source, c.device
ORDER BY c.device, conversion DESC;
