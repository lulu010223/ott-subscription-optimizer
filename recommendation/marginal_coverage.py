
import math
from dataclasses import dataclass

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)


@dataclass(frozen=True)
class MarginalCoverageResult:
    """두 구독 조합 사이의 변화량 분석 결과."""

    baseline: EvaluatedCandidate
    alternative: EvaluatedCandidate

    added_providers: frozenset[str]
    removed_providers: frozenset[str]

    marginal_cost: int
    marginal_coverage: float
    marginal_efficiency: float | None

    @property
    def marginal_coverage_pp(self) -> float:
        return self.marginal_coverage * 100


def calculate_marginal_coverage(
    baseline: EvaluatedCandidate,
    alternative: EvaluatedCandidate,
) -> MarginalCoverageResult:
    """기준 구독 조합 대비 대안의 비용 및 충족도 변화량 계산."""

    # 1. 입력 데이터 검증
    for candidate in (baseline, alternative):

        if not isinstance(candidate, EvaluatedCandidate):
            raise ValueError("유효하지 않은 평가 후보입니다.")

        coverage = candidate.preference_coverage

        if not math.isfinite(coverage) or not 0 <= coverage <= 1:
            raise ValueError("유효하지 않은 취향 충족도입니다.")

        if (
            type(candidate.total_price) is not int
            or candidate.total_price < 0
        ):
            raise ValueError("유효하지 않은 구독 비용입니다.")

    # 2. 추가 및 제거 OTT 확인
    added_providers = (
        alternative.providers - baseline.providers
    )

    removed_providers = (
        baseline.providers - alternative.providers
    )

    # 3. 비용 변화량
    marginal_cost = (
        alternative.total_price
        - baseline.total_price
    )

    # 4. 취향 충족도 변화량
    marginal_coverage = (
        alternative.preference_coverage
        - baseline.preference_coverage
    )

    # 5. 추가 비용 1,000원당 충족도 변화량(%p)
    marginal_efficiency = (
        marginal_coverage * 100
        / (marginal_cost / 1000)
        if marginal_cost > 0
        else None
    )

    return MarginalCoverageResult(
        baseline=baseline,
        alternative=alternative,
        added_providers=added_providers,
        removed_providers=removed_providers,
        marginal_cost=marginal_cost,
        marginal_coverage=marginal_coverage,
        marginal_efficiency=marginal_efficiency,
    )
