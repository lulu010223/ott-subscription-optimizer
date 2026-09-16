CREATE OR REPLACE VIEW `lulu260902.ott_optimizer.content_analysis` AS

WITH genre_agg AS (
    SELECT
        g.tmdb_id,
        g.media_type,
        ARRAY_AGG(g.genre_name IGNORE NULLS) AS genres
    FROM `lulu260902.ott_optimizer.content_genres` AS g
    GROUP BY
        g.tmdb_id,
        g.media_type
),

keyword_agg AS (
    SELECT
        k.tmdb_id,
        k.media_type,
        ARRAY_AGG(k.keyword_name IGNORE NULLS) AS keywords
    FROM `lulu260902.ott_optimizer.content_keywords` AS k
    GROUP BY
        k.tmdb_id,
        k.media_type
),

provider_agg AS (
    SELECT
        p.tmdb_id,
        p.media_type,
        ARRAY_AGG(p.normalized_provider IGNORE NULLS) AS providers
    FROM `lulu260902.ott_optimizer.content_providers` AS p
    GROUP BY
        p.tmdb_id,
        p.media_type
)

SELECT
    c.tmdb_id,
    c.media_type,
    c.title,
    c.original_title,
    c.overview,
    c.release_date,
    c.original_language,
    c.popularity,
    c.vote_average,
    c.vote_count,
    c.poster_path,
    g.genres,
    k.keywords,
    p.providers
FROM `lulu260902.ott_optimizer.contents` AS c

LEFT JOIN genre_agg AS g
    ON c.tmdb_id = g.tmdb_id
    AND c.media_type = g.media_type

LEFT JOIN keyword_agg AS k
    ON c.tmdb_id = k.tmdb_id
    AND c.media_type = k.media_type

LEFT JOIN provider_agg AS p
    ON c.tmdb_id = p.tmdb_id
    AND c.media_type = p.media_type;