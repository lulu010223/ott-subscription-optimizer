from dataclasses import FrozenInstanceError
from decimal import Decimal
from types import SimpleNamespace

import pytest
from candidate_generator import CandidateGenerator, IncludedPlan, OTTDataFetcher, Plan


@pytest.fixture
def mock_options():
    return [
        Plan("Netflix", "Basic", 9500, False, simultaneous_streams=2, max_quality="HD"),
        Plan("Disney+", "Standard", 9900, False),
        Plan("BUNDLE", "U+ Netflix/Disney", 15000, True, is_bundle=True,
             bundle_id="bundle-1", included_plans=(IncludedPlan("Netflix", "Basic"), IncludedPlan("Disney+", "Standard"))),
        Plan("Tving", "Ad-lite", 5500, True),
    ]


def test_all_nine_combinations(mock_options):
    results = CandidateGenerator(mock_options).generate(50000)
    expected = {frozenset(x) for x in [
        ("Basic",), ("Standard",), ("U+ Netflix/Disney",), ("Ad-lite",),
        ("Basic", "Standard"), ("Basic", "Ad-lite"), ("Standard", "Ad-lite"),
        ("U+ Netflix/Disney", "Ad-lite"), ("Basic", "Standard", "Ad-lite")
    ]}
    assert len(results) == 9
    assert {frozenset(c.items) for c in results} == expected
    for c in results:
        providers = [p for detail in c.details for p in detail.included_providers]
        assert len(providers) == len(set(providers))
        assert c.providers == frozenset(providers)
        assert c.total_price == sum(p.price for p in c.details)
        assert c.has_ads == any(p.ads for p in c.details)


def test_budget_and_bundle_price(mock_options):
    gen = CandidateGenerator(mock_options)
    results = gen.generate(20500)
    match = next(c for c in results if set(c.items) == {"U+ Netflix/Disney", "Ad-lite"})
    assert match.total_price == 20500
    assert all(c.total_price <= 20500 for c in results)
    assert match not in gen.generate(20499)
    assert gen.generate(0) == []


def test_full_combinations_and_explicit_limit():
    options = [Plan(f"provider-{i}", f"plan-{i}", 1, False) for i in range(5)]
    gen = CandidateGenerator(options)
    results = gen.generate(5)
    assert len(results) == 31
    assert sum(len(c.items) == 4 for c in results) == 5
    assert sum(len(c.items) == 5 for c in results) == 1
    assert len(gen.generate(5, max_combination=3)) == 25


def test_preservation_immutability_and_order(mock_options):
    gen = CandidateGenerator(mock_options)
    assert gen.generate(50000) == CandidateGenerator(reversed(mock_options)).generate(50000)
    results = gen.generate(50000)
    bundle = next(p for c in results for p in c.details if p.is_bundle)
    assert bundle.bundle_id == "bundle-1"
    assert set(bundle.included_plans) == {IncludedPlan("Netflix", "Basic"), IncludedPlan("Disney+", "Standard")}
    netflix = next(p for c in results for p in c.details if p.provider == "Netflix")
    assert (netflix.simultaneous_streams, netflix.max_quality) == (2, "HD")
    with pytest.raises(FrozenInstanceError):
        bundle.price = 1
    assert isinstance(bundle.included_providers, frozenset)


def test_input_validation(mock_options):
    for bad in (-1, 1.5, True, "10"):
        with pytest.raises(ValueError):
            CandidateGenerator(mock_options).generate(bad)
    with pytest.raises(ValueError):
        Plan("A", "A", -1, False)
    with pytest.raises(ValueError):
        Plan("A", "A", 1, False, included_providers={"B"})
    with pytest.raises(ValueError):
        Plan("BUNDLE", "bundle", 1, False, is_bundle=True, bundle_id="b", included_plans=(IncludedPlan("A", "x"), IncludedPlan("A", "y")))
    with pytest.raises(ValueError):
        CandidateGenerator([mock_options[0], mock_options[0]])
    with pytest.raises(ValueError):
        CandidateGenerator(mock_options).generate(10, 0)


def test_fetcher_maps_bigquery_rows():
    class Client:
        def query(self, sql):
            if "ott_plans`" in sql:
                return [SimpleNamespace(provider="Netflix", plan_name="Basic", monthly_price=Decimal("9500"), ads=False, simultaneous_streams=2, max_quality="HD")]
            return [SimpleNamespace(bundle_id="b1", bundle_name="Bundle", monthly_price=Decimal("15000"), ads=True, included_plans=[{"provider": "Netflix", "plan_name": "Basic"}, {"provider": "Disney+", "plan_name": "Standard"}])]
    options = OTTDataFetcher("my-project", "ott_optimizer", client=Client()).fetch_all_options()
    bundle = next(p for p in options if p.is_bundle)
    assert bundle.included_providers == {"Netflix", "Disney+"}
    assert IncludedPlan("Disney+", "Standard") in bundle.included_plans
    assert bundle.price == 15000 and type(bundle.price) is int
    assert next(p for p in options if not p.is_bundle).simultaneous_streams == 2
