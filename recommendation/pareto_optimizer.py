
import math

from recommendation.candidate_evaluator import (
    EvaluatedCandidate,
)


def dominates(
    a: EvaluatedCandidate,
    b: EvaluatedCandidate,
) -> bool:
    """후보 A가 후보 B를 Pareto 지배하는지 판단."""

    no_worse = (
        a.total_price <= b.total_price
        and
        a.preference_coverage >= b.preference_coverage
    )

    strictly_better = (
        a.total_price < b.total_price
        or
        a.preference_coverage > b.preference_coverage
    )

    return no_worse and strictly_better


def find_pareto_front(
    candidates: list[EvaluatedCandidate],
) -> list[EvaluatedCandidate]:
    """다른 후보에게 지배되지 않는 후보 목록 반환."""

    # 입력 데이터 검증
    for candidate in candidates:

        if not isinstance(candidate, EvaluatedCandidate):
            raise ValueError("유효하지 않은 평가 후보입니다.")

        score = candidate.preference_coverage

        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("취향 충족도는 0~1 사이여야 합니다.")

        if (
            type(candidate.total_price) is not int
            or candidate.total_price < 0
        ):
            raise ValueError("유효하지 않은 구독 비용입니다.")

    pareto_front = []

    for i, candidate in enumerate(candidates):

        is_dominated = any(
            dominates(other, candidate)
            for j, other in enumerate(candidates)
            if i != j
        )

        if not is_dominated:
            pareto_front.append(candidate)

    return sorted(
        pareto_front,
        key=lambda c: (
            c.total_price,
            -c.preference_coverage,
        ),
    )
