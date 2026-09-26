import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const Map = ({ predictions, onRoadSelect, loading }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const roadsLayerRef = useRef(null);
  const drainsLayerRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);

  const getRiskColor = (riskLevel) => {
    const colors = {
      low: '#10b981',
      moderate: '#fbbf24',
      high: '#f97316',
      critical: '#ef4444'
    };
    return colors[riskLevel] || '#9ca3af';
  };

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = L.map(mapContainer.current).setView([19.0750, 19.0750], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map.current);

    setMapReady(true);
  }, []);

  // Update roads when predictions change
  useEffect(() => {
    if (!map.current || !mapReady || !predictions) return;

    // Clear existing layers
    if (roadsLayerRef.current) {
      map.current.removeLayer(roadsLayerRef.current);
    }
    if (drainsLayerRef.current) {
      map.current.removeLayer(drainsLayerRef.current);
    }

    // Create GeoJSON layer for roads
    const roadFeatures = predictions.roads.map((road) => ({
      type: 'Feature',
      properties: {
        id: road.id,
        name: road.name,
        flood_risk: road.flood_risk,
        water_depth: road.water_depth,
        runoff_volume: road.runoff_volume,
        drain_capacity: road.drain_capacity,
        recommendation: road.recommendation
      },
      geometry: {
        type: 'LineString',
        coordinates: road.coordinates
      }
    }));

    const roadGeoJSON = {
      type: 'FeatureCollection',
      features: roadFeatures
    };

    roadsLayerRef.current = L.geoJSON(roadGeoJSON, {
      style: (feature) => ({
        color: getRiskColor(feature.properties.flood_risk),
        weight: 5,
        opacity: 0.8,
        lineCap: 'round',
        lineJoin: 'round'
      }),
      onEachFeature: (feature, layer) => {
        const popup = L.popup().setContent(`
          <div style="font-size: 12px; width: 200px;">
            <strong>${feature.properties.name}</strong>
            <br/>Risk: <span style="color: ${getRiskColor(feature.properties.flood_risk)}; font-weight: bold;">
              ${feature.properties.flood_risk.toUpperCase()}
            </span>
            <br/>Depth: ${feature.properties.water_depth}cm
            <br/>Runoff: ${Math.round(feature.properties.runoff_volume)}L
            <br/>Drain Cap: ${Math.round(feature.properties.drain_capacity)}L
            <br/><em>${feature.properties.recommendation}</em>
          </div>
        `);

        layer.bindPopup(popup);
        layer.on('click', () => {
          onRoadSelect(feature.properties);
        });
      }
    }).addTo(map.current);

    // Add drainage nodes
    if (predictions.drainage_nodes && predictions.drainage_nodes.length > 0) {
      const drainMarkers = L.featureGroup();

      predictions.drainage_nodes.forEach((node) => {
        const marker = L.circleMarker(
          [node.location[1], node.location[0]],
          {
            radius: 6,
            fillColor: '#2563eb',
            color: '#1e40af',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
          }
        );

        marker.bindPopup(`
          <div style="font-size: 12px;">
            <strong>${node.id}</strong>
            <br/>Type: ${node.type}
            <br/>Capacity: ${node.capacity}L/s
          </div>
        `);

        drainMarkers.addLayer(marker);
      });

      drainsLayerRef.current = drainMarkers;
      drainsLayerRef.current.addTo(map.current);
    }

  }, [predictions, mapReady, onRoadSelect]);

  return (
    <div
      className="map-container"
      ref={mapContainer}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        opacity: loading ? 0.6 : 1,
        transition: 'opacity 0.2s'
      }}
    >
      {loading && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            padding: '20px 30px',
            borderRadius: '8px',
            zIndex: 1000,
            fontWeight: 500
          }}
        >
          Calculating predictions...
        </div>
      )}
    </div>
  );
};

export default Map;
