
from dataclasses import dataclass

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)

from recommendation.ideal_point_optimizer import (
    IdealPointResult,
    rank_by_ideal_point,
)

from recommendation.marginal_coverage import (
    MarginalCoverageResult,
    calculate_marginal_coverage,
)


@dataclass(frozen=True)
class AlternativeRecommendation:
    """추천 유형별 후보 및 기준 조합 대비 변화량."""

    recommendation_type: str
    result: IdealPointResult
    marginal_analysis: MarginalCoverageResult

    @property
    def candidate(self) -> EvaluatedCandidate:
        return self.result.evaluated_candidate

    @property
    def items(self) -> tuple[str, ...]:
        return self.result.items

    @property
    def providers(self) -> frozenset[str]:
        return self.result.providers

    @property
    def total_price(self) -> int:
        return self.result.total_price

    @property
    def preference_coverage(self) -> float:
        return self.result.preference_coverage

    @property
    def has_ads(self) -> bool:
        return self.result.has_ads


@dataclass(frozen=True)
class RecommendationResult:
    """최종 추천 및 대안 추천 결과."""

    balanced: AlternativeRecommendation
    budget_friendly: AlternativeRecommendation
    coverage_maximized: AlternativeRecommendation

    total_candidate_count: int
    pareto_candidate_count: int


def recommend_alternatives(
    candidates: list[EvaluatedCandidate],
) -> RecommendationResult | None:
    """균형형, 비용 절약형, 취향 충족형 추천 생성."""

    # 1. Pareto Front 및 Ideal Point 순위 계산
    ranked = rank_by_ideal_point(candidates)

    if not ranked:
        return None

    # 2. 균형형 추천
    balanced = ranked[0]

    # 3. 비용 절약형 추천
    budget_friendly = min(
        ranked,
        key=lambda r: (
            r.total_price,
            -r.preference_coverage,
        ),
    )

    # 4. 취향 충족형 추천
    coverage_maximized = min(
        ranked,
        key=lambda r: (
            -r.preference_coverage,
            r.total_price,
        ),
    )

    # 5. 기준 추천 후보 설정
    baseline = balanced.evaluated_candidate

    # 6. 추천 유형별 변화량 분석
    def build_recommendation(
        recommendation_type: str,
        result: IdealPointResult,
    ) -> AlternativeRecommendation:

        marginal = calculate_marginal_coverage(
            baseline=baseline,
            alternative=result.evaluated_candidate,
        )

        return AlternativeRecommendation(
            recommendation_type=recommendation_type,
            result=result,
            marginal_analysis=marginal,
        )

    # 7. 최종 추천 결과 반환
    return RecommendationResult(
        balanced=build_recommendation(
            "balanced",
            balanced,
        ),
        budget_friendly=build_recommendation(
            "budget_friendly",
            budget_friendly,
        ),
        coverage_maximized=build_recommendation(
            "coverage_maximized",
            coverage_maximized,
        ),
        total_candidate_count=len(candidates),
        pareto_candidate_count=len(ranked),
    )
