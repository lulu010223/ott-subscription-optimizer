
import math

import numpy as np
import pytest

from recommendation.content_similarity import (
    calculate_cosine_similarities,
)


def make_vector(x, y):
    return [x, y] + [0.0] * 766


# 1. 코사인 유사도 계산 정확성
def test_cosine_similarity():
    user = make_vector(1.0, 0.0)

    embeddings = [
        make_vector(1.0, 0.0),
        make_vector(1.0, 1.0),
        make_vector(0.0, 1.0),
        make_vector(-1.0, 1.0),
        make_vector(-1.0, 0.0),
    ]

    scores = calculate_cosine_similarities(
        user, embeddings
    )

    expected = [
        1.0,
        1 / math.sqrt(2),
        0.0,
        -1 / math.sqrt(2),
        -1.0,
    ]

    assert scores == pytest.approx(expected)


# 2. 벡터 크기에 대한 불변성
def test_scale_invariance():
    user = make_vector(3.0, 4.0)

    embeddings = [
        make_vector(3.0, 4.0),
        make_vector(6.0, 8.0),
        make_vector(30.0, 40.0),
    ]

    scores = calculate_cosine_similarities(
        user, embeddings
    )

    assert scores == pytest.approx([1.0] * 3)


# 3. 결과 개수 및 유사도 범위 검증
def test_output_shape_and_range():
    rng = np.random.default_rng(42)

    user = rng.normal(size=768)
    embeddings = rng.normal(size=(100, 768))

    scores = calculate_cosine_similarities(
        user.tolist(),
        embeddings.tolist(),
    )

    assert scores.shape == (100,)
    assert np.all(np.isfinite(scores))
    assert np.all(scores >= -1.0)
    assert np.all(scores <= 1.0)


# 4. 잘못된 사용자 벡터
@pytest.mark.parametrize("invalid_user", [
    [1.0] * 767,
    [1.0] * 769,
    [0.0] * 768,
    [float("nan")] + [1.0] * 767,
    [float("inf")] + [1.0] * 767,
])
def test_invalid_user_vector(invalid_user):
    embeddings = [make_vector(1.0, 0.0)]

    with pytest.raises(ValueError):
        calculate_cosine_similarities(
            invalid_user,
            embeddings,
        )


# 5. 잘못된 콘텐츠 임베딩
@pytest.mark.parametrize("invalid_embeddings", [
    [],
    [[1.0] * 767],
    [[1.0] * 769],
    [[0.0] * 768],
    [[float("nan")] + [1.0] * 767],
    [[float("inf")] + [1.0] * 767],
    [[1.0] * 768, [1.0] * 767],
])
def test_invalid_content_embeddings(
    invalid_embeddings,
):
    user = make_vector(1.0, 0.0)

    with pytest.raises(ValueError):
        calculate_cosine_similarities(
            user,
            invalid_embeddings,
        )


# 6. 콘텐츠 순서 보존
def test_content_order_preservation():
    user = make_vector(1.0, 0.0)

    embeddings = [
        make_vector(-1.0, 0.0),
        make_vector(1.0, 0.0),
        make_vector(0.0, 1.0),
    ]

    scores = calculate_cosine_similarities(
        user, embeddings
    )

    assert scores == pytest.approx([
        -1.0, 1.0, 0.0
    ])
