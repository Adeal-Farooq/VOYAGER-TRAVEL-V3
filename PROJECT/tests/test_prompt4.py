"""PROMPT_4 tests: reliability, sentiment, TOPSIS scoring, ride pricing.

Pure-function unit tests only (no API keys / network). Covers the formulas
locked in PROMPT_4:
- reliability = 0.5*(rating/5) + 0.3*sentiment + 0.2*count, x status factor
- pin classes green/yellow/red
- sentiment polarity in [0,1], lexicon handles negation
- TOPSIS: cost/benefit directions, weights, rank order, best_match
- ride pricing: total is vehicle fare (never pp*group), source labeling
"""
import numpy as np

from backend.services.data_schema import (
    ReliabilityInput,
    RidePrice,
    ScoringContext,
    ScoredRoute,
    TopsisWeights,
)
from backend.services.reliability import compute_reliability, pin_class_of
from backend.services.ride_pricing import (
    coord_to_str,
    estimate_ride_prices,
    fetch_live_prices,
    merge_live_prices,
    ride_prices_for_distance,
)
from backend.services.sentiment import review_polarity, sentiment_avg
from backend.services.topsis_engine import (
    RouteCriterionValues,
    score_routes,
)


# ---------------------------------------------------------------- reliability
class TestReliability:
    def test_perfect_place_scores_high(self):
        r = compute_reliability(ReliabilityInput(
            rating=5.0, review_count=200, sentiment_avg=0.9,
            business_status="OPERATIONAL"))
        assert r.score_pct >= 80
        assert r.pin_class == "green"

    def test_negative_reviews_drag_score(self):
        r = compute_reliability(ReliabilityInput(
            rating=3.0, review_count=5, sentiment_avg=0.2,
            business_status="OPERATIONAL"))
        assert r.score < 0.5
        assert r.pin_class == "red"

    def test_permanently_closed_is_always_red(self):
        r = compute_reliability(ReliabilityInput(
            rating=4.5, review_count=300, sentiment_avg=0.8,
            business_status="CLOSED_PERMANENTLY"))
        assert r.pin_class == "red"
        assert r.score == 0.0

    def test_temporarily_closed_capped_at_yellow(self):
        r = compute_reliability(ReliabilityInput(
            rating=4.5, review_count=300, sentiment_avg=0.8,
            business_status="CLOSED_TEMPORARILY"))
        assert r.pin_class == "yellow"

    def test_unknown_status_no_penalty(self):
        r = compute_reliability(ReliabilityInput(
            rating=4.2, review_count=50, sentiment_avg=0.7, business_status=None))
        assert r.score > 0.5

    def test_no_reviews_still_explainable(self):
        r = compute_reliability(ReliabilityInput(
            rating=4.0, review_count=0, sentiment_avg=0.5, business_status="OPERATIONAL"))
        assert 0 <= r.score <= 1
        assert r.count_part == 0.0

    def test_pin_class_of_edges(self):
        assert pin_class_of(0.8, "OPERATIONAL") == "green"
        assert pin_class_of(0.6, None) == "yellow"
        assert pin_class_of(0.4, "OPERATIONAL") == "red"
        assert pin_class_of(0.9, "CLOSED_PERMANENTLY") == "red"


# ---------------------------------------------------------------- sentiment
class TestSentiment:
    def test_positive_review(self):
        assert review_polarity("The food was delicious and the staff were very friendly!") > 0.6

    def test_negative_review(self):
        assert review_polarity("Terrible service, rude staff, dirty washroom.") < 0.4

    def test_negation_flips(self):
        # "not clean" should score lower than "clean"
        a = review_polarity("The place is clean")
        b = review_polarity("The place is not clean")
        assert b < a

    def test_neutral_when_no_lexicon_words(self):
        assert review_polarity("") == 0.5
        assert review_polarity("lorem ipsum dolor") == 0.5

    def test_empty_list_average_is_neutral(self):
        assert sentiment_avg([]) == 0.5

    def test_average_over_reviews(self):
        avg = sentiment_avg(["Great place", "Terrible place"])
        assert 0.35 < avg < 0.65


# ---------------------------------------------------------------- TOPSIS
class TestTopsis:
    def _route(self, fare=0.0, dur=0, walk=0.0, transfers=0) -> ScoredRoute:
        return ScoredRoute(total_fare=fare, total_duration_min=dur,
                           total_walk_km=walk, transfers=transfers)

    def test_best_route_ranks_first_on_cost(self):
        cheap = self._route(fare=50.0, dur=60)
        expensive = self._route(fare=400.0, dur=30)
        ctx = ScoringContext()
        score_routes([cheap, expensive], [
            RouteCriterionValues(cost=50.0, time_of_day=60.0),
            RouteCriterionValues(cost=400.0, time_of_day=30.0),
        ], ctx, TopsisWeights(cost=0.8, time_of_day=0.05, walking=0.05,
                              traffic_crowd=0.02, weather=0.02, availability=0.02,
                              safety=0.02, group_size=0.02))
        assert cheap.rank == 1
        assert cheap.best_match
        assert expensive.rank == 2

    def test_fastest_route_ranks_first_on_time(self):
        slow = self._route(fare=100.0, dur=90)
        fast = self._route(fare=300.0, dur=20)
        ctx = ScoringContext()
        score_routes([slow, fast], [
            RouteCriterionValues(cost=100.0, time_of_day=90.0),
            RouteCriterionValues(cost=300.0, time_of_day=20.0),
        ], ctx, TopsisWeights(cost=0.05, time_of_day=0.8, walking=0.05,
                              traffic_crowd=0.02, weather=0.02, availability=0.02,
                              safety=0.02, group_size=0.02))
        assert fast.rank == 1

    def test_weather_prefers_covered_mode_when_rain(self):
        walk_route = self._route(walk=2.0)
        bus_route = self._route(walk=0.3)
        ctx = ScoringContext(rain_next_hour=True)
        # expose score derivation is irrelevant — only rank order matters
        score_routes([walk_route, bus_route], [
            RouteCriterionValues(walking=2.0),
            RouteCriterionValues(walking=0.3),
        ], ctx, TopsisWeights(cost=0.05, time_of_day=0.05, walking=0.7,
                              traffic_crowd=0.05, weather=0.05, availability=0.05,
                              safety=0.05, group_size=0.0))
        assert bus_route.rank == 1

    def test_single_route_is_best_match(self):
        r = self._route(fare=120.0, dur=45)
        score_routes([r], [RouteCriterionValues(cost=120.0, time_of_day=45.0)],
                     ScoringContext())
        assert r.rank == 1
        assert r.best_match

    def test_identical_routes_share_rank_one(self):
        a = self._route(fare=100.0, dur=30)
        b = self._route(fare=100.0, dur=30)
        score_routes([a, b], [
            RouteCriterionValues(cost=100.0, time_of_day=30.0),
            RouteCriterionValues(cost=100.0, time_of_day=30.0),
        ], ScoringContext())
        assert a.rank == 1 and b.rank == 1

    def test_cc_score_is_normalized(self):
        a = self._route(fare=60.0, dur=20)
        b = self._route(fare=400.0, dur=80)
        score_routes([a, b], [
            RouteCriterionValues(cost=60.0, time_of_day=20.0),
            RouteCriterionValues(cost=400.0, time_of_day=80.0),
        ], ScoringContext())
        assert 0.0 <= a.cc_score <= 1.0
        assert a.cc_score > b.cc_score

    def test_empty_routes(self):
        assert score_routes([], [], ScoringContext()) == []

    def test_weights_normalize_when_custom(self):
        # weight vector with one dominant criterion shouldn't crash and ranks
        a = self._route(fare=50.0, dur=10, walk=3.0)
        b = self._route(fare=100.0, dur=50, walk=0.2)
        score_routes([a, b], [
            RouteCriterionValues(cost=50.0, time_of_day=10.0, walking=3.0),
            RouteCriterionValues(cost=100.0, time_of_day=50.0, walking=0.2),
        ], ScoringContext(), TopsisWeights(cost=1.0, time_of_day=0.0, walking=0.0))
        assert a.rank == 1  # cheaper wins when only cost matters


# ---------------------------------------------------------------- ride pricing
class TestRidePricing:
    def test_total_is_vehicle_fare_not_per_person_times_group(self):
        prices = estimate_ride_prices(dist_km=10.0, group_size=4)
        for p in prices:
            assert abs(p.total / max(1, 4) - p.per_person) < 1e-6
            assert p.per_person < p.total

    def test_all_providers_present(self):
        prices = estimate_ride_prices(dist_km=5.0)
        assert {p.provider for p in prices} == {"Uber", "Ola", "Uber XL", "Auto", "Rapido"}
        assert all(p.source == "estimated" for p in prices)

    def test_fare_grows_with_distance(self):
        near = estimate_ride_prices(dist_km=2.0)
        far = estimate_ride_prices(dist_km=20.0)
        for n, f in zip(near, far):
            assert f.total > n.total

    def test_live_overrides_estimate(self):
        est = estimate_ride_prices(dist_km=8.0, group_size=1)
        live = [{"provider": "Uber", "price": "₹120", "duration": 15}]
        merged = merge_live_prices(live, est, 1)
        uber = next(m for m in merged if m.provider == "Uber")
        assert uber.source == "live"
        assert uber.total == 120.0
        assert any(m.provider == "Rapido" and m.source == "estimated" for m in merged)

    def test_bad_live_option_ignored(self):
        est = estimate_ride_prices(dist_km=5.0, group_size=2)
        merged = merge_live_prices([{"provider": "", "price": None}], est, 2)
        assert len(merged) == len(est)
        assert all(m.source == "estimated" for m in merged)

    def test_ride_prices_for_distance_labels(self):
        prices = ride_prices_for_distance(dist_km=7.0, group_size=2,
                                          live_options=None)
        assert all(p.source in ("live", "estimated") for p in prices)
        assert all(isinstance(p.total, float) for p in prices)

    def test_price_without_surge_components(self):
        # surge should never produce zero/negative totals
        prices = estimate_ride_prices(dist_km=0.5, group_size=1)
        assert all(p.total > 0 for p in prices)


class TestLivePriceFetch:
    def test_coord_to_str(self):
        assert coord_to_str((12.9716, 77.5946)) == "12.97160,77.59460"

    def test_fetch_live_prices_returns_none_without_client(self):
        live, km = fetch_live_prices(None, (12.97, 77.59), (13.0, 77.6))
        assert live is None and km == 0.0

    def test_fetch_live_prices_uses_real_data(self):
        class FakeSerp:
            def directions(self, origin, dest):
                return {
                    "distance_m": 5000,
                    "ride_options": [{"provider": "Uber", "price": "₹200", "duration": 12}],
                }
        live, km = fetch_live_prices(FakeSerp(), (12.97, 77.59), (13.0, 77.6))
        assert km == 5.0
        assert live == [{"provider": "Uber", "price": "₹200", "duration": 12}]

    def test_fetch_live_prices_returns_none_on_empty(self):
        class FakeSerp:
            def directions(self, origin, dest):
                return {"distance_m": 5000, "ride_options": []}
        live, km = fetch_live_prices(FakeSerp(), (12.97, 77.59), (13.0, 77.6))
        assert live is None and km == 5.0

    def test_search_service_wiring_passes_live(self):
        # ride_prices() must pass live_options (not None) into the pricing ladder
        from backend.services.search_service import SearchService
        from backend.services.clients.google_maps_client import GoogleMapsClient

        class FakeSerp:
            def directions(self, origin, dest):
                return {
                    "distance_m": 8000,
                    "ride_options": [{"provider": "Uber", "price": "₹150", "duration": 10}],
                }
        class FakeMaps(GoogleMapsClient):
            def __init__(self):
                pass
            def directions(self, origin, dest, mode="driving"):
                return {"distance_m": 8000}
        svc = SearchService(FakeMaps(), FakeSerp())
        prices = svc.ride_prices((12.97, 77.59), (13.0, 77.6), group_size=1)
        uber = next(p for p in prices if p.provider == "Uber")
        assert uber.source == "live"
        assert uber.total == 150.0
        assert any(p.source == "estimated" for p in prices)
