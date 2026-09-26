import React from 'react';

const ControlPanel = ({
  rainfallIntensity,
  timeline,
  onRainfallChange,
  onTimelineChange,
  onPredict,
  loading
}) => {
  const handleRainfallChange = (e) => {
    onRainfallChange(parseFloat(e.target.value));
  };

  return (
    <div className="control-panel">
      <h3>Simulation Controls</h3>

      <div className="rainfall-control">
        <div className="rainfall-value">
          <label>Rainfall Intensity</label>
          <span>{rainfallIntensity.toFixed(1)} mm/hr</span>
        </div>
        <input
          type="range"
          min="10"
          max="100"
          value={rainfallIntensity}
          onChange={handleRainfallChange}
          disabled={loading}
        />
        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
          Light ← → Heavy
        </div>
      </div>

      <div>
        <label style={{ fontSize: '12px', color: '#64748b', fontWeight: 500, marginBottom: '8px', display: 'block' }}>
          Prediction Timeline
        </label>
        <div className="timeline-buttons">
          {[0, 1, 2, 3].map((hour) => (
            <button
              key={hour}
              className={`timeline-btn ${timeline === hour ? 'active' : ''}`}
              onClick={() => onTimelineChange(hour)}
              disabled={loading}
            >
              {hour === 0 ? 'Now' : `+${hour}h`}
            </button>
          ))}
        </div>
      </div>

      <button
        className="predict-btn"
        onClick={onPredict}
        disabled={loading}
        style={{ marginTop: '12px' }}
      >
        {loading ? 'Calculating...' : 'Recalculate'}
      </button>

      {/* Quick Info */}
      <div style={{ marginTop: '16px', padding: '12px', background: '#f8fafc', borderRadius: '6px', fontSize: '12px' }}>
        <div style={{ color: '#64748b', marginBottom: '4px' }}>
          <strong>Intensity Level:</strong>
        </div>
        <div style={{ color: '#1e293b', fontSize: '13px', fontWeight: 500 }}>
          {rainfallIntensity < 30 && 'Light Shower'}
          {rainfallIntensity >= 30 && rainfallIntensity < 60 && 'Moderate Rain'}
          {rainfallIntensity >= 60 && 'Heavy Downpour'}
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
