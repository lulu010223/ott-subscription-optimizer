
import math

from google.cloud import bigquery

from recommendation.user_preference import SelectedContent


PROJECT_ID = "lulu260902"
DATASET_ID = "ott_optimizer"
LOCATION = "asia-northeast3"

MODEL_NAME = "gemini-embedding-001"
DIMENSION = 768


class ContentRepository:
    """BigQuery 콘텐츠 및 임베딩 조회."""

    def __init__(self, client=None):
        self.client = (
            client if client is not None
            else bigquery.Client(project=PROJECT_ID)
        )

    def fetch_selected_contents(
        self,
        content_keys: list[tuple[int, str]],
    ) -> tuple[
        list[SelectedContent],
        dict[tuple[int, str], list[float]],
    ]:
        """선택 콘텐츠의 메타데이터와 임베딩 조회."""

        if not content_keys:
            raise ValueError("선택 콘텐츠가 없습니다.")

        if len(set(content_keys)) != len(content_keys):
            raise ValueError("중복된 콘텐츠가 있습니다.")

        keys = [
            f"{tmdb_id}:{media_type}"
            for tmdb_id, media_type in content_keys
        ]

        query = f"""
        SELECT
            c.tmdb_id,
            c.media_type,
            c.title,
            c.genres,
            c.keywords,
            e.embedding
        FROM `{PROJECT_ID}.{DATASET_ID}.content_analysis` c
        INNER JOIN
            `{PROJECT_ID}.{DATASET_ID}.content_embeddings` e
            ON c.tmdb_id = e.tmdb_id
            AND c.media_type = e.media_type
        WHERE CONCAT(
            CAST(c.tmdb_id AS STRING),
            ':',
            c.media_type
        ) IN UNNEST(@keys)
        AND e.model_name = @model_name
        AND e.embedding_dimension = @dimension
        AND ARRAY_LENGTH(e.embedding) = @dimension
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "keys", "STRING", keys
                ),
                bigquery.ScalarQueryParameter(
                    "model_name", "STRING", MODEL_NAME
                ),
                bigquery.ScalarQueryParameter(
                    "dimension", "INT64", DIMENSION
                ),
            ]
        )

        rows = self.client.query(
            query,
            job_config=job_config,
            location=LOCATION,
        ).result()

        contents = {}
        embeddings = {}

        for row in rows:
            key = (row.tmdb_id, row.media_type)

            if key in contents:
                raise ValueError(
                    f"중복 조회된 콘텐츠: {key}"
                )

            vector = list(row.embedding)

            if (
                not all(math.isfinite(v) for v in vector)
                or not any(v != 0 for v in vector)
            ):
                raise ValueError(
                    f"유효하지 않은 임베딩: {key}"
                )

            contents[key] = SelectedContent(
                tmdb_id=row.tmdb_id,
                media_type=row.media_type,
                title=row.title,
                genres=list(row.genres or []),
                keywords=list(row.keywords or []),
            )

            embeddings[key] = vector

        missing = set(content_keys) - set(contents)

        if missing:
            raise ValueError(
                f"조회 가능한 임베딩이 없는 콘텐츠: {missing}"
            )

        return (
            [contents[key] for key in content_keys],
            embeddings,
        )


    def fetch_content_embeddings(
        self,
        limit: int | None = None,
    ) -> list[dict]:
        """유사도 계산 대상 콘텐츠 및 임베딩 조회."""

        if limit is not None and limit < 1:
            raise ValueError("limit은 1 이상이어야 합니다.")

        query = f"""
        SELECT
            c.tmdb_id,
            c.media_type,
            c.title,
            c.genres,
            c.providers,
            e.embedding
        FROM `{PROJECT_ID}.{DATASET_ID}.content_analysis` c
        INNER JOIN
            `{PROJECT_ID}.{DATASET_ID}.content_embeddings` e
            ON c.tmdb_id = e.tmdb_id
            AND c.media_type = e.media_type
        WHERE e.model_name = @model_name
            AND e.embedding_dimension = @dimension
            AND ARRAY_LENGTH(e.embedding) = @dimension
        ORDER BY c.media_type, c.tmdb_id
        """

        parameters = [
            bigquery.ScalarQueryParameter(
                "model_name", "STRING", MODEL_NAME
            ),
            bigquery.ScalarQueryParameter(
                "dimension", "INT64", DIMENSION
            ),
        ]

        if limit is not None:
            query += "\nLIMIT @limit"

            parameters.append(
                bigquery.ScalarQueryParameter(
                    "limit", "INT64", limit
                )
            )

        job_config = bigquery.QueryJobConfig(
            query_parameters=parameters
        )

        rows = self.client.query(
            query,
            job_config=job_config,
            location=LOCATION,
        ).result()

        results = []
        seen = set()

        for row in rows:
            key = (row.tmdb_id, row.media_type)

            if key in seen:
                raise ValueError(
                    f"중복 콘텐츠 발견: {key}"
                )

            seen.add(key)

            results.append({
                "tmdb_id": row.tmdb_id,
                "media_type": row.media_type,
                "title": row.title,
                "genres": list(row.genres or []),
                "providers": list(row.providers or []),
                "embedding": list(row.embedding),
            })

        return results
