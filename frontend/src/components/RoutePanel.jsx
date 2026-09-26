import React, { useState } from 'react';

const RoutePanel = ({ predictions, rainfallIntensity }) => {
  const [startPoint, setStartPoint] = useState('');
  const [endPoint, setEndPoint] = useState('');
  const [routeResult, setRouteResult] = useState(null);

  const handleFindRoute = async () => {
    if (!startPoint || !endPoint) {
      alert('Please enter both start and end points');
      return;
    }

    // Simulate route calculation
    // In production, would call backend API
    const floodedRoads = predictions?.roads.filter(
      (r) => r.flood_risk === 'high' || r.flood_risk === 'critical'
    ) || [];

    setRouteResult({
      startPoint,
      endPoint,
      floodedSegmentsAvoided: floodedRoads.length,
      distanceDifference: Math.random() * 2,
      timeDifference: Math.random() * 8
    });
  };

  const handleReset = () => {
    setStartPoint('');
    setEndPoint('');
    setRouteResult(null);
  };

  return (
    <div className="route-panel">
      <h3>🚗 Flood-Safe Routing</h3>

      <div className="input-group">
        <label>Start Location</label>
        <input
          type="text"
          placeholder="Enter starting point"
          value={startPoint}
          onChange={(e) => setStartPoint(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleFindRoute()}
        />
      </div>

      <div className="input-group">
        <label>End Location</label>
        <input
          type="text"
          placeholder="Enter destination"
          value={endPoint}
          onChange={(e) => setEndPoint(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleFindRoute()}
        />
      </div>

      <button
        className="predict-btn"
        onClick={handleFindRoute}
        style={{ marginBottom: '12px' }}
      >
        Find Safe Route
      </button>

      {routeResult && (
        <div style={{
          background: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: '6px',
          padding: '12px',
          fontSize: '12px'
        }}>
          <div style={{ marginBottom: '8px' }}>
            <strong style={{ color: '#15803d' }}>Route Analysis</strong>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', color: '#1e293b' }}>
            <div>
              <span style={{ color: '#64748b' }}>Flooded segments avoided:</span>
              <span style={{ float: 'right', fontWeight: 600 }}>
                {routeResult.floodedSegmentsAvoided}
              </span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Extra distance:</span>
              <span style={{ float: 'right', fontWeight: 600 }}>
                {routeResult.distanceDifference.toFixed(1)} km
              </span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Additional time:</span>
              <span style={{ float: 'right', fontWeight: 600 }}>
                {routeResult.timeDifference.toFixed(0)} min
              </span>
            </div>
          </div>

          <button
            className="predict-btn"
            onClick={handleReset}
            style={{
              marginTop: '10px',
              background: '#6b7280',
              fontSize: '12px',
              padding: '8px'
            }}
          >
            Clear Route
          </button>
        </div>
      )}

      {!routeResult && (
        <div style={{
          background: '#fef3c7',
          border: '1px solid #fcd34d',
          borderRadius: '6px',
          padding: '12px',
          fontSize: '12px',
          color: '#92400e'
        }}>
          <strong>Tip:</strong> Enter locations or click on the map to select route points. The system will avoid flooded roads.
        </div>
      )}
    </div>
  );
};

export default RoutePanel;
