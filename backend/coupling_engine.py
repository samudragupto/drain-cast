"""
Coupling Engine: Core flood prediction logic
Couples rainfall, drainage capacity, and terrain to predict water depth
"""

import math
import logging

logger = logging.getLogger(__name__)

def calculate_flood_risk(road_id, rainfall_intensity, surface_area, timeline,
                         nearest_drain, terrain_data, drainage_graph):
    """
    Calculate flood risk for a road segment

    Args:
        road_id: Unique identifier
        rainfall_intensity: mm/hr
        surface_area: Road area in m²
        timeline: Hours ahead (0-3)
        nearest_drain: Connected drainage node ID
        terrain_data: Elevation and slope info
        drainage_graph: NetworkX graph of drainage network

    Returns:
        dict with water_depth, runoff_volume, risk_level
    """

    # Step 1: Calculate surface runoff
    # Runoff = Rainfall × Area × Impervious coefficient × Timeline factor
    impervious_coefficient = 0.85  # Urban asphalt/concrete
    timeline_factor = 1.0 + (timeline * 0.15)  # Intensity increases slightly over time

    rainfall_volume_m3 = (rainfall_intensity / 1000) * surface_area * (timeline + 1)
    runoff_volume_liters = rainfall_volume_m3 * 1000 * impervious_coefficient

    # Step 2: Get drainage capacity
    drain_capacity_lps = get_drainage_capacity(nearest_drain, drainage_graph)
    available_capacity_timeline = drain_capacity_lps * 60 * 60 * (timeline + 1)  # Convert L/s to liters

    # Step 3: Calculate excess water
    excess_water_liters = max(0, runoff_volume_liters - available_capacity_timeline)

    # Step 4: Apply terrain factor
    terrain_factor = apply_slope_factor(terrain_data.get('slope', 0))
    excess_water_liters *= terrain_factor

    # Step 5: Calculate water depth
    # Depth (cm) = excess volume (liters) / surface area (m²) × 10
    water_depth_cm = (excess_water_liters / (surface_area * 1000)) * 10 if surface_area > 0 else 0
    water_depth_cm = max(0, water_depth_cm)  # No negative depths

    # Step 6: Classify risk
    risk_level = classify_risk(water_depth_cm)

    logger.debug(f"Road {road_id}: {water_depth_cm}cm depth, {risk_level} risk")

    return {
        'water_depth': water_depth_cm,
        'runoff_volume': runoff_volume_liters,
        'drain_capacity': available_capacity_timeline,
        'risk_level': risk_level,
        'terrain_factor': terrain_factor
    }

def get_drainage_capacity(drain_id, drainage_graph):
    """
    Get available drainage capacity for a node
    In production, would calculate based on network flow
    """
    if not drain_id or drain_id not in drainage_graph.nodes():
        return 500  # Default fallback

    node_data = drainage_graph.nodes[drain_id]
    return node_data.get('capacity', 1000)

def apply_slope_factor(slope):
    """
    Apply terrain slope factor to water accumulation
    Negative slope (low area) = water accumulates more
    Positive slope (high area) = water drains faster
    """
    if slope < -0.02:  # Strong negative slope
        return 1.4  # Water accumulates significantly
    elif slope < -0.01:
        return 1.2
    elif slope < 0:
        return 1.1
    elif slope < 0.01:
        return 1.0
    else:
        return 0.8  # Positive slope helps drainage

def classify_risk(water_depth_cm):
    """
    Classify flood risk based on water depth
    Based on vehicle undercarriage heights and walkability
    """
    if water_depth_cm < 5:
        return 'low'
    elif water_depth_cm < 15:
        return 'moderate'
    elif water_depth_cm < 30:
        return 'high'
    else:
        return 'critical'

def calculate_runoff_coefficient(surface_type, slope):
    """
    Calculate runoff coefficient based on surface and terrain
    """
    base_coefficients = {
        'asphalt': 0.85,
        'concrete': 0.85,
        'paved': 0.75,
        'gravel': 0.40,
        'grass': 0.25
    }

    coeff = base_coefficients.get('asphalt', 0.75)

    # Adjust for slope
    if slope > 0.05:
        coeff *= 0.9  # Steep areas drain better
    elif slope < -0.05:
        coeff *= 1.1  # Low areas accumulate more

    return min(1.0, coeff)

def estimate_peak_depth_timeline(base_depth, rainfall_intensity, timeline):
    """
    Estimate how depth changes over timeline
    Higher rainfall → faster accumulation
    """
    if timeline == 0:
        return base_depth

    # Non-linear accumulation (more intense at beginning)
    accumulation_factor = 1.0 + (0.3 * math.log(timeline + 1))
    return base_depth * accumulation_factor

def identify_bottleneck_nodes(drainage_graph):
    """
    Identify drainage nodes that serve many roads
    These are bottleneck points likely to overflow
    """
    bottlenecks = []
    for node in drainage_graph.nodes():
        in_degree = drainage_graph.in_degree(node)
        out_degree = drainage_graph.out_degree(node)

        if in_degree > 2:  # Node receives water from multiple sources
            capacity = drainage_graph.nodes[node].get('capacity', 1000)
            load_factor = in_degree / (capacity / 500)  # Normalized load

            if load_factor > 2:
                bottlenecks.append({
                    'node_id': node,
                    'load_factor': load_factor,
                    'connected_segments': in_degree
                })

    return bottlenecks
