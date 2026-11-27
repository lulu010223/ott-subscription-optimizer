
import pytest

from unittest.mock import patch

from recommendation.candidate_generator import Candidate

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)

from recommendation.ideal_point_optimizer import (
    rank_by_ideal_point,
)

from recommendation.alternative_recommender import (
    AlternativeRecommendation,
    RecommendationResult,
    recommend_alternatives,
)


def make_candidate(
    name,
    providers,
    price,
    coverage,
    has_ads=False,
):
    return EvaluatedCandidate(
        candidate=Candidate(
            items=(name,),
            providers=frozenset(providers),
            total_price=price,
            has_ads=has_ads,
            details=(),
        ),
        preference_coverage=coverage,
    )


@pytest.fixture
def candidates():
    return [
        make_candidate(
            "Netflix",
            ["Netflix"],
            5500,
            1.85 / 3.50,
            True,
        ),
        make_candidate(
            "Netflix + Watcha",
            ["Netflix", "Watcha"],
            13400,
            2.65 / 3.50,
            True,
        ),
        make_candidate(
            "Netflix + Disney+",
            ["Netflix", "Disney+"],
            15400,
            2.70 / 3.50,
            True,
        ),
        make_candidate(
            "Netflix + Disney+ + Watcha",
            ["Netflix", "Disney+", "Watcha"],
            19500,
            1.0,
            True,
        ),
        make_candidate(
            "Watcha",
            ["Watcha"],
            7900,
            0.80 / 3.50,
        ),
    ]


# 1. 반환 데이터 구조 검증
def test_result_structure(candidates):
    result = recommend_alternatives(candidates)

    assert isinstance(result, RecommendationResult)

    for recommendation in (
        result.balanced,
        result.budget_friendly,
        result.coverage_maximized,
    ):
        assert isinstance(
            recommendation,
            AlternativeRecommendation,
        )


# 2. 균형형 추천 정확성
def test_balanced_recommendation(candidates):
    result = recommend_alternatives(candidates)

    assert result.balanced.total_price == 13400

    assert result.balanced.providers == {
        "Netflix", "Watcha"
    }

    assert result.balanced.preference_coverage == pytest.approx(
        2.65 / 3.50
    )


# 3. 비용 절약형 추천 정확성
def test_budget_friendly_recommendation(candidates):
    result = recommend_alternatives(candidates)

    assert result.budget_friendly.total_price == 5500

    assert result.budget_friendly.providers == {
        "Netflix"
    }


# 4. 취향 충족형 추천 정확성
def test_coverage_maximized_recommendation(candidates):
    result = recommend_alternatives(candidates)

    assert result.coverage_maximized.total_price == 19500

    assert result.coverage_maximized.preference_coverage == 1.0

    assert result.coverage_maximized.providers == {
        "Netflix", "Disney+", "Watcha"
    }


# 5. 추천 유형 식별자 검증
def test_recommendation_types(candidates):
    result = recommend_alternatives(candidates)

    assert result.balanced.recommendation_type == "balanced"

    assert (
        result.budget_friendly.recommendation_type
        == "budget_friendly"
    )

    assert (
        result.coverage_maximized.recommendation_type
        == "coverage_maximized"
    )


# 6. 전체 및 Pareto 후보 수 검증
def test_candidate_counts(candidates):
    result = recommend_alternatives(candidates)

    assert result.total_candidate_count == 5
    assert result.pareto_candidate_count == 4


# 7. Pareto 지배 후보 제외
def test_dominated_candidate_exclusion(candidates):
    result = recommend_alternatives(candidates)

    for recommendation in (
        result.balanced,
        result.budget_friendly,
        result.coverage_maximized,
    ):
        assert recommendation.items != ("Watcha",)


# 8. 균형형 변화량 검증
def test_balanced_marginal_analysis(candidates):
    result = recommend_alternatives(candidates)

    marginal = result.balanced.marginal_analysis

    assert marginal.marginal_cost == 0
    assert marginal.marginal_coverage == 0
    assert marginal.marginal_efficiency is None
    assert marginal.added_providers == set()
    assert marginal.removed_providers == set()


# 9. 비용 절약형 변화량 검증
def test_budget_marginal_analysis(candidates):
    result = recommend_alternatives(candidates)

    marginal = result.budget_friendly.marginal_analysis

    assert marginal.marginal_cost == -7900

    assert marginal.marginal_coverage == pytest.approx(
        -0.80 / 3.50
    )

    assert marginal.removed_providers == {"Watcha"}
    assert marginal.marginal_efficiency is None


# 10. 취향 충족형 변화량 검증
def test_coverage_marginal_analysis(candidates):
    result = recommend_alternatives(candidates)

    marginal = result.coverage_maximized.marginal_analysis

    assert marginal.marginal_cost == 6100

    assert marginal.marginal_coverage == pytest.approx(
        0.85 / 3.50
    )

    assert marginal.added_providers == {"Disney+"}

    assert marginal.marginal_efficiency == pytest.approx(
        (0.85 / 3.50) * 100 / 6.1
    )


# 11. 변화량 분석 기준 일관성
def test_baseline_consistency(candidates):
    result = recommend_alternatives(candidates)

    baseline = result.balanced.candidate

    for recommendation in (
        result.balanced,
        result.budget_friendly,
        result.coverage_maximized,
    ):
        assert (
            recommendation.marginal_analysis.baseline
            is baseline
        )

        assert (
            recommendation.marginal_analysis.alternative
            is recommendation.candidate
        )


# 12. 동일 비용에서 높은 충족도 우선
def test_budget_tie_breaking():
    candidates = [
        make_candidate("A", ["Netflix"], 5000, 0.50),
        make_candidate("B", ["Watcha"], 5000, 0.80),
        make_candidate("C", ["Disney+"], 10000, 1.0),
    ]

    result = recommend_alternatives(candidates)

    assert result.budget_friendly.items == ("B",)


# 13. 동일 충족도에서 낮은 비용 우선
def test_coverage_tie_breaking():
    candidates = [
        make_candidate("A", ["Netflix"], 5000, 0.50),
        make_candidate("B", ["Watcha"], 10000, 0.90),
        make_candidate("C", ["Disney+"], 15000, 0.90),
    ]

    result = recommend_alternatives(candidates)

    assert result.coverage_maximized.items == ("B",)


# 14. 단일 후보 처리
def test_single_candidate():
    candidate = make_candidate(
        "Netflix",
        ["Netflix"],
        5500,
        0.80,
    )

    result = recommend_alternatives([candidate])

    assert result.total_candidate_count == 1
    assert result.pareto_candidate_count == 1

    for recommendation in (
        result.balanced,
        result.budget_friendly,
        result.coverage_maximized,
    ):
        assert recommendation.candidate is candidate

        assert (
            recommendation.marginal_analysis.marginal_cost
            == 0
        )

        assert (
            recommendation.marginal_analysis.marginal_coverage
            == 0
        )


# 15. 빈 후보 목록 처리
def test_empty_candidates():
    assert recommend_alternatives([]) is None


# 16. 잘못된 후보 객체
def test_invalid_candidate():
    with pytest.raises(ValueError):
        recommend_alternatives([None])


# 17. 잘못된 취향 충족도
@pytest.mark.parametrize("coverage", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_coverage(coverage):
    candidate = make_candidate(
        "Netflix",
        ["Netflix"],
        5500,
        coverage,
    )

    with pytest.raises(ValueError):
        recommend_alternatives([candidate])


# 18. 잘못된 구독 비용
@pytest.mark.parametrize("price", [
    -1000,
    5000.5,
    True,
])
def test_invalid_price(price):
    candidate = make_candidate(
        "Netflix",
        ["Netflix"],
        price,
        0.80,
    )

    with pytest.raises(ValueError):
        recommend_alternatives([candidate])


# 19. 기존 후보 정보 보존
def test_candidate_preservation(candidates):
    result = recommend_alternatives(candidates)

    for recommendation in (
        result.balanced,
        result.budget_friendly,
        result.coverage_maximized,
    ):
        candidate = recommendation.candidate

        assert any(
            candidate is original
            for original in candidates
        )

        assert recommendation.items == candidate.items
        assert recommendation.providers == candidate.providers
        assert recommendation.total_price == candidate.total_price
        assert recommendation.has_ads == candidate.has_ads

        assert (
            recommendation.preference_coverage
            == candidate.preference_coverage
        )


# 20. 중복 최적화 계산 방지
def test_single_optimizer_call(candidates):
    with patch(
        "recommendation.alternative_recommender."
        "rank_by_ideal_point",
        wraps=rank_by_ideal_point,
    ) as mocked:

        recommend_alternatives(candidates)

        assert mocked.call_count == 1


# 21. 추천 유형별 목적함수 최적성
def test_objective_optimality(candidates):
    result = recommend_alternatives(candidates)

    assert result.budget_friendly.total_price == min(
        c.total_price for c in candidates
    )

    assert result.coverage_maximized.preference_coverage == max(
        c.preference_coverage for c in candidates
    )

    assert result.balanced.result.distance == min(
        r.distance
        for r in rank_by_ideal_point(candidates)
    )


# 22. 입력 목록 변경 방지
def test_input_preservation(candidates):
    original = candidates.copy()

    recommend_alternatives(candidates)

    assert candidates == original
