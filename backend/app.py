from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import math
from coupling_engine import calculate_flood_risk
from graph_builder import build_drainage_graph, get_road_drainage_capacity
from routing import calculate_safe_route
from terrain_processor import apply_terrain_factor
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load data at startup
def load_data():
    global roads_data, drainage_nodes, drainage_edges, elevation_data
    try:
        with open('../data/roads.geojson', 'r') as f:
            roads_data = json.load(f)
        with open('../data/drainage_nodes.json', 'r') as f:
            drainage_nodes = json.load(f)
        with open('../data/drainage_edges.json', 'r') as f:
            drainage_edges = json.load(f)
        with open('../data/elevation.json', 'r') as f:
            elevation_data = json.load(f)
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Error loading data: {e}")

load_data()
drainage_graph = build_drainage_graph(drainage_nodes, drainage_edges)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

@app.route('/api/predict', methods=['POST'])
def predict():
    """
    Main prediction endpoint
    Input: rainfall_intensity (mm/hr), timeline (0-3 hours)
    Output: roads with flood predictions
    """
    try:
        data = request.json
        rainfall_intensity = data.get('rainfall_intensity', 50)
        timeline = data.get('timeline', 0)

        # Validate inputs
        rainfall_intensity = max(10, min(100, float(rainfall_intensity)))
        timeline = max(0, min(3, int(timeline)))

        predictions = []
        for feature in roads_data['features']:
            road_id = feature['properties']['id']
            road_name = feature['properties']['name']
            surface_area = feature['properties']['surface_area']
            nearest_drain = feature['properties']['nearest_drain']

            # Get elevation data for terrain factor
            terrain_data = elevation_data.get(road_id, {"avg_elevation": 10, "slope": 0})

            # Calculate flood risk
            flood_data = calculate_flood_risk(
                road_id=road_id,
                rainfall_intensity=rainfall_intensity,
                surface_area=surface_area,
                timeline=timeline,
                nearest_drain=nearest_drain,
                terrain_data=terrain_data,
                drainage_graph=drainage_graph
            )

            predictions.append({
                "id": road_id,
                "name": road_name,
                "coordinates": feature['geometry']['coordinates'],
                "flood_risk": flood_data['risk_level'],
                "water_depth": round(flood_data['water_depth'], 1),
                "runoff_volume": round(flood_data['runoff_volume'], 0),
                "drain_capacity": round(flood_data['drain_capacity'], 0),
                "risk_color": get_risk_color(flood_data['risk_level']),
                "recommendation": get_recommendation(flood_data['risk_level'])
            })

        return jsonify({
            "roads": predictions,
            "drainage_nodes": format_drainage_nodes(),
            "timestamp": datetime.utcnow().isoformat(),
            "rainfall_intensity": rainfall_intensity,
            "timeline_hours": timeline
        }), 200

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/api/route', methods=['POST'])
def route():
    """
    Calculate flood-safe routing
    """
    try:
        data = request.json
        start = tuple(data.get('start'))
        end = tuple(data.get('end'))
        flood_data = data.get('current_flood_data', [])

        flooded_roads = [r['id'] for r in flood_data if r['flood_risk'] in ['high', 'critical']]

        # Simple pathfinding (would use real routing engine in production)
        safe_route = calculate_safe_route(start, end, flooded_roads, roads_data)

        return jsonify({
            "normal_route": safe_route['normal'],
            "safe_route": safe_route['safe'],
            "avoided_roads": flooded_roads,
            "distance_saved": round(safe_route.get('distance_difference', 0), 2),
            "time_added": round(safe_route.get('time_difference', 0), 1)
        }), 200

    except Exception as e:
        logger.error(f"Routing error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/api/ward-info', methods=['GET'])
def ward_info():
    """
    Ward statistics and metadata
    """
    try:
        total_roads = len(roads_data['features'])
        total_drain_capacity = sum(n['capacity'] for n in drainage_nodes)

        return jsonify({
            "ward_name": "Kurla East",
            "total_roads": total_roads,
            "total_drainage_nodes": len(drainage_nodes),
            "total_drain_capacity": total_drain_capacity,
            "coverage_percentage": 85.5,
            "bounds": {
                "north": 19.0850,
                "south": 19.0650,
                "east": 72.8900,
                "west": 72.8650
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def get_risk_color(risk_level):
    colors = {
        'low': '#10b981',
        'moderate': '#fbbf24',
        'high': '#f97316',
        'critical': '#ef4444'
    }
    return colors.get(risk_level, '#9ca3af')

def get_recommendation(risk_level):
    recommendations = {
        'low': 'No action needed',
        'moderate': 'Monitor this area',
        'high': 'Avoid this route',
        'critical': 'Immediate closure recommended'
    }
    return recommendations.get(risk_level, 'Unknown')

def format_drainage_nodes():
    return [
        {
            "id": node['id'],
            "location": node['location'],
            "capacity": node['capacity'],
            "type": node['type']
        }
        for node in drainage_nodes
    ]

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
