import React, { useState, useCallback, useEffect } from 'react';
import './App.css';
import Map from './components/Map';
import ControlPanel from './components/ControlPanel';
import InfoPanel from './components/InfoPanel';
import RoutePanel from './components/RoutePanel';
import Legend from './components/Legend';
import Header from './components/Header';
import { fetchPredictions, fetchWardInfo } from './utils/api';

function App() {
  const [rainfallIntensity, setRainfallIntensity] = useState(50);
  const [timeline, setTimeline] = useState(0);
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedRoad, setSelectedRoad] = useState(null);
  const [showRouting, setShowRouting] = useState(false);
  const [wardInfo, setWardInfo] = useState(null);
  const [error, setError] = useState(null);

  // Fetch predictions when rainfall or timeline changes
  const handlePredict = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPredictions(rainfallIntensity, timeline);
      setPredictions(data);
    } catch (err) {
      setError('Failed to fetch predictions. Please try again.');
      console.error('Prediction error:', err);
    } finally {
      setLoading(false);
    }
  }, [rainfallIntensity, timeline]);

  // Fetch ward info on mount
  useEffect(() => {
    const loadWardInfo = async () => {
      try {
        const info = await fetchWardInfo();
        setWardInfo(info);
      } catch (err) {
        console.error('Failed to load ward info:', err);
      }
    };
    loadWardInfo();
  }, []);

  // Initial prediction load
  useEffect(() => {
    handlePredict();
  }, []);

  const handleRainfallChange = (value) => {
    setRainfallIntensity(value);
  };

  const handleTimelineChange = (hours) => {
    setTimeline(hours);
  };

  const handleRoadSelect = (road) => {
    setSelectedRoad(road);
  };

  const handleCloseInfo = () => {
    setSelectedRoad(null);
  };

  return (
    <div className="app-container">
      <Header wardInfo={wardInfo} />

      <div className="main-content">
        <Map
          predictions={predictions}
          onRoadSelect={handleRoadSelect}
          loading={loading}
        />

        <div className="sidebar">
          <ControlPanel
            rainfallIntensity={rainfallIntensity}
            timeline={timeline}
            onRainfallChange={handleRainfallChange}
            onTimelineChange={handleTimelineChange}
            onPredict={handlePredict}
            loading={loading}
          />

          {selectedRoad && (
            <InfoPanel
              road={selectedRoad}
              rainfallIntensity={rainfallIntensity}
              timeline={timeline}
              onClose={handleCloseInfo}
            />
          )}

          {!selectedRoad && (
            <RoutePanel
              predictions={predictions}
              rainfallIntensity={rainfallIntensity}
            />
          )}

          <Legend />
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <p>{error}</p>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

export default App;
