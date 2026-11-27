
import pytest

from recommendation.candidate_generator import Candidate

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)

from recommendation.marginal_coverage import (
    MarginalCoverageResult,
    calculate_marginal_coverage,
)


def make_candidate(name, providers, price, coverage):
    return EvaluatedCandidate(
        candidate=Candidate(
            items=(name,),
            providers=frozenset(providers),
            total_price=price,
            has_ads=False,
            details=(),
        ),
        preference_coverage=coverage,
    )


@pytest.fixture
def baseline():
    return make_candidate(
        "Netflix + Watcha",
        ["Netflix", "Watcha"],
        13400,
        2.65 / 3.50,
    )


# 1. 비용 변화량 계산
def test_marginal_cost(baseline):
    alternative = make_candidate(
        "Netflix + Watcha + Disney+",
        ["Netflix", "Watcha", "Disney+"],
        23300,
        1.0,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_cost == 9900


# 2. 취향 충족도 변화량 계산
def test_marginal_coverage(baseline):
    alternative = make_candidate(
        "Netflix + Watcha + Disney+",
        ["Netflix", "Watcha", "Disney+"],
        23300,
        1.0,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_coverage == pytest.approx(
        0.85 / 3.50
    )


# 3. 퍼센트포인트 변환
def test_percentage_point_conversion(baseline):
    alternative = make_candidate(
        "Netflix + Watcha + Disney+",
        ["Netflix", "Watcha", "Disney+"],
        23300,
        1.0,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_coverage_pp == pytest.approx(
        0.85 / 3.50 * 100
    )


# 4. 한계 비용 효율성 계산
def test_marginal_efficiency(baseline):
    alternative = make_candidate(
        "Netflix + Watcha + Disney+",
        ["Netflix", "Watcha", "Disney+"],
        23300,
        1.0,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    expected = (
        (0.85 / 3.50) * 100 / 9.9
    )

    assert result.marginal_efficiency == pytest.approx(
        expected
    )


# 5. 결합 상품의 비용 효율성 비교
def test_bundle_efficiency(baseline):
    individual = make_candidate(
        "개별 구독",
        ["Netflix", "Watcha", "Disney+"],
        23300,
        1.0,
    )

    bundle = make_candidate(
        "결합 구독",
        ["Netflix", "Watcha", "Disney+"],
        19500,
        1.0,
    )

    individual_result = calculate_marginal_coverage(
        baseline, individual
    )

    bundle_result = calculate_marginal_coverage(
        baseline, bundle
    )

    assert bundle_result.marginal_coverage == pytest.approx(
        individual_result.marginal_coverage
    )

    assert bundle_result.marginal_cost == 6100

    assert (
        bundle_result.marginal_efficiency
        > individual_result.marginal_efficiency
    )


# 6. OTT 추가
def test_added_providers(baseline):
    alternative = make_candidate(
        "Netflix + Watcha + Disney+",
        ["Netflix", "Watcha", "Disney+"],
        19500,
        1.0,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.added_providers == {"Disney+"}
    assert result.removed_providers == set()


# 7. OTT 제거
def test_removed_providers(baseline):
    alternative = make_candidate(
        "Netflix",
        ["Netflix"],
        5500,
        1.85 / 3.50,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.added_providers == set()
    assert result.removed_providers == {"Watcha"}


# 8. OTT 교체
def test_provider_replacement(baseline):
    alternative = make_candidate(
        "Netflix + Disney+",
        ["Netflix", "Disney+"],
        15400,
        2.70 / 3.50,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.added_providers == {"Disney+"}
    assert result.removed_providers == {"Watcha"}

    assert result.marginal_cost == 2000

    assert result.marginal_coverage == pytest.approx(
        0.05 / 3.50
    )


# 9. 비용 절약형 대안
def test_negative_cost(baseline):
    alternative = make_candidate(
        "Netflix",
        ["Netflix"],
        5500,
        1.85 / 3.50,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_cost == -7900

    assert result.marginal_coverage == pytest.approx(
        -0.80 / 3.50
    )

    assert result.marginal_efficiency is None


# 10. 비용 증가 및 충족도 감소
def test_negative_efficiency(baseline):
    alternative = make_candidate(
        "Alternative",
        ["Disney+"],
        20000,
        0.50,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_cost > 0
    assert result.marginal_coverage < 0
    assert result.marginal_efficiency < 0


# 11. 동일 비용에서 충족도 증가
def test_zero_cost_positive_coverage(baseline):
    alternative = make_candidate(
        "Alternative",
        ["Netflix", "Disney+"],
        13400,
        0.90,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_cost == 0
    assert result.marginal_coverage > 0
    assert result.marginal_efficiency is None


# 12. 추가 비용은 있지만 충족도 동일
def test_zero_coverage_gain(baseline):
    alternative = make_candidate(
        "Alternative",
        ["Netflix", "Watcha"],
        15000,
        baseline.preference_coverage,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_cost == 1600
    assert result.marginal_coverage == 0
    assert result.marginal_efficiency == 0


# 13. 동일 구독 조합
def test_identical_candidate(baseline):
    result = calculate_marginal_coverage(
        baseline, baseline
    )

    assert result.marginal_cost == 0
    assert result.marginal_coverage == 0
    assert result.marginal_efficiency is None
    assert result.added_providers == set()
    assert result.removed_providers == set()


# 14. 기존 후보 정보 보존
def test_candidate_preservation(baseline):
    alternative = make_candidate(
        "Alternative",
        ["Netflix", "Disney+"],
        15400,
        0.80,
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert isinstance(result, MarginalCoverageResult)
    assert result.baseline is baseline
    assert result.alternative is alternative


# 15. 잘못된 기준 후보
def test_invalid_baseline(baseline):
    with pytest.raises(ValueError):
        calculate_marginal_coverage(None, baseline)


# 16. 잘못된 대안 후보
def test_invalid_alternative(baseline):
    with pytest.raises(ValueError):
        calculate_marginal_coverage(baseline, None)


# 17. 잘못된 취향 충족도
@pytest.mark.parametrize("coverage", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_coverage(baseline, coverage):
    alternative = make_candidate(
        "Alternative",
        ["Netflix"],
        15000,
        coverage,
    )

    with pytest.raises(ValueError):
        calculate_marginal_coverage(
            baseline, alternative
        )


# 18. 잘못된 구독 비용
@pytest.mark.parametrize("price", [
    -1000,
    5000.5,
    True,
])
def test_invalid_price(baseline, price):
    alternative = make_candidate(
        "Alternative",
        ["Netflix"],
        price,
        0.80,
    )

    with pytest.raises(ValueError):
        calculate_marginal_coverage(
            baseline, alternative
        )


# 19. 충족도 경계값
def test_boundary_values():
    baseline = make_candidate(
        "A", ["Netflix"], 0, 0.0
    )

    alternative = make_candidate(
        "B", ["Netflix", "Watcha"], 1000, 1.0
    )

    result = calculate_marginal_coverage(
        baseline, alternative
    )

    assert result.marginal_coverage == 1.0
    assert result.marginal_coverage_pp == 100.0
    assert result.marginal_efficiency == 100.0
