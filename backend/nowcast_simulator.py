"""
Nowcast Simulator: Simulates rainfall intensity changes over time
For demo purposes, uses realistic weather patterns
"""

import math
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def simulate_rainfall_timeline(base_intensity, hours_ahead):
    """
    Simulate rainfall evolution over 0-3 hours
    Different patterns for different weather scenarios

    Args:
        base_intensity: Initial rainfall in mm/hr
        hours_ahead: Hours to project (0-3)

    Returns:
        Adjusted rainfall intensity
    """

    # Default: slight increase as storm builds
    if base_intensity < 30:
        # Light rain - may increase
        pattern = "light_buildup"
    elif base_intensity < 60:
        # Moderate rain - relatively stable
        pattern = "moderate_steady"
    else:
        # Heavy rain - may decrease as storm passes
        pattern = "heavy_decay"

    return apply_rainfall_pattern(base_intensity, hours_ahead, pattern)

def apply_rainfall_pattern(base_intensity, hours_ahead, pattern):
    """
    Apply weather pattern transformation to rainfall
    """

    patterns = {
        'light_buildup': {
            0: 1.0,
            1: 1.15,
            2: 1.25,
            3: 1.20
        },
        'moderate_steady': {
            0: 1.0,
            1: 1.05,
            2: 1.08,
            3: 1.10
        },
        'heavy_decay': {
            0: 1.0,
            1: 0.95,
            2: 0.85,
            3: 0.70
        },
        'convective_peak': {
            0: 1.0,
            1: 1.40,
            2: 1.30,
            3: 0.50
        },
        'steady_downpour': {
            0: 1.0,
            1: 1.0,
            2: 1.0,
            3: 1.0
        }
    }

    multiplier = patterns.get(pattern, patterns['moderate_steady']).get(hours_ahead, 1.0)

    adjusted_intensity = base_intensity * multiplier

    # Add small random variation (±5%)
    random_factor = 1.0 + (math.sin(hours_ahead * 3.14159) * 0.05)

    return min(100, max(10, adjusted_intensity * random_factor))

def get_rainfall_scenario(scenario_name):
    """
    Get predefined rainfall scenarios for demo
    """
    scenarios = {
        'light_shower': {
            'base_intensity': 20,
            'duration_hours': 1,
            'pattern': 'light_buildup',
            'description': 'Light to moderate rain'
        },
        'moderate_rain': {
            'base_intensity': 50,
            'duration_hours': 2,
            'pattern': 'moderate_steady',
            'description': 'Steady moderate rainfall'
        },
        'heavy_downpour': {
            'base_intensity': 75,
            'duration_hours': 3,
            'pattern': 'heavy_decay',
            'description': 'Heavy rain, gradually decreasing'
        },
        'flash_storm': {
            'base_intensity': 90,
            'duration_hours': 2,
            'pattern': 'convective_peak',
            'description': 'Intense flash storm with rapid decay'
        },
        'continuous_rainfall': {
            'base_intensity': 40,
            'duration_hours': 6,
            'pattern': 'steady_downpour',
            'description': 'Continuous steady rainfall'
        }
    }

    return scenarios.get(scenario_name, scenarios['moderate_rain'])

def generate_rainfall_timeline(base_intensity, hours=3, interval_minutes=15):
    """
    Generate detailed rainfall timeline
    Returns timeline of (time, intensity) tuples
    """
    timeline = []

    for i in range(0, hours * 60 + 1, interval_minutes):
        hours_elapsed = i / 60.0
        adjusted_intensity = simulate_rainfall_timeline(base_intensity, hours_elapsed)

        timestamp = datetime.utcnow() + timedelta(minutes=i)
        timeline.append({
            'timestamp': timestamp.isoformat(),
            'hours_elapsed': round(hours_elapsed, 2),
            'intensity': round(adjusted_intensity, 1)
        })

    return timeline

def estimate_cumulative_rainfall(base_intensity, hours_ahead):
    """
    Calculate total rainfall accumulated over period
    Integrates intensity over time
    """
    total_rainfall = 0

    # Simpson's rule for integration
    n = 60  # Minutes
    dt = hours_ahead / n

    for i in range(n):
        t1 = hours_ahead * (i / n)
        t2 = hours_ahead * ((i + 1) / n)

        i1 = simulate_rainfall_timeline(base_intensity, t1)
        i2 = simulate_rainfall_timeline(base_intensity, t2)

        total_rainfall += (i1 + i2) / 2 * dt

    return total_rainfall

def predict_rainfall_probability(base_intensity, hours_ahead, confidence=0.85):
    """
    Estimate confidence level of rainfall prediction
    Higher confidence near present, lower for 3+ hours ahead
    """
    # Confidence decreases exponentially with time
    confidence_decay = math.exp(-0.5 * hours_ahead)

    final_confidence = confidence * confidence_decay

    return round(min(1.0, final_confidence), 2)

def detect_rainfall_trend(recent_intensities):
    """
    Analyze recent rainfall trend
    Returns: 'increasing', 'decreasing', or 'stable'
    """
    if len(recent_intensities) < 2:
        return 'unknown'

    # Simple linear regression
    n = len(recent_intensities)
    x_values = list(range(n))

    x_mean = sum(x_values) / n
    y_mean = sum(recent_intensities) / n

    numerator = sum((x_values[i] - x_mean) * (recent_intensities[i] - y_mean) for i in range(n))
    denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 'stable'

    slope = numerator / denominator

    if slope > 5:
        return 'increasing'
    elif slope < -5:
        return 'decreasing'
    else:
        return 'stable'

def get_weather_alert(base_intensity, trend):
    """
    Generate weather-based alert
    """
    alerts = {
        'light': 'Monitor situation',
        'moderate': 'Prepare for possible flooding',
        'heavy': 'High flood risk, divert traffic',
        'severe': 'CRITICAL: Close roads immediately'
    }

    if base_intensity < 30:
        level = 'light'
    elif base_intensity < 50:
        level = 'moderate'
    elif base_intensity < 75:
        level = 'heavy'
    else:
        level = 'severe'

    message = alerts[level]

    if trend == 'increasing':
        message += ' - rainfall intensifying'
    elif trend == 'decreasing':
        message += ' - conditions improving'

    return {
        'level': level,
        'message': message,
        'color': {
            'light': '#10b981',
            'moderate': '#fbbf24',
            'heavy': '#f97316',
            'severe': '#ef4444'
        }[level]
    }
