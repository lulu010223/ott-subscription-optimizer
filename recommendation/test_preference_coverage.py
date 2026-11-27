
import pytest

from recommendation.preference_coverage import (
    ScoredContent,
    calculate_weighted_preference_coverage,
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


# 1. OTT 조합별 충족도 계산
@pytest.mark.parametrize("providers, expected", [
    (["Netflix"], 1.85 / 3.50),
    (["Disney+"], 1.80 / 3.50),
    (["Watcha"], 0.80 / 3.50),
    (["Netflix", "Disney+"], 2.70 / 3.50),
    (["Netflix", "Watcha"], 2.65 / 3.50),
    (["Netflix", "Disney+", "Watcha"], 1.0),
    ([], 0.0),
])
def test_coverage(contents, providers, expected):
    result = calculate_weighted_preference_coverage(
        contents, providers, 0.80
    )

    assert result == pytest.approx(expected)
    assert 0 <= result <= 1


# 2. 중복 제공 콘텐츠 처리
def test_overlapping_contents(contents):
    result = calculate_weighted_preference_coverage(
        contents,
        ["Netflix", "Disney+"],
        0.80,
    )

    assert result == pytest.approx(2.70 / 3.50)


# 3. Threshold 경계값 포함 여부
def test_threshold_boundary(contents):
    result = calculate_weighted_preference_coverage(
        contents,
        ["Watcha"],
        0.80,
    )

    assert result == pytest.approx(0.80 / 3.50)


# 4. Threshold 변경에 따른 결과 검증
def test_threshold_filtering(contents):
    result = calculate_weighted_preference_coverage(
        contents,
        ["Netflix"],
        0.90,
    )

    assert result == pytest.approx(1.0)


# 5. 동일 OTT 중복 입력
def test_duplicate_providers(contents):
    result = calculate_weighted_preference_coverage(
        contents,
        ["Netflix", "Netflix"],
        0.80,
    )

    assert result == pytest.approx(1.85 / 3.50)


# 6. 복합키 기준 콘텐츠 구분
def test_composite_key():
    data = [
        ScoredContent(
            1, "movie", "A",
            ["Netflix"], 0.90,
        ),
        ScoredContent(
            1, "tv", "B",
            ["Disney+"], 0.90,
        ),
    ]

    result = calculate_weighted_preference_coverage(
        data, ["Netflix"], 0.80
    )

    assert result == pytest.approx(0.5)


# 7. 중복 콘텐츠 데이터 예외 처리
def test_duplicate_contents(contents):
    duplicated = contents + [contents[0]]

    with pytest.raises(ValueError):
        calculate_weighted_preference_coverage(
            duplicated, ["Netflix"], 0.80
        )


# 8. 잘못된 Threshold
@pytest.mark.parametrize("threshold", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_threshold(contents, threshold):
    with pytest.raises(ValueError):
        calculate_weighted_preference_coverage(
            contents, ["Netflix"], threshold
        )


# 9. 잘못된 취향 점수
@pytest.mark.parametrize("score", [
    -1.1,
    1.1,
    float("nan"),
    float("inf"),
])
def test_invalid_score(score):
    data = [
        ScoredContent(
            1, "movie", "A",
            ["Netflix"], score,
        ),
    ]

    with pytest.raises(ValueError):
        calculate_weighted_preference_coverage(
            data, ["Netflix"], 0.80
        )


# 10. 유효한 취향 콘텐츠가 없는 경우
def test_no_relevant_contents(contents):
    with pytest.raises(ValueError):
        calculate_weighted_preference_coverage(
            contents, ["Netflix"], 0.99
        )


# 11. 빈 콘텐츠 목록
def test_empty_contents():
    with pytest.raises(ValueError):
        calculate_weighted_preference_coverage(
            [], ["Netflix"], 0.80
        )


# 12. 음수 유사도 제외
def test_negative_similarity():
    data = [
        ScoredContent(
            1, "movie", "A",
            ["Netflix"], 0.90,
        ),
        ScoredContent(
            2, "movie", "B",
            ["Disney+"], -0.50,
        ),
    ]

    result = calculate_weighted_preference_coverage(
        data, ["Netflix"], 0.0
    )

    assert result == pytest.approx(1.0)


# 13. OTT 추가에 따른 충족도 단조 증가
def test_coverage_monotonicity(contents):
    single = calculate_weighted_preference_coverage(
        contents, ["Netflix"], 0.80
    )

    combined = calculate_weighted_preference_coverage(
        contents, ["Netflix", "Disney+"], 0.80
    )

    assert combined >= single
