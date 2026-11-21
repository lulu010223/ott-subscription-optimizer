
CREATE OR REPLACE VIEW
  `lulu260902.ott_optimizer.bundle_catalog`
AS
SELECT
  b.bundle_id,
  b.bundle_name,
  b.monthly_price,
  b.ads,
  ARRAY_AGG(
    STRUCT(
      bp.provider AS provider,
      bp.plan_name AS plan_name
    )
    ORDER BY bp.provider
  ) AS included_plans
FROM
  `lulu260902.ott_optimizer.ott_bundles` b
JOIN
  `lulu260902.ott_optimizer.bundle_providers` bp
ON
  b.bundle_id = bp.bundle_id
GROUP BY
  b.bundle_id,
  b.bundle_name,
  b.monthly_price,
  b.ads;
