
import numpy as np


EMBEDDING_DIMENSION = 768


def calculate_cosine_similarities(
    user_vector: list[float],
    content_embeddings: list[list[float]],
) -> np.ndarray:
    """사용자 벡터와 콘텐츠 임베딩 간 코사인 유사도 계산."""

    user = np.asarray(user_vector, dtype=np.float64)
    matrix = np.asarray(content_embeddings, dtype=np.float64)

    if user.shape != (EMBEDDING_DIMENSION,):
        raise ValueError("사용자 벡터 차원 불일치")

    if (
        matrix.ndim != 2
        or matrix.shape[0] == 0
        or matrix.shape[1] != EMBEDDING_DIMENSION
    ):
        raise ValueError("콘텐츠 임베딩 행렬 차원 불일치")

    if (
        not np.all(np.isfinite(user))
        or not np.all(np.isfinite(matrix))
    ):
        raise ValueError("유효하지 않은 벡터값")

    user_norm = np.linalg.norm(user)

    content_norms = np.linalg.norm(
        matrix,
        axis=1,
    )

    if (
        not np.isfinite(user_norm)
        or not np.all(np.isfinite(content_norms))
        or user_norm == 0
        or np.any(content_norms == 0)
    ):
        raise ValueError("유효하지 않은 벡터 길이")

    # L2 Normalization
    normalized_user = user / user_norm

    normalized_matrix = (
        matrix / content_norms[:, np.newaxis]
    )

    # 행렬과 벡터의 내적
    similarities = normalized_matrix @ normalized_user

    # 부동소수점 오차로 인한 범위 초과 방지
    return np.clip(similarities, -1.0, 1.0)
