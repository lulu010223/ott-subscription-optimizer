
from collections import Counter
from dataclasses import dataclass, field
import math

EMBEDDING_DIMENSION = 768


@dataclass
class SelectedContent:
    """사용자가 선택한 콘텐츠 정보."""

    tmdb_id: int
    media_type: str
    title: str
    genres: list[str]
    keywords: list[str]


@dataclass
class PreferenceProfile:
    """사용자의 장르 및 키워드 취향 프로필."""

    genre_frequencies: dict[str, float]
    keyword_frequencies: dict[str, float]


@dataclass
class UserPreferenceInput:
    """사용자의 취향 분석 입력값."""

    selected_contents: list[SelectedContent]
    preferred_genres: list[str] = field(
        default_factory=list
    )


def build_preference_profile(
    user_input: UserPreferenceInput,
) -> PreferenceProfile:
    """장르 및 키워드 빈도 기반 취향 프로필 생성."""

    contents = user_input.selected_contents
    preferred_genres = set(user_input.preferred_genres)

    n = len(contents)

    if not 3 <= n <= 10:
        raise ValueError(
            "선호 콘텐츠는 3~10개 선택해야 합니다."
        )

    keys = {
        (c.tmdb_id, c.media_type)
        for c in contents
    }

    if len(keys) != n:
        raise ValueError(
            "동일한 콘텐츠를 중복 선택할 수 없습니다."
        )

    if len(preferred_genres) > 3:
        raise ValueError(
            "선호 장르는 최대 3개까지 선택할 수 있습니다."
        )

    genre_counts = Counter()
    keyword_counts = Counter()

    # 선택 콘텐츠의 장르 및 키워드 등장 횟수 계산
    for content in contents:
        genre_counts.update(set(content.genres))
        keyword_counts.update(set(content.keywords))

    # 직접 선택한 선호 장르를 추가 관측값으로 반영
    genre_counts.update(preferred_genres)

    genre_denominator = n + int(bool(preferred_genres))

    # 장르별 빈도 계산
    genre_frequencies = {
        genre: count / genre_denominator
        for genre, count in genre_counts.items()
    }

    # 키워드별 빈도 계산
    keyword_frequencies = {
        keyword: count / n
        for keyword, count in keyword_counts.items()
    }

    return PreferenceProfile(
        genre_frequencies=genre_frequencies,
        keyword_frequencies=keyword_frequencies,
    )

# 콘텐츠별 가중치 계산
def calculate_content_weight(
    content: SelectedContent,
    profile: PreferenceProfile,
) -> float:
    """개별 콘텐츠의 취향 기반 가중치 계산."""

    genre_scores = [
        profile.genre_frequencies.get(genre, 0.0)
        for genre in set(content.genres)
    ]

    keyword_scores = [
        profile.keyword_frequencies.get(keyword, 0.0)
        for keyword in set(content.keywords)
    ]

    scores = genre_scores + keyword_scores

    if not scores:
        return 0.0

    return sum(scores) / len(scores)

# 전체 콘텐츠 가중치 정규화

def calculate_content_weights(
    user_input: UserPreferenceInput,
) -> dict[tuple[int, str], float]:
    """선택 콘텐츠별 가중치 계산 및 정규화."""

    profile = build_preference_profile(user_input)

    raw_weights = {
        (content.tmdb_id, content.media_type):
            calculate_content_weight(content, profile)
        for content in user_input.selected_contents
    }

    total_weight = sum(raw_weights.values())

    # 모든 가중치가 0인 경우 균등 가중치 적용
    if total_weight == 0:
        n = len(raw_weights)

        return {
            key: 1.0 / n
            for key in raw_weights
        }

    return {
        key: weight / total_weight
        for key, weight in raw_weights.items()
    }


def build_user_preference_vector(
    user_input: UserPreferenceInput,
    embeddings: dict[tuple[int, str], list[float]],
) -> list[float]:
    """Weighted Centroid 기반 사용자 취향 벡터 생성."""

    weights = calculate_content_weights(user_input)

    user_vector = [0.0] * EMBEDDING_DIMENSION

    for content in user_input.selected_contents:
        key = (content.tmdb_id, content.media_type)

        if key not in embeddings:
            raise ValueError(
                f"임베딩이 없는 콘텐츠: {key}"
            )

        vector = embeddings[key]
        weight = weights[key]

        if len(vector) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"임베딩 차원 불일치: {key}"
            )

        if (
            not all(math.isfinite(v) for v in vector)
            or not any(v != 0 for v in vector)
        ):
            raise ValueError(
                f"유효하지 않은 임베딩: {key}"
            )

        # 각 차원에 콘텐츠별 가중치 적용
        for i, value in enumerate(vector):
            user_vector[i] += weight * value

    # 사용자 취향 벡터의 L2 Norm 계산
    norm = math.hypot(*user_vector)

    if not math.isfinite(norm) or norm == 0:
        raise ValueError(
            "유효하지 않은 사용자 취향 벡터입니다."
        )

    # L2 Normalization
    return [
        value / norm
        for value in user_vector
    ]
