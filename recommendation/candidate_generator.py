"""OTT subscription combinations. Prices and budgets are integer Korean won.

The generator returns every non-empty, affordable combination without provider
coverage overlap. Empty subscriptions are deliberately excluded. BigQuery is
only required when OTTDataFetcher is instantiated.
"""
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Optional


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _money(value, name):
    # BigQuery NUMERIC values arrive as Decimal. Reject fractional won.
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError(f"{name} must be a non-negative integer amount")
    if not value.is_finite() if isinstance(value, Decimal) else False:
        raise ValueError(f"{name} must be finite")
    if value < 0 or value != int(value):
        raise ValueError(f"{name} must be a non-negative integer amount")
    return int(value)


@dataclass(frozen=True)
class IncludedPlan:
    provider: str
    plan_name: str

    def __post_init__(self):
        object.__setattr__(self, "provider", _text(self.provider, "provider"))
        object.__setattr__(self, "plan_name", _text(self.plan_name, "plan_name"))


@dataclass(frozen=True)
class Plan:
    provider: str
    plan_name: str
    price: int
    ads: bool
    is_bundle: bool = False
    bundle_id: Optional[str] = None
    included_providers: frozenset[str] = frozenset()
    included_plans: tuple[IncludedPlan, ...] = ()
    simultaneous_streams: Optional[int] = None
    max_quality: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "provider", _text(self.provider, "provider"))
        object.__setattr__(self, "plan_name", _text(self.plan_name, "plan_name"))
        object.__setattr__(self, "price", _money(self.price, "price"))
        if type(self.ads) is not bool or type(self.is_bundle) is not bool:
            raise ValueError("ads and is_bundle must be bool")
        if self.bundle_id is not None:
            object.__setattr__(self, "bundle_id", _text(self.bundle_id, "bundle_id"))
        if self.is_bundle and self.bundle_id is None:
            raise ValueError("a bundle requires bundle_id")
        if not self.is_bundle and self.bundle_id is not None:
            raise ValueError("a standalone plan cannot have bundle_id")
        if self.simultaneous_streams is not None and (type(self.simultaneous_streams) is not int or self.simultaneous_streams < 1):
            raise ValueError("simultaneous_streams must be a positive integer or None")
        if self.max_quality is not None:
            object.__setattr__(self, "max_quality", _text(self.max_quality, "max_quality"))
        if isinstance(self.included_providers, (str, bytes)):
            raise ValueError("included_providers must be a collection of provider names")
        providers = frozenset(_text(p, "included provider") for p in self.included_providers)
        plans = tuple(self.included_plans)
        if any(not isinstance(p, IncludedPlan) for p in plans):
            raise ValueError("included_plans must contain IncludedPlan objects")
        if not self.is_bundle:
            if providers and providers != {self.provider}:
                raise ValueError("standalone provider coverage must match provider")
            providers = frozenset({self.provider})
            if plans and plans != (IncludedPlan(self.provider, self.plan_name),):
                raise ValueError("standalone included plan must match the plan")
            plans = (IncludedPlan(self.provider, self.plan_name),)
        elif not providers:
            providers = frozenset(p.provider for p in plans)
        if not providers:
            raise ValueError("a bundle must cover at least one provider")
        if plans and (len({p.provider for p in plans}) != len(plans) or {p.provider for p in plans} != providers):
            raise ValueError("included plan providers must match coverage without duplicates")
        object.__setattr__(self, "included_providers", providers)
        object.__setattr__(self, "included_plans", tuple(sorted(plans, key=lambda p: (p.provider, p.plan_name))))


@dataclass(frozen=True)
class Candidate:
    items: tuple[str, ...]
    providers: frozenset[str]
    total_price: int
    has_ads: bool
    details: tuple[Plan, ...]


def _plan_key(p):
    return (p.provider, p.plan_name, p.bundle_id or "", p.price, p.ads,
            p.is_bundle, tuple(sorted(p.included_providers)),
            tuple((x.provider, x.plan_name) for x in p.included_plans),
            (p.simultaneous_streams is not None, p.simultaneous_streams or 0),
            p.max_quality or "")


class CandidateGenerator:
    def __init__(self, options):
        options = tuple(options)
        if any(not isinstance(p, Plan) for p in options):
            raise ValueError("options must contain Plan objects")
        if len(set(options)) != len(options):
            raise ValueError("duplicate options are not allowed")
        self.options = tuple(sorted(options, key=_plan_key))

    def generate(self, budget: int, max_combination: Optional[int] = None) -> list[Candidate]:
        budget = _money(budget, "budget")
        if max_combination is not None and (type(max_combination) is not int or max_combination < 1):
            raise ValueError("max_combination must be a positive integer or None")
        limit = len(self.options) if max_combination is None else max_combination
        candidates = []

        def visit(start, chosen, providers, total):
            if chosen:
                candidates.append(Candidate(tuple(p.plan_name for p in chosen), providers,
                                            total, any(p.ads for p in chosen), tuple(chosen)))
            if len(chosen) == limit:
                return
            for i in range(start, len(self.options)):
                plan = self.options[i]
                if total + plan.price > budget or not providers.isdisjoint(plan.included_providers):
                    continue
                visit(i + 1, chosen + (plan,), providers | plan.included_providers, total + plan.price)

        visit(0, (), frozenset(), 0)
        return sorted(candidates, key=lambda c: (c.total_price, tuple(_plan_key(p) for p in c.details)))


class OTTDataFetcher:
    """Load BigQuery tables; optional client allows offline testing."""
    def __init__(self, project_id: str, dataset_id: str, client=None):
        project_id = _text(project_id, "project_id")
        dataset_id = _text(dataset_id, "dataset_id")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", project_id):
            raise ValueError("invalid project_id")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dataset_id):
            raise ValueError("invalid dataset_id")
        if client is None:
            try:
                from google.cloud import bigquery
            except ImportError as exc:
                raise ImportError("Install google-cloud-bigquery to fetch data") from exc
            client = bigquery.Client(project=project_id)
        self.client = client
        self.project_id = project_id
        self.dataset = dataset_id

    def fetch_all_options(self) -> list[Plan]:
        prefix = f"{self.project_id}.{self.dataset}"
        plans = self.client.query(f"SELECT provider, plan_name, monthly_price, ads, simultaneous_streams, max_quality FROM `{prefix}.ott_plans`")
        options = [Plan(row.provider, row.plan_name, row.monthly_price, row.ads,
                        simultaneous_streams=row.simultaneous_streams, max_quality=row.max_quality)
                   for row in plans]
        bundles = self.client.query(f"SELECT bundle_id, bundle_name, monthly_price, ads, included_plans FROM `{prefix}.bundle_catalog`")
        for row in bundles:
            included = tuple(IncludedPlan(p['provider'], p['plan_name']) for p in row.included_plans)
            options.append(Plan("BUNDLE", row.bundle_name, row.monthly_price, row.ads,
                                is_bundle=True, bundle_id=row.bundle_id, included_plans=included))
        return sorted(options, key=_plan_key)



if __name__ == "__main__":
    fetcher = OTTDataFetcher(
        project_id="lulu260902",
        dataset_id="ott_optimizer"
    )

    options = fetcher.fetch_all_options()
    print(f"조회된 구매 상품: {len(options)}개")

    generator = CandidateGenerator(options)
    candidates = generator.generate(budget=30000)

    print(f"생성된 추천 후보: {len(candidates)}개")

    for candidate in candidates[:10]:
        print(
            candidate.items,
            candidate.total_price,
            candidate.providers
        )
