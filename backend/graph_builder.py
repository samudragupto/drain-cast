"""
Graph Builder: Constructs and analyzes drainage network
Uses NetworkX for directed graph representation
"""

import networkx as nx
import math
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

def build_drainage_graph(nodes_json, edges_json):
    """
    Build directed graph of drainage network

    Nodes: Drainage points (manholes, inlets)
    Edges: Pipes connecting nodes with capacity weights

    Args:
        nodes_json: List of drainage node dictionaries
        edges_json: List of pipe edge dictionaries

    Returns:
        NetworkX DiGraph with node/edge attributes
    """
    G = nx.DiGraph()

    # Add nodes with attributes
    for node in nodes_json:
        G.add_node(
            node['id'],
            location=tuple(node['location']),
            elevation=node.get('elevation', 10),
            capacity=node.get('capacity', 1000),
            node_type=node.get('type', 'manhole')
        )

    # Add edges with attributes
    for edge in edges_json:
        G.add_edge(
            edge['from'],
            edge['to'],
            capacity=edge.get('capacity', 1000),
            diameter=edge.get('pipe_diameter', 600),
            length=edge.get('length', 100),
            weight=1 / edge.get('capacity', 1000)  # Lower capacity = higher weight (resistance)
        )

    logger.info(f"Built drainage graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G

def get_road_drainage_capacity(road_id, drainage_graph, road_location):
    """
    Find drainage capacity for a road
    Returns capacity of connected drainage network

    Args:
        road_id: Road identifier
        drainage_graph: NetworkX DiGraph
        road_location: [lat, lon] of road

    Returns:
        Available capacity in L/s
    """
    if not drainage_graph.number_of_nodes():
        return 500

    # Find nearest drainage node to road
    nearest_node = find_nearest_node(road_location, drainage_graph)

    if not nearest_node:
        return 500

    # Get node capacity
    node_capacity = drainage_graph.nodes[nearest_node].get('capacity', 1000)

    # Check downstream capacity (bottleneck analysis)
    downstream_capacity = analyze_downstream_capacity(nearest_node, drainage_graph)

    # Use minimum of node and downstream capacity
    return min(node_capacity, downstream_capacity)

def find_nearest_node(location, drainage_graph):
    """
    Find nearest drainage node to a location
    Location: [lat, lon]
    """
    if not drainage_graph.number_of_nodes():
        return None

    min_distance = float('inf')
    nearest_id = None

    for node_id in drainage_graph.nodes():
        node_location = drainage_graph.nodes[node_id].get('location')
        if node_location:
            distance = haversine_distance(location, node_location)
            if distance < min_distance:
                min_distance = distance
                nearest_id = node_id

    return nearest_id if min_distance < 1.0 else None  # Within ~1km

def haversine_distance(loc1, loc2):
    """
    Calculate distance between two lat/lon points in km
    """
    lat1, lon1 = loc1
    lat2, lon2 = loc2

    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def analyze_downstream_capacity(start_node, drainage_graph, max_depth=5):
    """
    Analyze bottlenecks in drainage network downstream
    Find minimum capacity in outflow paths

    Args:
        start_node: Starting node ID
        drainage_graph: NetworkX DiGraph
        max_depth: Maximum path depth to analyze

    Returns:
        Minimum bottleneck capacity in L/s
    """
    if start_node not in drainage_graph:
        return 500

    min_capacity = float('inf')

    # BFS to find all downstream paths
    visited = set()
    queue = [(start_node, 0)]

    while queue:
        node, depth = queue.pop(0)

        if node in visited or depth > max_depth:
            continue

        visited.add(node)
        node_capacity = drainage_graph.nodes[node].get('capacity', 1000)
        min_capacity = min(min_capacity, node_capacity)

        # Explore successors
        for successor in drainage_graph.successors(node):
            if successor not in visited:
                queue.append((successor, depth + 1))

    return min_capacity if min_capacity != float('inf') else 500

def identify_bottleneck_nodes(drainage_graph):
    """
    Identify critical bottleneck nodes in drainage network
    Nodes with high in-degree and low capacity
    """
    bottlenecks = []

    for node in drainage_graph.nodes():
        in_degree = drainage_graph.in_degree(node)
        capacity = drainage_graph.nodes[node].get('capacity', 1000)

        # Node is critical if it receives water from multiple sources
        if in_degree >= 2:
            stress_factor = in_degree / (capacity / 500)

            if stress_factor > 2.0:
                bottlenecks.append({
                    'node_id': node,
                    'stress_factor': round(stress_factor, 2),
                    'in_degree': in_degree,
                    'capacity': capacity
                })

    bottlenecks.sort(key=lambda x: x['stress_factor'], reverse=True)
    return bottlenecks

def calculate_network_flow(drainage_graph, source_node, target_node):
    """
    Calculate maximum flow through drainage network
    Uses min-cost max-flow algorithm
    """
    if source_node not in drainage_graph or target_node not in drainage_graph:
        return 0

    try:
        # SimpleMaxFlow finds maximum flow through network
        flow_value = nx.maximum_flow_value(
            drainage_graph,
            source_node,
            target_node,
            capacity='capacity'
        )
        return flow_value
    except nx.NetworkXError:
        return 0

def find_overflow_path(drainage_graph, start_node):
    """
    Find path water would take if primary drain overflows
    Based on elevation and pipe capacity
    """
    if start_node not in drainage_graph:
        return []

    # Dijkstra's algorithm to find path with minimum resistance
    try:
        path = nx.dijkstra_path(
            drainage_graph,
            source=start_node,
            target=None,
            weight='weight'
        )
        return path[:3] if path else []  # Return first 3 hops
    except nx.NetworkXError:
        return []

def get_network_statistics(drainage_graph):
    """
    Get overall network health statistics
    """
    if not drainage_graph.number_of_nodes():
        return {}

    total_capacity = sum(
        drainage_graph.nodes[n].get('capacity', 0)
        for n in drainage_graph.nodes()
    )

    avg_capacity = total_capacity / drainage_graph.number_of_nodes()

    bottlenecks = identify_bottleneck_nodes(drainage_graph)

    return {
        'total_nodes': drainage_graph.number_of_nodes(),
        'total_edges': drainage_graph.number_of_edges(),
        'total_capacity': total_capacity,
        'average_capacity': round(avg_capacity, 0),
        'bottleneck_count': len(bottlenecks),
        'network_redundancy': calculate_redundancy(drainage_graph)
    }

def calculate_redundancy(drainage_graph):
    """
    Measure network redundancy (alternative paths if one node fails)
    Based on edge connectivity
    """
    if drainage_graph.number_of_nodes() < 2:
        return 0

    # Try removing each node and see if network stays connected
    # More resilient networks maintain connectivity
    try:
        connectivity = nx.node_connectivity(drainage_graph)
        return min(connectivity, 3)  # Cap at 3 for simplicity
    except:
        return 1
