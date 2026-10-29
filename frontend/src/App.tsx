import React, { useState, useEffect } from 'react';
import { ConceptSummary, EvaluationData, ValidationData } from './types';
import { fetchConcepts, fetchEvaluation, fetchValidation, runPipeline } from './api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'concepts' | 'validation' | 'benchmark'>('overview');
  const [concepts, setConcepts] = useState<ConceptSummary[]>([]);
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [validation, setValidation] = useState<ValidationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');

  const loadData = async () => {
    try {
      const [c, e, v] = await Promise.all([
        fetchConcepts().catch(() => []),
        fetchEvaluation().catch(() => null),
        fetchValidation().catch(() => null),
      ]);
      setConcepts(c);
      setEvaluation(e);
      setValidation(v);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await runPipeline('.', './output', false);
      await loadData();
    } catch (err) {
      alert(`Pipeline error: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const filteredConcepts = concepts.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase()) ||
    c.tags.some((t) => t.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div>
      <header>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <div style={{ width: 34, height: 34, background: '#06b6d4', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>K</div>
          <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>KnowledgeSmith AI</span>
        </div>
      </header>

      <div className="tabs-nav">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>
        <button className={`tab-btn ${activeTab === 'concepts' ? 'active' : ''}`} onClick={() => setActiveTab('concepts')}>Concepts</button>
        <button className={`tab-btn ${activeTab === 'validation' ? 'active' : ''}`} onClick={() => setActiveTab('validation')}>Validation</button>
        <button className={`tab-btn ${activeTab === 'benchmark' ? 'active' : ''}`} onClick={() => setActiveTab('benchmark')}>Benchmark</button>
      </div>

      <main>
        {activeTab === 'overview' && (
          <div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Concepts</div>
                <div className="stat-value">{evaluation?.metrics.total_concepts || 0}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Claims</div>
                <div className="stat-value">{evaluation?.metrics.total_claims || 0}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Relationships</div>
                <div className="stat-value">{evaluation?.metrics.total_relationships || 0}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Health Score</div>
                <div className="stat-value">{evaluation?.metrics.composite_health_score || 0}%</div>
              </div>
            </div>

            <form onSubmit={handleRun} style={{ background: 'var(--bg-surface)', padding: '1.5rem', borderRadius: 12 }}>
              <h3>Trigger Knowledge Pipeline</h3>
              <button
                type="submit"
                disabled={loading}
                style={{ marginTop: '1rem', padding: '0.6rem 1.2rem', background: '#06b6d4', border: 'none', color: '#fff', borderRadius: 6, fontWeight: 600, cursor: 'pointer' }}
              >
                {loading ? 'Running Pipeline...' : 'Run Pipeline'}
              </button>
            </form>
          </div>
        )}

        {activeTab === 'concepts' && (
          <div>
            <input
              type="text"
              placeholder="Search concepts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: '100%', padding: '0.6rem 1rem', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: '#fff', marginBottom: '1.5rem' }}
            />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
              {filteredConcepts.map((c) => (
                <div key={c.concept_id} style={{ background: 'var(--bg-card)', padding: '1.25rem', borderRadius: 12, border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong>{c.title}</strong>
                    <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', background: '#3b82f6', borderRadius: 4 }}>{c.concept_type}</span>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{c.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'validation' && (
          <div style={{ background: 'var(--bg-surface)', padding: '1.5rem', borderRadius: 12 }}>
            <h3>Validation Report: {validation?.is_valid ? '✅ Valid' : `❌ ${validation?.error_count} Errors`}</h3>
            <ul>
              {validation?.issues.map((i, idx) => (
                <li key={idx} style={{ marginTop: '0.5rem' }}>[{i.severity.toUpperCase()}] {i.code}: {i.message}</li>
              ))}
            </ul>
          </div>
        )}

        {activeTab === 'benchmark' && (
          <div style={{ background: 'var(--bg-surface)', padding: '1.5rem', borderRadius: 12 }}>
            <h3>Grade: {evaluation?.benchmark.letter_grade} ({evaluation?.benchmark.overall_score}%)</h3>
            <p>{evaluation?.benchmark.summary}</p>
          </div>
        )}
      </main>
    </div>
  );
};
export default App;
