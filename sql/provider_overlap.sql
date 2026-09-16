WITH
  content_base AS (
    -- 1. 콘텐츠를 고유하게 식별하기 위해 tmdb_id와 media_type을 결합하여 베이스 데이터를 생성합니다.
    SELECT DISTINCT
      normalized_provider AS provider,
      CONCAT(media_type, ':', CAST(tmdb_id AS STRING)) AS content_key
    FROM `lulu260902.ott_optimizer.content_providers`
  ),
  provider_counts AS (
    -- 2. 각 OTT(provider)별로 보유한 고유 콘텐츠의 총 개수를 계산합니다.
    SELECT provider, COUNT(content_key) AS content_count
    FROM content_base
    GROUP BY provider
  ),
  cross_join_providers AS (
    -- 3. 서로 다른 두 OTT 간의 모든 조합을 생성합니다. (A < B 조건을 통해 중복 쌍 제거)
    SELECT
      a.provider AS provider_a,
      b.provider AS provider_b,
      a.content_count AS provider_a_contents,
      b.content_count AS provider_b_contents
    FROM provider_counts AS a
    CROSS JOIN provider_counts AS b
    WHERE a.provider < b.provider
  ),
  common_counts AS (
    -- 4. 두 OTT 쌍이 공통으로 가지고 있는 콘텐츠의 수를 계산합니다.
    SELECT
      a.provider AS provider_a,
      b.provider AS provider_b,
      COUNT(a.content_key) AS common_contents
    FROM content_base AS a
    INNER JOIN content_base AS b
      ON a.content_key = b.content_key
    WHERE a.provider < b.provider
    GROUP BY provider_a, provider_b
  )
-- 5. 최종 결과: 공통 콘텐츠 수, 합집합 수, 그리고 Jaccard Similarity를 계산합니다.
SELECT
  p.provider_a,
  p.provider_b,
  p.provider_a_contents,
  p.provider_b_contents,
  COALESCE(c.common_contents, 0) AS common_contents,
  -- 합집합 공식: A + B - (A ∩ B)
  (
    p.provider_a_contents + p.provider_b_contents - COALESCE(
      c.common_contents, 0))
    AS union_contents,
  -- Jaccard Similarity: (A ∩ B) / (A ∪ B)
  SAFE_DIVIDE(
    COALESCE(c.common_contents, 0),
    (
      p.provider_a_contents + p.provider_b_contents - COALESCE(
        c.common_contents, 0)))
    AS jaccard_similarity
FROM cross_join_providers AS p
LEFT JOIN common_counts AS c
  ON p.provider_a = c.provider_a AND p.provider_b = c.provider_b
ORDER BY jaccard_similarity DESC;

