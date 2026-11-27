
import math

import pytest

from recommendation.candidate_generator import Candidate

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)

from recommendation.ideal_point_optimizer import (
    IdealPointResult,
    rank_by_ideal_point,
    select_optimal_candidate,
)


def make_candidate(
    name,
    price,
    coverage,
    has_ads=False,
):
    """단위 테스트용 평가 후보 생성."""

    candidate = Candidate(
        items=(name,),
        providers=frozenset([name]),
        total_price=price,
        has_ads=has_ads,
        details=(),
    )

    return EvaluatedCandidate(
        candidate=candidate,
        preference_coverage=coverage,
    )


@pytest.fixture
def candidates():
    return [
        make_candidate("A", 5500, 1.85 / 3.50),
        make_candidate("B", 13400, 2.65 / 3.50),
        make_candidate("C", 15400, 2.70 / 3.50),
        make_candidate("D", 19500, 1.0),
    ]


# 1. 비용 정규화 정확성
def test_cost_normalization(candidates):
    results = rank_by_ideal_point(candidates)

    expected = {
        5500: 0.0,
        13400: 7900 / 14000,
        15400: 9900 / 14000,
        19500: 1.0,
    }

    for result in results:
        assert result.normalized_cost == pytest.approx(
            expected[result.total_price]
        )


# 2. 취향 충족도 정규화 정확성
def test_coverage_normalization(candidates):
    results = rank_by_ideal_point(candidates)

    expected = {
        5500: 0.0,
        13400: 0.80 / 1.65,
        15400: 0.85 / 1.65,
        19500: 1.0,
    }

    for result in results:
        assert result.normalized_coverage == pytest.approx(
            expected[result.total_price]
        )


# 3. 이상점 거리 계산 정확성
def test_ideal_point_distance(candidates):
    results = rank_by_ideal_point(candidates)

    expected = {
        5500: 1.0,
        13400: math.sqrt(
            (7900 / 14000) ** 2
            + (0.85 / 1.65) ** 2
        ),
        15400: math.sqrt(
            (9900 / 14000) ** 2
            + (0.80 / 1.65) ** 2
        ),
        19500: 1.0,
    }

    for result in results:
        assert result.distance == pytest.approx(
            expected[result.total_price]
        )


# 4. 정규화 및 거리 범위
def test_normalized_ranges(candidates):
    results = rank_by_ideal_point(candidates)

    for result in results:
        assert 0 <= result.normalized_cost <= 1
        assert 0 <= result.normalized_coverage <= 1
        assert 0 <= result.distance <= math.sqrt(2)


# 5. 추천 순위 정확성
def test_ranking(candidates):
    results = rank_by_ideal_point(candidates)

    assert [
        r.total_price for r in results
    ] == [
        13400,
        15400,
        5500,
        19500,
    ]


# 6. 최종 추천 후보 선정
def test_select_optimal_candidate(candidates):
    result = select_optimal_candidate(candidates)

    assert isinstance(result, IdealPointResult)
    assert result.total_price == 13400
    assert result.items == ("B",)
    assert result.preference_coverage == pytest.approx(
        2.65 / 3.50
    )


# 7. Pareto 지배 후보 자동 제거
def test_dominated_candidate_removal(candidates):
    dominated = make_candidate(
        "E", 20000, 0.50
    )

    results = rank_by_ideal_point(
        candidates + [dominated]
    )

    assert len(results) == 4

    assert all(
        r.evaluated_candidate != dominated
        for r in results
    )


# 8. 동일 비용 처리
def test_equal_cost():
    candidates = [
        make_candidate("A", 5000, 0.50),
        make_candidate("B", 5000, 0.90),
    ]

    results = rank_by_ideal_point(candidates)

    assert len(results) == 1
    assert results[0].items == ("B",)
    assert results[0].normalized_cost == 0.0
    assert results[0].distance == 0.0


# 9. 동일 충족도 처리
def test_equal_coverage():
    candidates = [
        make_candidate("A", 5000, 0.80),
        make_candidate("B", 10000, 0.80),
    ]

    results = rank_by_ideal_point(candidates)

    assert len(results) == 1
    assert results[0].items == ("A",)
    assert results[0].normalized_coverage == 1.0
    assert results[0].distance == 0.0


# 10. 동일 목적함수 후보 보존
def test_equal_objectives():
    candidates = [
        make_candidate("A", 5000, 0.80, True),
        make_candidate("B", 5000, 0.80, False),
    ]

    results = rank_by_ideal_point(candidates)

    assert len(results) == 2

    for result in results:
        assert result.normalized_cost == 0.0
        assert result.normalized_coverage == 1.0
        assert result.distance == 0.0


# 11. 동일 거리에서 낮은 비용 우선
def test_distance_tie_breaking():
    a = make_candidate("A", 5000, 0.50)
    b = make_candidate("B", 10000, 1.0)

    results = rank_by_ideal_point([b, a])

    assert results[0].distance == pytest.approx(1.0)
    assert results[1].distance == pytest.approx(1.0)

    assert results[0].items == ("A",)
    assert results[1].items == ("B",)


# 12. 단일 후보
def test_single_candidate():
    candidate = make_candidate("A", 5000, 0.80)

    results = rank_by_ideal_point([candidate])

    assert len(results) == 1
    assert results[0].distance == 0.0

    assert select_optimal_candidate(
        [candidate]
    ) == results[0]


# 13. 빈 후보 목록 순위 계산
def test_empty_ranking():
    assert rank_by_ideal_point([]) == []


# 14. 빈 후보 목록 최종 추천
def test_empty_selection():
    assert select_optimal_candidate([]) is None


# 15. 기존 후보 정보 보존
def test_candidate_preservation():
    candidate = make_candidate(
        "A", 5000, 0.80, True
    )

    result = select_optimal_candidate([candidate])

    assert result.evaluated_candidate is candidate
    assert result.total_price == candidate.total_price
    assert result.preference_coverage == candidate.preference_coverage
    assert result.items == candidate.items
    assert result.providers == candidate.providers
    assert result.has_ads == candidate.has_ads


# 16. 잘못된 후보 객체
def test_invalid_candidate():
    with pytest.raises(ValueError):
        rank_by_ideal_point([None])


# 17. 잘못된 취향 충족도
@pytest.mark.parametrize("coverage", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_coverage(coverage):
    candidate = make_candidate(
        "A", 5000, coverage
    )

    with pytest.raises(ValueError):
        rank_by_ideal_point([candidate])


# 18. 잘못된 구독 비용
@pytest.mark.parametrize("price", [
    -1000,
    5000.5,
    True,
])
def test_invalid_price(price):
    candidate = make_candidate(
        "A", price, 0.80
    )

    with pytest.raises(ValueError):
        rank_by_ideal_point([candidate])


# 19. 목적함수 경계값
def test_boundary_values():
    candidate = make_candidate("A", 0, 1.0)

    result = select_optimal_candidate([candidate])

    assert result.total_price == 0
    assert result.preference_coverage == 1.0
    assert result.distance == 0.0


# 20. 입력 목록 변경 방지
def test_input_preservation(candidates):
    original = candidates.copy()

    rank_by_ideal_point(candidates)

    assert candidates == original
