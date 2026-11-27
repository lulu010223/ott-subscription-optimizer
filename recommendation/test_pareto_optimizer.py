
import pytest

from recommendation.candidate_generator import Candidate

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)

from recommendation.pareto_optimizer import (
    dominates,
    find_pareto_front,
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


# 1. 비용과 충족도 모두 우수
def test_dominates_both_objectives():
    a = make_candidate("A", 5000, 0.90)
    b = make_candidate("B", 10000, 0.70)

    assert dominates(a, b)
    assert not dominates(b, a)


# 2. 동일 충족도, 더 낮은 비용
def test_dominates_lower_cost():
    a = make_candidate("A", 5000, 0.80)
    b = make_candidate("B", 10000, 0.80)

    assert dominates(a, b)


# 3. 동일 비용, 더 높은 충족도
def test_dominates_higher_coverage():
    a = make_candidate("A", 5000, 0.90)
    b = make_candidate("B", 5000, 0.70)

    assert dominates(a, b)


# 4. 비용과 충족도 간 상충 관계
def test_tradeoff():
    a = make_candidate("A", 5000, 0.60)
    b = make_candidate("B", 10000, 0.90)

    assert not dominates(a, b)
    assert not dominates(b, a)


# 5. 동일 목적함수 값
def test_equal_objectives():
    a = make_candidate("A", 5000, 0.80)
    b = make_candidate("B", 5000, 0.80)

    assert not dominates(a, b)
    assert not dominates(b, a)


# 6. 자기 자신에 대한 지배 관계
def test_self_dominance():
    a = make_candidate("A", 5000, 0.80)

    assert not dominates(a, a)


# 7. Pareto Front 정확성
def test_pareto_front():
    a = make_candidate("A", 5000, 0.50)
    b = make_candidate("B", 7000, 0.40)
    c = make_candidate("C", 10000, 0.80)
    d = make_candidate("D", 12000, 0.80)
    e = make_candidate("E", 15000, 1.00)

    front = find_pareto_front(
        [a, b, c, d, e]
    )

    assert front == [a, c, e]


# 8. 모든 후보가 비지배 후보인 경우
def test_all_non_dominated():
    candidates = [
        make_candidate("A", 5000, 0.50),
        make_candidate("B", 10000, 0.80),
        make_candidate("C", 15000, 1.00),
    ]

    assert find_pareto_front(
        candidates
    ) == candidates


# 9. 하나의 후보가 나머지를 모두 지배
def test_single_dominant_candidate():
    a = make_candidate("A", 5000, 1.00)
    b = make_candidate("B", 7000, 0.80)
    c = make_candidate("C", 10000, 0.50)

    assert find_pareto_front(
        [b, c, a]
    ) == [a]


# 10. 동일 목적함수 후보 보존
def test_preserve_equal_candidates():
    a = make_candidate(
        "A", 5000, 0.80, has_ads=True
    )

    b = make_candidate(
        "B", 5000, 0.80, has_ads=False
    )

    front = find_pareto_front([a, b])

    assert len(front) == 2
    assert a in front
    assert b in front


# 11. 결과 정렬 검증
def test_sorted_front():
    a = make_candidate("A", 5000, 0.50)
    b = make_candidate("B", 10000, 0.80)
    c = make_candidate("C", 15000, 1.00)

    assert find_pareto_front(
        [c, a, b]
    ) == [a, b, c]


# 12. 빈 후보 목록
def test_empty_candidates():
    assert find_pareto_front([]) == []


# 13. 단일 후보
def test_single_candidate():
    a = make_candidate("A", 5000, 0.80)

    assert find_pareto_front([a]) == [a]


# 14. 잘못된 후보 객체
def test_invalid_candidate():
    with pytest.raises(ValueError):
        find_pareto_front([None])


# 15. 잘못된 취향 충족도
@pytest.mark.parametrize("coverage", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_coverage(coverage):
    a = make_candidate("A", 5000, coverage)

    with pytest.raises(ValueError):
        find_pareto_front([a])


# 16. 잘못된 구독 비용
@pytest.mark.parametrize("price", [
    -1000,
    5000.5,
    True,
])
def test_invalid_price(price):
    a = make_candidate("A", price, 0.80)

    with pytest.raises(ValueError):
        find_pareto_front([a])


# 17. 목적함수 경계값
def test_boundary_values():
    a = make_candidate("A", 0, 0.0)
    b = make_candidate("B", 10000, 1.0)

    assert find_pareto_front(
        [a, b]
    ) == [a, b]


# 18. 입력 목록 변경 방지
def test_input_preservation():
    a = make_candidate("A", 5000, 0.50)
    b = make_candidate("B", 10000, 0.80)

    candidates = [b, a]
    original = candidates.copy()

    find_pareto_front(candidates)

    assert candidates == original
