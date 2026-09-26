export const riskColors = {
  low: '#10b981',
  moderate: '#fbbf24',
  high: '#f97316',
  critical: '#ef4444'
};

export const getRiskColor = (riskLevel) => {
  return riskColors[riskLevel] || '#9ca3af';
};

export const getRiskLabel = (riskLevel) => {
  const labels = {
    low: 'Low Risk',
    moderate: 'Moderate Risk',
    high: 'High Risk',
    critical: 'Critical Risk'
  };
  return labels[riskLevel] || 'Unknown';
};

export const roadStyle = (riskLevel) => ({
  color: getRiskColor(riskLevel),
  weight: 5,
  opacity: 0.8,
  lineCap: 'round',
  lineJoin: 'round'
});

export const getRiskBgColor = (riskLevel) => {
  const bgColors = {
    low: '#d1fae5',
    moderate: '#fef3c7',
    high: '#fed7aa',
    critical: '#fee2e2'
  };
  return bgColors[riskLevel] || '#f3f4f6';
};

export const getRiskTextColor = (riskLevel) => {
  const textColors = {
    low: '#065f46',
    moderate: '#92400e',
    high: '#92400e',
    critical: '#7f1d1d'
  };
  return textColors[riskLevel] || '#374151';
};

export const depthRange = {
  low: { min: 0, max: 5 },
  moderate: { min: 5, max: 15 },
  high: { min: 15, max: 30 },
  critical: { min: 30, max: Infinity }
};

export const getRiskFromDepth = (depth) => {
  if (depth < 5) return 'low';
  if (depth < 15) return 'moderate';
  if (depth < 30) return 'high';
  return 'critical';
};
