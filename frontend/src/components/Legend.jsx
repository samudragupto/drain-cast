import React from 'react';

const Legend = () => {
  const riskLevels = [
    { level: 'Low', range: '< 5 cm', color: '#10b981' },
    { level: 'Moderate', range: '5-15 cm', color: '#fbbf24' },
    { level: 'High', range: '15-30 cm', color: '#f97316' },
    { level: 'Critical', range: '> 30 cm', color: '#ef4444' }
  ];

  return (
    <div className="legend">
      <h4>Water Depth Legend</h4>

      {riskLevels.map((item) => (
        <div key={item.level} className="legend-item">
          <div
            className="legend-color"
            style={{ backgroundColor: item.color }}
          />
          <span>
            <strong>{item.level}</strong> — {item.range}
          </span>
        </div>
      ))}

      <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #e2e8f0' }}>
        <div className="legend-item">
          <div
            className="legend-color"
            style={{ backgroundColor: '#2563eb', borderRadius: '50%' }}
          />
          <span>Drainage Points</span>
        </div>
      </div>

      <div style={{
        marginTop: '12px',
        paddingTop: '12px',
        borderTop: '1px solid #e2e8f0',
        fontSize: '11px',
        color: '#64748b',
        lineHeight: '1.6'
      }}>
        <strong>Interpretation:</strong>
        <ul style={{ marginLeft: '16px', marginTop: '6px' }}>
          <li>Green roads are safe for traffic</li>
          <li>Yellow roads need monitoring</li>
          <li>Orange/Red roads should be avoided</li>
        </ul>
      </div>
    </div>
  );
};

export default Legend;
