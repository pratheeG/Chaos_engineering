import React from 'react';
import { Toaster } from 'react-hot-toast';
import ChaosStatus from './components/ChaosStatus';
import ProductList from './components/ProductList';
import './index.css';

const App: React.FC = () => {
  return (
    <div className="app">
      <Toaster position="top-right" toastOptions={{ duration: 3000 }} />

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-brand">
            <span className="header-logo">⚡</span>
            <div>
              <h1 className="header-title">Chaos Engineering POC</h1>
              <p className="header-subtitle">Spring Boot · MongoDB · LitmusChaos</p>
            </div>
          </div>
          <div className="header-badges">
            <span className="tech-badge spring">Spring Boot 3.2</span>
            <span className="tech-badge mongo">MongoDB</span>
            <span className="tech-badge react">React + TS</span>
            <span className="tech-badge litmus">LitmusChaos</span>
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────── */}
      <main className="app-main">
        {/* Chaos Status Monitor */}
        <section className="app-section">
          <h2 className="section-title">
            <span className="section-icon">🩺</span> Service Health
          </h2>
          <ChaosStatus />
        </section>

        {/* Divider */}
        <div className="section-divider" />

        {/* Product Catalog */}
        <section className="app-section">
          <h2 className="section-title">
            <span className="section-icon">🛍️</span> Product Catalog
            <span className="section-subtitle">— Target service for chaos experiments</span>
          </h2>
          <ProductList />
        </section>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="app-footer">
        <p>
          Built for LitmusChaos experiments · Endpoints: <code>/api/products</code> ·{' '}
          <code>/actuator/health</code> · <code>/actuator/metrics</code>
        </p>
      </footer>
    </div>
  );
};

export default App;
