
import math
from dataclasses import dataclass

from recommendation.candidate_generator import Candidate

from recommendation.preference_coverage import (
    ScoredContent,
    calculate_weighted_preference_coverage,
)


@dataclass(frozen=True)
class EvaluatedCandidate:
    """취향 충족도 평가가 완료된 OTT 추천 후보."""

    candidate: Candidate
    preference_coverage: float

    @property
    def total_price(self) -> int:
        return self.candidate.total_price

    @property
    def providers(self) -> frozenset[str]:
        return self.candidate.providers

    @property
    def items(self) -> tuple[str, ...]:
        return self.candidate.items

    @property
    def has_ads(self) -> bool:
        return self.candidate.has_ads


def evaluate_candidates(
    candidates: list[Candidate],
    contents: list[ScoredContent],
    threshold: float,
) -> list[EvaluatedCandidate]:
    """각 OTT 추천 후보의 가중 취향 충족도 계산."""

    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold는 0~1 사이여야 합니다.")

    coverage_cache: dict[frozenset[str], float] = {}

    evaluated = []

    for candidate in candidates:

        if not isinstance(candidate, Candidate):
            raise ValueError("유효하지 않은 추천 후보입니다.")

        providers = candidate.providers

        # 동일 OTT 조합의 충족도 재사용
        if providers not in coverage_cache:

            coverage_cache[providers] = (
                calculate_weighted_preference_coverage(
                    contents=contents,
                    selected_providers=sorted(providers),
                    threshold=threshold,
                )
            )

        evaluated.append(
            EvaluatedCandidate(
                candidate=candidate,
                preference_coverage=coverage_cache[providers],
            )
        )

    return evaluated
