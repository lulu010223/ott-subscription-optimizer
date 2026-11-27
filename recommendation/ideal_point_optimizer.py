
import math
from dataclasses import dataclass

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)

from recommendation.pareto_optimizer import (
    find_pareto_front,
)


@dataclass(frozen=True)
class IdealPointResult:
    """이상점 거리 계산이 완료된 추천 후보."""

    evaluated_candidate: EvaluatedCandidate
    normalized_cost: float
    normalized_coverage: float
    distance: float

    @property
    def total_price(self) -> int:
        return self.evaluated_candidate.total_price

    @property
    def preference_coverage(self) -> float:
        return self.evaluated_candidate.preference_coverage

    @property
    def items(self) -> tuple[str, ...]:
        return self.evaluated_candidate.items

    @property
    def providers(self) -> frozenset[str]:
        return self.evaluated_candidate.providers

    @property
    def has_ads(self) -> bool:
        return self.evaluated_candidate.has_ads


def rank_by_ideal_point(
    candidates: list[EvaluatedCandidate],
) -> list[IdealPointResult]:
    """Pareto 최적 후보를 이상점 거리 기준으로 정렬."""

    # Pareto Front 계산 및 입력 데이터 검증
    front = find_pareto_front(candidates)

    if not front:
        return []

    # 1. 목적함수별 최솟값 및 최댓값
    min_cost = min(c.total_price for c in front)
    max_cost = max(c.total_price for c in front)

    min_coverage = min(
        c.preference_coverage for c in front
    )

    max_coverage = max(
        c.preference_coverage for c in front
    )

    cost_range = max_cost - min_cost
    coverage_range = max_coverage - min_coverage

    results = []

    for candidate in front:

        # 2. 비용 정규화
        normalized_cost = (
            (candidate.total_price - min_cost)
            / cost_range
            if cost_range > 0
            else 0.0
        )

        # 3. 취향 충족도 정규화
        normalized_coverage = (
            (
                candidate.preference_coverage
                - min_coverage
            )
            / coverage_range
            if coverage_range > 0
            else 1.0
        )

        # 4. 이상점 (0, 1)과의 유클리드 거리
        distance = math.hypot(
            normalized_cost,
            1.0 - normalized_coverage,
        )

        results.append(
            IdealPointResult(
                evaluated_candidate=candidate,
                normalized_cost=normalized_cost,
                normalized_coverage=normalized_coverage,
                distance=distance,
            )
        )

    # 5. 이상점 거리 기준 순위 결정
    return sorted(
        results,
        key=lambda r: (
            r.distance,
            r.total_price,
            -r.preference_coverage,
        ),
    )


def select_optimal_candidate(
    candidates: list[EvaluatedCandidate],
) -> IdealPointResult | None:
    """이상점과 가장 가까운 최적 구독 조합 반환."""

    ranked = rank_by_ideal_point(candidates)

    return ranked[0] if ranked else None
