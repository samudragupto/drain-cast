"""
Routing: Calculate flood-safe paths through road network
"""

import math
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

def calculate_safe_route(start: Tuple, end: Tuple, flooded_roads: List[str], roads_data: Dict):
    """
    Find safest route avoiding flooded roads

    Args:
        start: (lat, lon) of origin
        end: (lat, lon) of destination
        flooded_roads: List of road IDs to avoid
        roads_data: GeoJSON FeatureCollection of all roads

    Returns:
        Dict with normal_route and safe_route
    """

    # Build simple road network graph
    network = build_road_network(roads_data)

    # Find normal route (shortest distance ignoring floods)
    normal_route = find_shortest_path(start, end, network, [], roads_data)

    # Find safe route (avoiding flooded roads)
    safe_route = find_shortest_path(start, end, network, flooded_roads, roads_data)

    # Calculate metrics
    normal_distance = calculate_route_distance(normal_route)
    safe_distance = calculate_route_distance(safe_route)

    flooded_segments = count_flooded_segments(normal_route, flooded_roads)

    return {
        'normal': normal_route,
        'safe': safe_route,
        'distance_difference': safe_distance - normal_distance,
        'time_difference': (safe_distance - normal_distance) / 40 * 60,  # 40 km/h average
        'flooded_avoided': flooded_segments
    }

def build_road_network(roads_data):
    """
    Convert GeoJSON roads to network graph
    Returns adjacency info for pathfinding
    """
    network = {}
    features = roads_data.get('features', [])

    for feature in features:
        road_id = feature['properties']['id']
        coords = feature['geometry']['coordinates']

        network[road_id] = {
            'coordinates': coords,
            'start': tuple(coords[0]),
            'end': tuple(coords[-1]),
            'distance': calculate_line_distance(coords),
            'name': feature['properties'].get('name', 'Unknown Road')
        }

    return network

def find_shortest_path(start: Tuple, end: Tuple, network: Dict,
                      avoid_roads: List[str], roads_data: Dict):
    """
    Dijkstra's algorithm for shortest path
    Weights by distance, heavy penalty for flooded roads
    """

    # Find closest road to start and end points
    start_road = find_nearest_road(start, network)
    end_road = find_nearest_road(end, network)

    if not start_road or not end_road:
        # Fallback: direct line
        return [{'type': 'LineString', 'coordinates': [start, end]}]

    # BFS with Dijkstra weights
    visited = set()
    distances = {start_road: 0}
    previous = {start_road: None}
    priority_queue = [(0, start_road)]

    while priority_queue:
        current_distance, current_road = min(priority_queue, key=lambda x: x[0])
        priority_queue.remove((current_distance, current_road))

        if current_road in visited:
            continue

        visited.add(current_road)

        if current_road == end_road:
            break

        # Find adjacent roads (share endpoints or are close)
        for next_road in find_adjacent_roads(current_road, network):
            if next_road in visited:
                continue

            # Calculate edge weight
            road_distance = network[next_road]['distance']

            # Apply heavy penalty if flooded
            if next_road in avoid_roads:
                weight = road_distance * 10  # 10x penalty for flooded roads
            else:
                weight = road_distance

            new_distance = current_distance + weight

            if next_road not in distances or new_distance < distances[next_road]:
                distances[next_road] = new_distance
                previous[next_road] = current_road
                priority_queue.append((new_distance, next_road))

    # Reconstruct path
    path = []
    current = end_road

    while current:
        road = network.get(current)
        if road:
            path.insert(0, road['coordinates'])
        current = previous.get(current)

    return path

def find_nearest_road(point: Tuple, network: Dict):
    """
    Find closest road to a point
    Returns road ID
    """
    min_distance = float('inf')
    nearest_road = None

    for road_id, road_data in network.items():
        # Check distance to both endpoints
        for endpoint in [road_data['start'], road_data['end']]:
            distance = haversine_distance(point, endpoint)
            if distance < min_distance:
                min_distance = distance
                nearest_road = road_id

    return nearest_road if min_distance < 0.02 else None  # Within ~2km

def find_adjacent_roads(road_id: str, network: Dict):
    """
    Find roads that connect to this one
    """
    road = network.get(road_id)
    if not road:
        return []

    adjacent = []
    road_end = road['end']

    for other_id, other_data in network.items():
        if other_id == road_id:
            continue

        # Check if this road starts where other ends
        if other_data['start'] == road_end or other_data['end'] == road_end:
            adjacent.append(other_id)

    return adjacent

def haversine_distance(point1: Tuple, point2: Tuple) -> float:
    """
    Distance between two lat/lon points in km
    """
    lat1, lon1 = point1
    lat2, lon2 = point2

    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def calculate_line_distance(coordinates: List[Tuple]) -> float:
    """
    Calculate total distance of polyline
    """
    distance = 0
    for i in range(len(coordinates) - 1):
        distance += haversine_distance(
            (coordinates[i][1], coordinates[i][0]),  # Swap to lat/lon
            (coordinates[i+1][1], coordinates[i+1][0])
        )
    return distance

def calculate_route_distance(route: List) -> float:
    """
    Calculate total distance of entire route
    """
    total = 0
    for segment in route:
        if isinstance(segment, list):
            total += calculate_line_distance(segment)
        elif isinstance(segment, dict) and 'coordinates' in segment:
            total += calculate_line_distance(segment['coordinates'])
    return total

def count_flooded_segments(route: List, flooded_roads: List[str]) -> int:
    """
    Count how many flooded road segments are in route
    """
    # Simple counting - in production would link route back to road IDs
    return 0

def get_travel_time(distance_km: float, conditions: str = "normal") -> float:
    """
    Estimate travel time in minutes
    Accounts for traffic conditions
    """
    speeds = {
        'normal': 40,      # km/h
        'congested': 20,
        'light': 50,
        'flooded': 10      # Very slow in flood zones
    }

    speed = speeds.get(conditions, 40)
    time_hours = distance_km / speed
    return time_hours * 60

def format_route_for_display(route_coordinates: List[List]) -> Dict:
    """
    Format route for frontend display
    """
    return {
        'type': 'LineString',
        'coordinates': route_coordinates,
        'properties': {
            'distance': calculate_line_distance(route_coordinates),
            'travel_time': get_travel_time(calculate_line_distance(route_coordinates))
        }
    }
