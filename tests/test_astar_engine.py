"""Unit tests for astar_engine.py — A* pathfinder on small hand-crafted graphs."""

import pytest
from backend.services.astar_engine import AStarPathfinder


class TestAStarPathfinder:
    def setup_method(self):
        self.pf = AStarPathfinder()

    def test_empty_graph(self):
        path = self.pf.find_path("A", "B")
        assert path == []

    def test_single_edge(self):
        self.pf.graph = {"A": [("B", 1.0, "walk")], "B": [("A", 1.0, "walk")]}
        path = self.pf.find_path("A", "B")
        assert path == ["A", "B"]

    def test_no_path_returns_empty(self):
        self.pf.graph = {"A": [("C", 1.0, "walk")], "C": [("A", 1.0, "walk")], "B": []}
        path = self.pf.find_path("A", "B")
        assert path == []

    def test_multi_step_path(self):
        self.pf.graph = {
            "A": [("B", 1.0, "walk"), ("C", 5.0, "walk")],
            "B": [("A", 1.0, "walk"), ("C", 2.0, "walk")],
            "C": [("A", 5.0, "walk"), ("B", 2.0, "walk"), ("D", 1.0, "walk")],
            "D": [("C", 1.0, "walk")],
        }
        path = self.pf.find_path("A", "D", {"A": (0, 0), "B": (0.01, 0), "C": (0.02, 0), "D": (0.03, 0)})
        assert path == ["A", "B", "C", "D"]

    def test_heuristic_with_coords(self):
        self.pf.graph = {"A": [("B", 100, "walk")], "B": [("A", 100, "walk")]}
        coords = {"A": (0, 0), "B": (1, 1)}
        h = self.pf.heuristic("A", "B", coords)
        assert h > 0
        assert h < 200  # geopy km between (0,0) and (1,1)
        assert isinstance(h, float)

    def test_heuristic_missing_coords(self):
        h = self.pf.heuristic("A", "B", {})
        assert h == 0

    def test_add_edge(self):
        self.pf.add_edge("X", "Y", 2.5, "metro")
        assert "X" in self.pf.graph
        assert "Y" in self.pf.graph
        assert ("Y", 2.5, "metro") in self.pf.graph["X"]
        assert ("X", 2.5, "metro") in self.pf.graph["Y"]

    def test_find_path_with_modes(self):
        self.pf.graph = {
            "A": [("B", 1.0, "walk"), ("C", 5.0, "walk")],
            "B": [("A", 1.0, "walk"), ("C", 2.0, "bus")],
            "C": [("A", 5.0, "walk"), ("B", 2.0, "bus")],
        }
        modes = self.pf.find_path_with_modes("A", "C", {"A": (0, 0), "B": (0.01, 0), "C": (0.02, 0)})
        assert len(modes) == 2
        assert modes[0]["mode"] == "walk"
        assert modes[1]["mode"] == "bus"
        assert modes[0]["from"] == "A"
        assert modes[1]["to"] == "C"

    def test_find_path_with_modes_no_path(self):
        self.pf.graph = {"A": [], "B": []}
        modes = self.pf.find_path_with_modes("A", "B")
        assert modes == []

    def test_start_not_in_graph(self):
        self.pf.graph = {"B": []}
        path = self.pf.find_path("A", "B")
        assert path == []

    def test_goal_not_in_graph(self):
        self.pf.graph = {"A": []}
        path = self.pf.find_path("A", "B")
        assert path == []

    def test_shortest_path_chosen(self):
        # Two paths: A->B->D (shorter) vs A->C->D (longer)
        self.pf.graph = {
            "A": [("B", 1, "walk"), ("C", 10, "walk")],
            "B": [("A", 1, "walk"), ("D", 1, "walk")],
            "C": [("A", 10, "walk"), ("D", 10, "walk")],
            "D": [("B", 1, "walk"), ("C", 10, "walk")],
        }
        path = self.pf.find_path("A", "D", {"A": (0, 0), "B": (0, 1), "C": (1, 0), "D": (0, 2)})
        assert path == ["A", "B", "D"]
