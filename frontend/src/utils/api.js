import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

export const fetchPredictions = async (rainfallIntensity, timeline) => {
  try {
    const response = await apiClient.post('/predict', {
      rainfall_intensity: rainfallIntensity,
      timeline: timeline
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching predictions:', error);
    throw error;
  }
};

export const fetchRoute = async (start, end, floodData) => {
  try {
    const response = await apiClient.post('/route', {
      start,
      end,
      current_flood_data: floodData
    });
    return response.data;
  } catch (error) {
    console.error('Error calculating route:', error);
    throw error;
  }
};

export const fetchWardInfo = async () => {
  try {
    const response = await apiClient.get('/ward-info');
    return response.data;
  } catch (error) {
    console.error('Error fetching ward info:', error);
    throw error;
  }
};

export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/health');
    return response.data;
  } catch (error) {
    console.error('Error checking health:', error);
    throw error;
  }
};

export default apiClient;
