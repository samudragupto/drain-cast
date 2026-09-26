"""
Terrain Processor: Handles elevation and slope analysis
Simplified DEM processing for flow direction and water accumulation
"""

import math
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

def get_flow_direction(elevation_data):
    """
    Determine water flow direction based on elevation
    Lower elevation = water flows there

    Args:
        elevation_data: Dict mapping road_id to elevation info

    Returns:
        Dict with flow graph structure
    """
    flow_graph = {}

    for road_id, data in elevation_data.items():
        elevation = data.get('avg_elevation', 10)
        flow_graph[road_id] = {
            'elevation': elevation,
            'flows_to': find_lower_adjacent(road_id, elevation, elevation_data),
            'accumulation_potential': calculate_accumulation_potential(
                data.get('slope', 0)
            )
        }

    return flow_graph

def find_lower_adjacent(road_id, current_elevation, elevation_data, max_distance=0.0015):
    """
    Find adjacent roads with lower elevation
    Water naturally flows to lower points
    """
    lower_roads = []

    for other_id, other_data in elevation_data.items():
        if other_id == road_id:
            continue

        other_elevation = other_data.get('avg_elevation', 10)
        if other_elevation < current_elevation:
            lower_roads.append({
                'target': other_id,
                'elevation_diff': current_elevation - other_elevation
            })

    # Sort by elevation difference (flows to nearest lower point first)
    lower_roads.sort(key=lambda x: x['elevation_diff'])
    return lower_roads[:2]  # Top 2 lower points

def calculate_accumulation_potential(slope):
    """
    Calculate how much water accumulates at this location
    Negative slope = depression where water accumulates
    Positive slope = elevated area water flows from
    """
    if slope < -0.02:
        return 1.4  # Strong depression
    elif slope < -0.01:
        return 1.2  # Mild depression
    elif slope < 0:
        return 1.1  # Slight depression
    elif slope == 0:
        return 1.0  # Neutral
    else:
        return 0.8  # Elevated (water drains away)

def apply_terrain_slope_factor(water_depth, slope):
    """
    Adjust water depth based on terrain slope
    """
    factor = calculate_accumulation_potential(slope)
    adjusted_depth = water_depth * factor

    # Cap adjustment (physical limits)
    return min(adjusted_depth, water_depth * 2.0)

def identify_depression_areas(elevation_data):
    """
    Find natural depression zones where water accumulates
    These areas have highest flood risk at same rainfall
    """
    depressions = []

    for road_id, data in elevation_data.items():
        slope = data.get('slope', 0)

        # Strong negative slope = depression
        if slope < -0.01:
            depressions.append({
                'road_id': road_id,
                'depression_factor': calculate_accumulation_potential(slope),
                'slope': slope,
                'elevation': data.get('avg_elevation', 0)
            })

    depressions.sort(key=lambda x: x['depression_factor'], reverse=True)
    return depressions

def calculate_flow_velocity(slope, water_depth_cm):
    """
    Estimate water velocity based on slope and depth
    Using simplified Manning's equation

    v = (1/n) * R^(2/3) * S^(1/2)
    where n=Manning's coefficient (0.04 for roads), R=hydraulic radius, S=slope
    """
    if water_depth_cm < 1:
        return 0

    manning_n = 0.04  # Asphalt/concrete
    slope_percent = abs(slope) * 100

    # Simplified: assume rectangular channel
    # Hydraulic radius ≈ depth for wide channels
    depth_m = water_depth_cm / 100

    # Avoid division by zero
    if slope == 0:
        return 0.1  # Minimal flow for flat areas

    velocity = (1 / manning_n) * (depth_m ** (2/3)) * (abs(slope) ** 0.5)
    return velocity

def calculate_travel_time(distance_m, slope, water_depth_cm):
    """
    Estimate time for water to travel distance
    Based on flow velocity
    """
    velocity = calculate_flow_velocity(slope, water_depth_cm)

    if velocity == 0:
        return float('inf')  # Water doesn't flow

    time_seconds = distance_m / velocity
    return time_seconds

def process_dem_data(dem_grid, cell_size=10):
    """
    Process Digital Elevation Model grid
    Calculate slope and aspect for each cell

    Args:
        dem_grid: 2D array of elevation values
        cell_size: Size of grid cells in meters

    Returns:
        Dict with slope and aspect for each cell
    """
    results = {}

    if not dem_grid or len(dem_grid) < 3:
        return results

    rows, cols = len(dem_grid), len(dem_grid[0]) if dem_grid else 0

    for i in range(1, rows - 1):
        for j in range(1, cols - 1):
            # Get 3x3 neighborhood
            neighbors = [
                dem_grid[i-1][j-1], dem_grid[i-1][j], dem_grid[i-1][j+1],
                dem_grid[i][j-1],                       dem_grid[i][j+1],
                dem_grid[i+1][j-1], dem_grid[i+1][j], dem_grid[i+1][j+1]
            ]

            center = dem_grid[i][j]

            # Calculate slope using Sobel operator
            x_slope = ((dem_grid[i-1][j+1] + 2*dem_grid[i][j+1] + dem_grid[i+1][j+1]) -
                      (dem_grid[i-1][j-1] + 2*dem_grid[i][j-1] + dem_grid[i+1][j-1])) / (8 * cell_size)

            y_slope = ((dem_grid[i+1][j-1] + 2*dem_grid[i+1][j] + dem_grid[i+1][j+1]) -
                      (dem_grid[i-1][j-1] + 2*dem_grid[i-1][j] + dem_grid[i-1][j+1])) / (8 * cell_size)

            slope = math.sqrt(x_slope**2 + y_slope**2)
            aspect = math.atan2(-x_slope, y_slope) * 180 / math.pi

            results[f"cell_{i}_{j}"] = {
                'elevation': center,
                'slope': slope,
                'aspect': aspect,
                'position': (i, j)
            }

    return results

def create_simplified_dem(bounds, resolution=0.001):
    """
    Create simplified DEM for demo ward
    bounds: {"north": lat, "south": lat, "east": lon, "west": lon}
    resolution: Grid resolution in degrees
    """
    dem = {}

    north, south = bounds['north'], bounds['south']
    east, west = bounds['east'], bounds['west']

    lat = south
    while lat <= north:
        lon = west
        while lon <= east:
            # Create realistic elevation pattern
            # Higher in north, lower in south/east (towards water)
            base_elevation = 10 + ((north - lat) * 100)  # Increases northward
            noise = ((lon - west) * 50) - 5  # Slight variation

            key = f"point_{lat:.4f}_{lon:.4f}"
            dem[key] = {
                'elevation': base_elevation + noise,
                'slope': -0.01 + (((north - lat) - (east - lon)) * 0.005)  # Varies
            }

            lon += resolution
        lat += resolution

    return dem

def get_slope_category(slope):
    """
    Categorize slope for analysis
    """
    if slope < -0.05:
        return "steep_depression"
    elif slope < -0.02:
        return "strong_depression"
    elif slope < -0.01:
        return "mild_depression"
    elif slope < 0:
        return "slight_depression"
    elif slope == 0:
        return "flat"
    elif slope < 0.01:
        return "slight_elevation"
    elif slope < 0.02:
        return "mild_elevation"
    else:
        return "steep_elevation"
