import { useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE, ApiError, checkHealth, discoverLeads } from './api/client';
import type { HealthResponse, Lead, LeadDiscoveryResponse } from './api/types';
import DiscoveryForm from './components/DiscoveryForm';
import FunnelChart from './components/FunnelChart';
import LeadPanel from './components/LeadPanel';
import ProgressPanel from './components/ProgressPanel';
import ResultsTable, { type ResultsTab } from './components/ResultsTable';
import Sidebar, { type NavId } from './components/Sidebar';
import StatsRow from './components/StatsRow';
import TopBar from './components/TopBar';
import {
  emptyForm,
  toRequest,
  validateForm,
  type FieldErrors,
  type FormValues,
} from './validation';
import { exportLeadsCsv } from './utils';

type Phase = 'idle' | 'loading' | 'success' | 'error';
type Health = 'checking' | 'online' | 'offline';

const SAVED_KEY = 'leadfinder.saved';

const STATUS_COPY: Record<string, { label: string; className: string }> = {
  completed: { label: 'Completed', className: 'ok' },
  completed_with_errors: { label: 'Completed with warnings', className: 'warn' },
  failed: { label: 'Failed', className: 'fail' },
};

function loadSaved(): string[] {
  try {
    const raw = window.localStorage.getItem(SAVED_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
}

function scrollToSection(selector: string) {
  document.querySelector(selector)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export default function App() {
  const [values, setValues] = useState<FormValues>(emptyForm);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [serverFieldErrors, setServerFieldErrors] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<Phase>('idle');
  const [response, setResponse] = useState<LeadDiscoveryResponse | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health>('checking');
  const [environment, setEnvironment] = useState('development');
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [query, setQuery] = useState('');
  const [tab, setTab] = useState<ResultsTab>('all');
  const [saved, setSaved] = useState<string[]>(loadSaved);
  const [checked, setChecked] = useState<string[]>([]);
  const [activeNav, setActiveNav] = useState<NavId>('dashboard');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiBaseDraft, setApiBaseDraft] = useState(API_BASE);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal)
      .then((data: HealthResponse) => {
        setHealth('online');
        setEnvironment(data.environment);
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setHealth('offline');
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(SAVED_KEY, JSON.stringify(saved));
    } catch {
      /* storage unavailable */
    }
  }, [saved]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const handleChange = (next: FormValues) => {
    setValues(next);
    setFieldErrors({});
    setServerFieldErrors({});
  };

  const handleSubmit = async () => {
    const errors = validateForm(values);
    setFieldErrors(errors);
    setServerFieldErrors({});
    if (Object.keys(errors).length > 0) {
      scrollToSection('#discovery');
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setFatalError(null);
    setPhase('loading');
    setSelectedLead(null);
    setChecked([]);

    try {
      const result = await discoverLeads(toRequest(values), controller.signal);
      setResponse(result);
      setPhase('success');
      setHealth('online');
      setActiveNav('results');
      window.setTimeout(() => scrollToSection('#results'), 150);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        setPhase(response ? 'success' : 'idle');
      } else if (error instanceof ApiError && error.status === 422) {
        setServerFieldErrors(error.fieldErrors);
        setPhase(response ? 'success' : 'idle');
        scrollToSection('#discovery');
      } else {
        setFatalError(error instanceof Error ? error.message : 'Something went wrong.');
        setPhase('error');
        setHealth('offline');
      }
    } finally {
      abortRef.current = null;
    }
  };

  const handleCancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPhase(response ? 'success' : 'idle');
  };

  const toggleSave = (lead: Lead) => {
    setSaved((current) =>
      current.includes(lead.domain)
        ? current.filter((d) => d !== lead.domain)
        : [...current, lead.domain],
    );
  };

  const toggleCheck = (domain: string) => {
    setChecked((current) =>
      current.includes(domain)
        ? current.filter((d) => d !== domain)
        : [...current, domain],
    );
  };

  const checkAll = (domains: string[], on: boolean) => {
    setChecked((current) => {
      const others = current.filter((d) => !domains.includes(d));
      return on ? [...others, ...domains] : others;
    });
  };

  const allLeads = response?.leads ?? [];

  const counts = useMemo<Record<ResultsTab, number>>(() => {
    const base = response?.leads ?? [];
    return {
      all: base.length,
      high: base.filter((l) => l.score >= 90).length,
      tierA: base.filter((l) => l.tier === 'A').length,
      saved: base.filter((l) => saved.includes(l.domain)).length,
    };
  }, [response, saved]);

  const visibleLeads = useMemo(() => {
    let leads = response?.leads ?? [];
    if (tab === 'high') leads = leads.filter((l) => l.score >= 90);
    if (tab === 'tierA') leads = leads.filter((l) => l.tier === 'A');
    if (tab === 'saved') leads = leads.filter((l) => saved.includes(l.domain));
    const q = query.trim().toLowerCase();
    if (q) {
      leads = leads.filter((lead) =>
        [
          lead.company_name,
          lead.domain,
          lead.industry,
          lead.location,
          lead.summary ?? '',
          lead.recommended_service ?? '',
          ...lead.signals,
          ...lead.buying_signals,
          ...lead.technologies,
        ]
          .join(' ')
          .toLowerCase()
          .includes(q),
      );
    }
    return leads;
  }, [response, tab, query, saved]);

  const handleNavigate = (id: NavId) => {
    setActiveNav(id);
    if (id === 'settings') {
      setApiBaseDraft(API_BASE);
      setSettingsOpen(true);
      return;
    }
    if (id === 'saved') {
      setTab('saved');
      scrollToSection('#results');
      return;
    }
    if (id === 'dashboard') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    scrollToSection(`#${id}`);
  };

  const handleExportSelected = () => {
    const leads = allLeads.filter((lead) => checked.includes(lead.domain));
    if (leads.length > 0) exportLeadsCsv('leads-export.csv', leads);
  };

  const handleSaveSettings = () => {
    const next = apiBaseDraft.trim().replace(/\/+$/, '');
    try {
      if (next) window.localStorage.setItem('leadfinder.apiBase', next);
      else window.localStorage.removeItem('leadfinder.apiBase');
    } catch {
      /* storage unavailable */
    }
    window.location.reload();
  };

  const status = response ? STATUS_COPY[response.status] : null;
  const showPanel = selectedLead !== null;

  return (
    <div className="app-shell">
      <Sidebar
        active={activeNav}
        savedCount={saved.length}
        health={health}
        environment={environment}
        onNavigate={handleNavigate}
      />

      <div className="main">
        <TopBar
          query={query}
          onQueryChange={setQuery}
          running={phase === 'loading'}
          health={health}
          apiBase={API_BASE}
          onOpenDocs={() => window.open(`${API_BASE}/docs`, '_blank', 'noopener')}
        />

        <div className={`columns ${showPanel ? 'with-panel' : ''}`}>
          <div className="content">
            <DiscoveryForm
              values={values}
              errors={fieldErrors}
              serverFieldErrors={serverFieldErrors}
              loading={phase === 'loading'}
              onChange={handleChange}
              onSubmit={handleSubmit}
            />

            <StatsRow response={response} />

            {phase === 'loading' && <ProgressPanel onCancel={handleCancel} />}

            {phase === 'error' && (
              <div className="card status-card fail">
                <div className="status-head">
                  <h3>Request failed</h3>
                  <span className="muted">HTTP error</span>
                </div>
                <p>{fatalError}</p>
                <button type="button" className="btn btn-gradient" onClick={handleSubmit}>
                  Try again
                </button>
              </div>
            )}

            {phase !== 'loading' && response && (
              <div className={`card status-card ${status?.className ?? ''}`}>
                <div className="status-head">
                  <h3>{status?.label}</h3>
                  <span className="muted">
                    {response.total_leads} lead{response.total_leads === 1 ? '' : 's'} returned
                  </span>
                </div>
                {response.errors.length > 0 && (
                  <ul className="error-list">
                    {response.errors.map((error) => (
                      <li key={error}>{error}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <ResultsTable
              leads={visibleLeads}
              counts={counts}
              tab={tab}
              onTabChange={setTab}
              selected={selectedLead}
              onSelect={setSelectedLead}
              saved={saved}
              onToggleSave={toggleSave}
              checked={checked}
              onToggleCheck={toggleCheck}
              onCheckAll={checkAll}
              onExportSelected={handleExportSelected}
              onRerun={handleSubmit}
              loading={phase === 'loading'}
              hasResults={allLeads.length > 0}
            />

            {response && <FunnelChart funnel={response.funnel} />}
          </div>

          {showPanel && selectedLead && (
            <LeadPanel
              lead={selectedLead}
              saved={saved.includes(selectedLead.domain)}
              onToggleSave={toggleSave}
              onClose={() => setSelectedLead(null)}
            />
          )}
        </div>

        <footer className="footer">
          LeadFinder AI · backend <code>{API_BASE}</code> · FastAPI + LangGraph + Groq + Tavily
        </footer>
      </div>

      {settingsOpen && (
        <div className="modal-overlay" onClick={() => setSettingsOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>Settings</h3>
              <button
                type="button"
                className="icon-btn"
                onClick={() => setSettingsOpen(false)}
              >
                ×
              </button>
            </div>
            <div className="field">
              <label htmlFor="api-base">API base URL</label>
              <input
                id="api-base"
                type="text"
                value={apiBaseDraft}
                onChange={(e) => setApiBaseDraft(e.target.value)}
                placeholder="http://127.0.0.1:8000"
              />
              <p className="field-hint">
                Stored in this browser (localStorage key <code>leadfinder.apiBase</code>) and
                applied after reload. Leave as-is for the local backend.
              </p>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => window.open(`${API_BASE}/docs`, '_blank', 'noopener')}
              >
                Open API docs
              </button>
              <button type="button" className="btn btn-gradient" onClick={handleSaveSettings}>
                Save & reload
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
