
import math
from dataclasses import dataclass


@dataclass
class ScoredContent:
    """취향 유사도 계산이 완료된 콘텐츠."""

    tmdb_id: int
    media_type: str
    title: str
    providers: list[str]
    preference_score: float


def calculate_weighted_preference_coverage(
    contents: list[ScoredContent],
    selected_providers: list[str],
    threshold: float,
) -> float:
    """OTT 조합의 가중 취향 충족도 계산."""

    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold는 0~1 사이여야 합니다.")

    provider_set = set(selected_providers)

    denominator = 0.0
    numerator = 0.0

    seen = set()

    for content in contents:
        key = (
            content.tmdb_id,
            content.media_type,
        )

        if key in seen:
            raise ValueError(f"중복 콘텐츠: {key}")

        seen.add(key)

        score = content.preference_score

        if not math.isfinite(score) or not -1 <= score <= 1:
            raise ValueError(f"유효하지 않은 취향 점수: {key}")

        # threshold 미만 콘텐츠 제외
        if score < threshold:
            continue

        # 전체 취향 관련 콘텐츠 점수 합계
        denominator += score

        # 선택 OTT 중 하나 이상이 제공하는 콘텐츠
        if provider_set.intersection(content.providers):
            numerator += score

    if denominator == 0:
        raise ValueError("유효한 취향 점수 합계가 없습니다.")

    return numerator / denominator
