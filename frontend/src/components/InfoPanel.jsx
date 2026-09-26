import React from 'react';

const InfoPanel = ({ road, rainfallIntensity, timeline, onClose }) => {
  const getRiskClass = (risk) => `risk-${risk.toLowerCase().replace(' ', '-')}`;
  const getRiskLabel = (risk) => {
    const labels = {
      low: 'Low Risk',
      moderate: 'Moderate Risk',
      high: 'High Risk',
      critical: 'Critical Risk'
    };
    return labels[risk] || risk;
  };

  const getRecommendation = (risk) => {
    const recommendations = {
      low: 'No action needed. Road is safe.',
      moderate: 'Monitor this area. Possible minor flooding.',
      high: 'Avoid this route. Significant flooding expected.',
      critical: 'CLOSE immediately. Severe flooding risk.'
    };
    return recommendations[risk] || 'Unknown';
  };

  return (
    <div className="info-panel">
      <div className="info-header">
        <h4>{road.name}</h4>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="info-content">
        <div className="info-row">
          <label>Risk Level</label>
          <span>
            <div className={`risk-badge ${getRiskClass(road.flood_risk)}`}>
              {getRiskLabel(road.flood_risk)}
            </div>
          </span>
        </div>

        <div className="info-row">
          <label>Rainfall Intensity</label>
          <span>{rainfallIntensity.toFixed(1)} mm/hr</span>
        </div>

        <div className="info-row">
          <label>Water Depth (Est.)</label>
          <span style={{ color: '#ef4444', fontWeight: 700 }}>
            {road.water_depth.toFixed(1)} cm
          </span>
        </div>

        <div className="info-row">
          <label>Surface Runoff</label>
          <span>{Math.round(road.runoff_volume).toLocaleString()} L</span>
        </div>

        <div className="info-row">
          <label>Drain Capacity</label>
          <span>{Math.round(road.drain_capacity).toLocaleString()} L</span>
        </div>

        <div className="info-row">
          <label>Excess Water</label>
          <span style={{ color: road.flood_risk === 'low' ? '#10b981' : '#ef4444' }}>
            {Math.round(Math.max(0, road.runoff_volume - road.drain_capacity)).toLocaleString()} L
          </span>
        </div>

        <div style={{
          background: '#f0f9ff',
          border: '1px solid #bfdbfe',
          borderRadius: '6px',
          padding: '12px',
          marginTop: '4px',
          fontSize: '12px',
          color: '#1e40af'
        }}>
          <strong>Recommendation:</strong>
          <div style={{ marginTop: '6px' }}>
            {getRecommendation(road.flood_risk)}
          </div>
        </div>

        <div style={{
          background: '#f9fafb',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          padding: '10px',
          fontSize: '11px',
          color: '#64748b',
          marginTop: '8px'
        }}>
          <strong>Timeline:</strong> Prediction for <span style={{ fontWeight: 600, color: '#1e293b' }}>+{timeline} hours</span>
        </div>
      </div>
    </div>
  );
};

export default InfoPanel;
