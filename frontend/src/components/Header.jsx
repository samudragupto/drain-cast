import React, { useState } from 'react';

const Header = ({ wardInfo }) => {
  const [selectedWard, setSelectedWard] = useState('kurla-east');

  const wards = [
    { id: 'kurla-east', name: 'Kurla East' },
    { id: 'kurla-west', name: 'Kurla West' },
    { id: 'ghatkopar', name: 'Ghatkopar' },
    { id: 'powai', name: 'Powai' }
  ];

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-title">
          <h1>🌊 DrainCast</h1>
          <p>Urban Flood Nowcasting System</p>
        </div>

        {wardInfo && (
          <div className="header-stats">
            <div className="stat-item">
              <div className="stat-value">{wardInfo.total_roads}</div>
              <div className="stat-label">Roads</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{wardInfo.total_drainage_nodes}</div>
              <div className="stat-label">Drains</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{wardInfo.coverage_percentage}%</div>
              <div className="stat-label">Coverage</div>
            </div>
          </div>
        )}
      </div>

      <div className="header-actions">
        <select
          className="ward-select"
          value={selectedWard}
          onChange={(e) => setSelectedWard(e.target.value)}
        >
          {wards.map((ward) => (
            <option key={ward.id} value={ward.id}>
              {ward.name}
            </option>
          ))}
        </select>

        <a
          href="https://github.com/yourusername/draincast"
          target="_blank"
          rel="noopener noreferrer"
          className="icon-link"
          title="GitHub Repository"
        >
          ⧉
        </a>
      </div>
    </header>
  );
};

export default Header;
