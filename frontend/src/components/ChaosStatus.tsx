import React, { useEffect, useState, useCallback } from 'react';
import { fetchActuatorHealth } from '../services/api';
import type { HealthStatus } from '../types';

const POLL_INTERVAL_MS = 5000;

const ChaosStatus: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus>({ status: 'CHECKING' });
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [uptime, setUptime] = useState<number>(0);
  const [checkCount, setCheckCount] = useState<number>(0);

  const checkHealth = useCallback(async () => {
    try {
      const data = await fetchActuatorHealth();
      setHealth(data);
    } catch {
      setHealth({ status: 'DOWN' });
    } finally {
      setLastChecked(new Date());
      setCheckCount((c) => c + 1);
      setUptime((u) => health.status === 'UP' ? u + POLL_INTERVAL_MS / 1000 : u);
    }
  }, [health.status]);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [checkHealth]);

  const statusColor = {
    UP: '#10b981',
    DOWN: '#ef4444',
    CHECKING: '#f59e0b',
  }[health.status];

  const statusLabel = {
    UP: '● SYSTEM OPERATIONAL',
    DOWN: '● SERVICE DOWN',
    CHECKING: '◌ CHECKING...',
  }[health.status];

  return (
    <div className="chaos-status-card">
      <div className="chaos-status-header">
        <span className="chaos-status-title">⚡ Chaos Status Monitor</span>
        <span className="chaos-status-badge" style={{ background: statusColor }}>
          {statusLabel}
        </span>
      </div>

      <div className="chaos-status-grid">
        <div className="chaos-stat">
          <span className="chaos-stat-label">MongoDB</span>
          <span
            className="chaos-stat-value"
            style={{ color: health.components?.mongo?.status === 'UP' ? '#10b981' : statusColor }}
          >
            {health.components?.mongo?.status ?? (health.status === 'CHECKING' ? '...' : health.status)}
          </span>
        </div>
        <div className="chaos-stat">
          <span className="chaos-stat-label">Health Checks</span>
          <span className="chaos-stat-value">{checkCount}</span>
        </div>
        <div className="chaos-stat">
          <span className="chaos-stat-label">Uptime (s)</span>
          <span className="chaos-stat-value">{Math.round(uptime)}</span>
        </div>
        <div className="chaos-stat">
          <span className="chaos-stat-label">Last Polled</span>
          <span className="chaos-stat-value" style={{ fontSize: '0.8rem' }}>
            {lastChecked ? lastChecked.toLocaleTimeString() : '—'}
          </span>
        </div>
      </div>

      <div className="chaos-status-footer">
        <span>Polls every {POLL_INTERVAL_MS / 1000}s via <code>/actuator/health</code></span>
        <button className="refresh-btn" onClick={checkHealth}>↺ Refresh</button>
      </div>
    </div>
  );
};

export default ChaosStatus;
