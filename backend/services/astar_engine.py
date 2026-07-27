"""A* pathfinder for transit graph — moved from ml/astar.py."""

import heapq
import math
from geopy.distance import geodesic


class AStarPathfinder:
    def __init__(self):
        self.graph = {}

    def add_edge(self, from_node: str, to_node: str, weight: float, mode: str = "walk"):
        if from_node not in self.graph:
            self.graph[from_node] = []
        if to_node not in self.graph:
            self.graph[to_node] = []
        self.graph[from_node].append((to_node, weight, mode))
        self.graph[to_node].append((from_node, weight, mode))

    def build_transit_graph(self, metro_stations: list, bus_stops: dict):
        import itertools

        for i, station in enumerate(metro_stations):
            node_id = f"metro_{station['name']}"
            self.graph.setdefault(node_id, [])

            for j, other in enumerate(metro_stations):
                if i != j and station.get("line") == other.get("line"):
                    dist = geodesic(
                        (station["lat"], station["lng"]),
                        (other["lat"], other["lng"])
                    ).km
                    self.graph.setdefault(node_id, [])
                    other_id = f"metro_{other['name']}"
                    self.graph[node_id].append((other_id, dist, "metro"))
                    self.graph[other_id].append((node_id, dist, "metro"))

        for stop_id, stop in list(bus_stops.items())[:200]:
            node_id = f"bus_{stop['name']}"
            self.graph.setdefault(node_id, [])

            for other_id, other in list(bus_stops.items())[:200]:
                if stop_id != other_id:
                    dist = geodesic(
                        (stop["lat"], stop["lng"]),
                        (other["lat"], other["lng"])
                    ).km
                    if dist < 15:
                        other_node = f"bus_{other['name']}"
                        self.graph[node_id].append((other_node, dist, "bus"))
                        self.graph[other_node].append((node_id, dist, "bus"))

        for station in metro_stations[:50]:
            metro_node = f"metro_{station['name']}"
            for stop_id, stop in list(bus_stops.items())[:200]:
                dist = geodesic(
                    (station["lat"], station["lng"]),
                    (stop["lat"], stop["lng"])
                ).km
                if dist < 1.5:
                    bus_node = f"bus_{stop['name']}"
                    self.graph[metro_node].append((bus_node, dist + 0.5, "interchange"))
                    self.graph[bus_node].append((metro_node, dist + 0.5, "interchange"))

    def heuristic(self, node_a: str, node_b: str, node_coords: dict) -> float:
        if node_a in node_coords and node_b in node_coords:
            return geodesic(node_coords[node_a], node_coords[node_b]).km
        return 0

    def find_path(self, start: str, goal: str, node_coords: dict = None) -> list:
        if start not in self.graph or goal not in self.graph:
            return []

        open_set = []
        heapq.heappush(open_set, (0, start))

        came_from = {}
        g_score = {node: float("inf") for node in self.graph}
        g_score[start] = 0

        f_score = {node: float("inf") for node in self.graph}
        f_score[start] = self.heuristic(start, goal, node_coords or {})

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()
                return path

            for neighbor, weight, mode in self.graph.get(current, []):
                tentative_g = g_score[current] + weight
                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self.heuristic(neighbor, goal, node_coords or {})
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []

    def find_path_with_modes(self, start: str, goal: str, node_coords: dict = None) -> list:
        path = self.find_path(start, goal, node_coords)
        path_with_modes = []

        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            for neighbor, weight, mode in self.graph.get(current, []):
                if neighbor == next_node:
                    path_with_modes.append({
                        "from": current,
                        "to": next_node,
                        "mode": mode,
                        "distance_km": round(weight, 2)
                    })
                    break

        return path_with_modes


astar = AStarPathfinder()
