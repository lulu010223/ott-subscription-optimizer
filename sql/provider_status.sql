SELECT
  normalized_provider AS provider,
  -- 각 OTT별로 고유한 (tmdb_id, media_type) 조합의 전체 개수를 집계합니다.
  COUNT(DISTINCT CONCAT(media_type, ':', CAST(tmdb_id AS STRING)))
    AS total_contents,
  -- media_type이 'movie'인 고유 콘텐츠의 수를 집계합니다.
  COUNT(
    DISTINCT
      IF(
        media_type = 'movie',
        CONCAT(media_type, ':', CAST(tmdb_id AS STRING)),
        NULL))
    AS movie_count,
  -- media_type이 'tv'인 고유 콘텐츠의 수를 집계합니다.
  COUNT(
    DISTINCT
      IF(
        media_type = 'tv',
        CONCAT(media_type, ':', CAST(tmdb_id AS STRING)),
        NULL))
    AS tv_count
FROM `lulu260902.ott_optimizer.content_providers`
GROUP BY provider
ORDER BY total_contents DESC;

