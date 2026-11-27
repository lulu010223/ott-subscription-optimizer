
from unittest.mock import patch

import pytest

from recommendation.candidate_generator import (
    Plan,
    IncludedPlan,
    CandidateGenerator,
)

from recommendation.preference_coverage import (
    ScoredContent,
)

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
    evaluate_candidates,
    calculate_weighted_preference_coverage,
)


@pytest.fixture
def candidates():
    options = [
        Plan("Netflix", "Netflix 광고형", 5500, True),
        Plan("Netflix", "Netflix 스탠다드", 13500, False),
        Plan("Disney+", "Disney+ 스탠다드", 9900, False),
        Plan("Watcha", "Watcha 베이직", 7900, False),
        Plan(
            provider="BUNDLE",
            plan_name="Disney+ · Watcha 결합",
            price=14000,
            ads=False,
            is_bundle=True,
            bundle_id="test_bundle",
            included_plans=(
                IncludedPlan("Disney+", "스탠다드"),
                IncludedPlan("Watcha", "베이직"),
            ),
        ),
    ]

    return CandidateGenerator(options).generate(
        budget=30000
    )


@pytest.fixture
def contents():
    return [
        ScoredContent(
            1, "movie", "A",
            ["Netflix", "Disney+"], 0.95,
        ),
        ScoredContent(
            2, "movie", "B",
            ["Netflix"], 0.90,
        ),
        ScoredContent(
            3, "movie", "C",
            ["Disney+"], 0.85,
        ),
        ScoredContent(
            4, "movie", "D",
            ["Watcha"], 0.80,
        ),
        ScoredContent(
            5, "movie", "E",
            ["Netflix"], 0.70,
        ),
    ]


# 1. 전체 후보 평가 및 결과 범위
def test_evaluate_candidates(candidates, contents):
    results = evaluate_candidates(
        candidates, contents, 0.80
    )

    assert len(results) == len(candidates) == 13

    assert all(
        isinstance(r, EvaluatedCandidate)
        for r in results
    )

    assert all(
        0 <= r.preference_coverage <= 1
        for r in results
    )


# 2. 기존 후보 정보 및 순서 보존
def test_candidate_preservation(candidates, contents):
    results = evaluate_candidates(
        candidates, contents, 0.80
    )

    for candidate, result in zip(candidates, results):
        assert result.candidate is candidate
        assert result.items == candidate.items
        assert result.providers == candidate.providers
        assert result.total_price == candidate.total_price
        assert result.has_ads == candidate.has_ads


# 3. OTT 조합별 충족도 정확성
def test_coverage_accuracy(candidates, contents):
    results = evaluate_candidates(
        candidates, contents, 0.80
    )

    expected = {
        frozenset(["Netflix"]): 1.85 / 3.50,
        frozenset(["Disney+"]): 1.80 / 3.50,
        frozenset(["Watcha"]): 0.80 / 3.50,
        frozenset(["Netflix", "Disney+"]): 2.70 / 3.50,
        frozenset(["Netflix", "Watcha"]): 2.65 / 3.50,
        frozenset(["Disney+", "Watcha"]): 2.60 / 3.50,
        frozenset(["Netflix", "Disney+", "Watcha"]): 1.0,
    }

    for result in results:
        assert result.preference_coverage == pytest.approx(
            expected[result.providers]
        )


# 4. 동일 OTT 조합의 캐싱 검증
def test_coverage_cache(candidates, contents):
    with patch(
        "recommendation.candidate_evaluator."
        "calculate_weighted_preference_coverage",
        wraps=calculate_weighted_preference_coverage,
    ) as mocked:

        results = evaluate_candidates(
            candidates, contents, 0.80
        )

        unique_combinations = {
            c.providers for c in candidates
        }

        assert len(results) == 13
        assert len(unique_combinations) == 7
        assert mocked.call_count == 7


# 5. 결합 상품과 개별 구독 비교
def test_bundle_coverage(candidates, contents):
    results = evaluate_candidates(
        candidates, contents, 0.80
    )

    target = frozenset(["Disney+", "Watcha"])

    matched = [
        r for r in results
        if r.providers == target
    ]

    assert len(matched) == 2

    assert matched[0].preference_coverage == pytest.approx(
        matched[1].preference_coverage
    )

    assert sorted(
        r.total_price for r in matched
    ) == [14000, 17800]


# 6. 서로 다른 threshold 간 캐시 독립성
def test_cache_isolation(candidates, contents):
    first = evaluate_candidates(
        candidates, contents, 0.80
    )

    second = evaluate_candidates(
        candidates, contents, 0.90
    )

    netflix = frozenset(["Netflix"])

    first_score = next(
        r.preference_coverage
        for r in first
        if r.providers == netflix
    )

    second_score = next(
        r.preference_coverage
        for r in second
        if r.providers == netflix
    )

    assert first_score == pytest.approx(1.85 / 3.50)
    assert second_score == pytest.approx(1.0)


# 7. 빈 후보 목록
def test_empty_candidates(contents):
    assert evaluate_candidates(
        [], contents, 0.80
    ) == []


# 8. 잘못된 후보 객체
def test_invalid_candidate(contents):
    with pytest.raises(ValueError):
        evaluate_candidates(
            [None], contents, 0.80
        )


# 9. 잘못된 threshold
@pytest.mark.parametrize("threshold", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_threshold(
    candidates, contents, threshold
):
    with pytest.raises(ValueError):
        evaluate_candidates(
            candidates, contents, threshold
        )


# 10. 유효한 취향 콘텐츠 부재
def test_no_relevant_contents(candidates, contents):
    with pytest.raises(ValueError):
        evaluate_candidates(
            candidates, contents, 0.99
        )
