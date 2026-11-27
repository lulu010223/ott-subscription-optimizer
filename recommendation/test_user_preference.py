# 1.공통 테스트 데이터 정의

import math

import pytest

from recommendation.user_preference import (
    SelectedContent,
    UserPreferenceInput,
    build_preference_profile,
    calculate_content_weight,
    calculate_content_weights,
    build_user_preference_vector,
)


@pytest.fixture
def sample_contents():
    return [
        SelectedContent(
            1, "movie", "A",
            ["SF"], ["Space"],
        ),
        SelectedContent(
            2, "movie", "B",
            ["SF"], ["Space"],
        ),
        SelectedContent(
            3, "movie", "C",
            ["Drama"], ["Family"],
        ),
    ]


@pytest.fixture
def sample_input(sample_contents):
    return UserPreferenceInput(
        selected_contents=sample_contents,
    )


@pytest.fixture
def sample_embeddings():
    return {
        (1, "movie"): [1.0, 0.0] + [0.0] * 766,
        (2, "movie"): [1.0, 0.0] + [0.0] * 766,
        (3, "movie"): [0.0, 1.0] + [0.0] * 766,
    }

# 2.취향 프로필 테스트

def test_preference_profile(sample_input):
    profile = build_preference_profile(sample_input)

    assert profile.genre_frequencies == pytest.approx({
        "SF": 2 / 3,
        "Drama": 1 / 3,
    })

    assert profile.keyword_frequencies == pytest.approx({
        "Space": 2 / 3,
        "Family": 1 / 3,
    })


def test_preferred_genres(sample_contents):
    user_input = UserPreferenceInput(
        selected_contents=sample_contents,
        preferred_genres=["SF", "Action"],
    )

    profile = build_preference_profile(user_input)

    assert profile.genre_frequencies == pytest.approx({
        "SF": 3 / 4,
        "Drama": 1 / 4,
        "Action": 1 / 4,
    })

    assert profile.keyword_frequencies == pytest.approx({
        "Space": 2 / 3,
        "Family": 1 / 3,
    })


def test_duplicate_features(sample_contents):
    sample_contents[0].genres.append("SF")
    sample_contents[0].keywords.append("Space")

    profile = build_preference_profile(
        UserPreferenceInput(sample_contents)
    )

    assert profile.genre_frequencies["SF"] == pytest.approx(2 / 3)
    assert profile.keyword_frequencies["Space"] == pytest.approx(2 / 3)

# 3. 사용자 입력값 검증 테스트

@pytest.mark.parametrize("count", [0, 2, 11])
def test_invalid_content_count(count):
    contents = [
        SelectedContent(
            i, "movie", f"Content {i}",
            ["SF"], ["Space"],
        )
        for i in range(count)
    ]

    with pytest.raises(ValueError):
        build_preference_profile(
            UserPreferenceInput(contents)
        )


def test_duplicate_contents(sample_contents):
    contents = sample_contents + [sample_contents[0]]

    with pytest.raises(ValueError):
        build_preference_profile(
            UserPreferenceInput(contents)
        )


def test_too_many_preferred_genres(sample_contents):
    user_input = UserPreferenceInput(
        selected_contents=sample_contents,
        preferred_genres=[
            "SF", "Action", "Drama", "Comedy"
        ],
    )

    with pytest.raises(ValueError):
        build_preference_profile(user_input)

# 4.콘텐츠별 가중치 테스트

def test_raw_content_weights(sample_input):
    profile = build_preference_profile(sample_input)

    weights = [
        calculate_content_weight(content, profile)
        for content in sample_input.selected_contents
    ]

    assert weights == pytest.approx([
        2 / 3,
        2 / 3,
        1 / 3,
    ])


def test_normalized_weights(sample_input):
    weights = calculate_content_weights(sample_input)

    assert weights == pytest.approx({
        (1, "movie"): 0.4,
        (2, "movie"): 0.4,
        (3, "movie"): 0.2,
    })

    assert sum(weights.values()) == pytest.approx(1.0)


def test_uniform_weight_fallback():
    contents = [
        SelectedContent(
            i, "movie", f"Content {i}", [], []
        )
        for i in range(3)
    ]

    weights = calculate_content_weights(
        UserPreferenceInput(contents)
    )

    assert all(
        w == pytest.approx(1 / 3)
        for w in weights.values()
    )

    assert sum(weights.values()) == pytest.approx(1.0)

# 사용자 취향 벡터 테스트

def test_weighted_centroid(
    sample_input,
    sample_embeddings,
):
    vector = build_user_preference_vector(
        sample_input,
        sample_embeddings,
    )

    assert len(vector) == 768
    assert vector[0] == pytest.approx(4 / math.sqrt(17))
    assert vector[1] == pytest.approx(1 / math.sqrt(17))
    assert all(v == 0 for v in vector[2:])
    assert math.hypot(*vector) == pytest.approx(1.0)


def test_missing_embedding(
    sample_input,
    sample_embeddings,
):
    del sample_embeddings[(1, "movie")]

    with pytest.raises(ValueError):
        build_user_preference_vector(
            sample_input,
            sample_embeddings,
        )


@pytest.mark.parametrize("invalid_vector", [
    [1.0] * 767,
    [1.0] * 769,
    [float("nan")] + [1.0] * 767,
    [float("inf")] + [1.0] * 767,
    [0.0] * 768,
])
def test_invalid_embedding(
    sample_input,
    sample_embeddings,
    invalid_vector,
):
    sample_embeddings[(1, "movie")] = invalid_vector

    with pytest.raises(ValueError):
        build_user_preference_vector(
            sample_input,
            sample_embeddings,
        )


def test_zero_centroid(sample_input):
    embeddings = {
        (1, "movie"): [1.0] + [0.0] * 767,
        (2, "movie"): [-0.5] + [0.0] * 767,
        (3, "movie"): [-1.0] + [0.0] * 767,
    }

    with pytest.raises(ValueError):
        build_user_preference_vector(
            sample_input,
            embeddings,
        )
