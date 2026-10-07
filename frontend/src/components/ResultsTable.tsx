import type { Lead } from '../api/types';
import { exportLeadJson, hueFor, initials } from '../utils';

export type ResultsTab = 'all' | 'high' | 'tierA' | 'saved';

interface TabDef {
  id: ResultsTab;
  label: string;
}

const TABS: TabDef[] = [
  { id: 'all', label: 'All Leads' },
  { id: 'high', label: 'High Match (90%+)' },
  { id: 'tierA', label: 'Tier A' },
  { id: 'saved', label: 'Saved' },
];

interface Props {
  leads: Lead[];
  counts: Record<ResultsTab, number>;
  tab: ResultsTab;
  onTabChange: (tab: ResultsTab) => void;
  selected: Lead | null;
  onSelect: (lead: Lead) => void;
  saved: string[];
  onToggleSave: (lead: Lead) => void;
  checked: string[];
  onToggleCheck: (domain: string) => void;
  onCheckAll: (domains: string[], checked: boolean) => void;
  onExportSelected: () => void;
  onRerun: () => void;
  loading: boolean;
  hasResults: boolean;
}

function SignalChips({ lead }: { lead: Lead }) {
  const signals = lead.buying_signals.filter(Boolean).slice(0, 2);
  const tech = lead.technologies.filter(Boolean).slice(0, 2);
  const fallback = lead.signals.filter(Boolean).slice(0, 2);
  const chips = signals.length > 0 ? signals : fallback;

  return (
    <div className="signal-chips">
      {chips.map((signal) => (
        <span key={signal} className="signal-chip signal-hot">
          {signal}
        </span>
      ))}
      {tech.length > 0 && (
        <span className="signal-chip signal-tech">
          Tech: {tech.join(', ')}
        </span>
      )}
      {chips.length === 0 && tech.length === 0 && (
        <span className="signal-chip signal-muted">
          ICP fit {lead.fit_score}%
        </span>
      )}
    </div>
  );
}

export default function ResultsTable({
  leads,
  counts,
  tab,
  onTabChange,
  selected,
  onSelect,
  saved,
  onToggleSave,
  checked,
  onToggleCheck,
  onCheckAll,
  onExportSelected,
  onRerun,
  loading,
  hasResults,
}: Props) {
  const allVisibleChecked =
    leads.length > 0 && leads.every((lead) => checked.includes(lead.domain));

  return (
    <section className="card results-card" id="results">
      <div className="card-head">
        <h3>Lead Discovery Results</h3>
        <div className="head-actions">
          {checked.length > 0 && (
            <button type="button" className="btn btn-ghost btn-small" onClick={onExportSelected}>
              Export CSV ({checked.length})
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={onRerun}
            disabled={loading}
          >
            Re-run leads
          </button>
        </div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map((def) => (
          <button
            key={def.id}
            type="button"
            role="tab"
            aria-selected={tab === def.id}
            className={`tab ${tab === def.id ? 'active' : ''}`}
            onClick={() => onTabChange(def.id)}
          >
            {def.label}
            <span className="tab-count">{counts[def.id]}</span>
          </button>
        ))}
      </div>

      {!hasResults ? (
        <div className="table-empty">
          <p className="table-empty-title">No discovery run yet</p>
          <p>
            Set your brief above and hit <strong>Discover Leads</strong> — results,
            match scores and outreach drafts will land here.
          </p>
        </div>
      ) : leads.length === 0 ? (
        <div className="table-empty">
          <p className="table-empty-title">Nothing in this view</p>
          <p>
            {tab === 'high'
              ? 'No leads scored 90% or higher this run.'
              : tab === 'tierA'
                ? 'No tier-A leads this run — try a tighter ICP or broader location.'
                : tab === 'saved'
                  ? 'Save leads with the bookmark action to collect them here.'
                  : 'No leads match your search.'}
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="leads-table">
            <thead>
              <tr>
                <th className="col-check">
                  <input
                    type="checkbox"
                    checked={allVisibleChecked}
                    onChange={(e) =>
                      onCheckAll(
                        leads.map((lead) => lead.domain),
                        e.target.checked,
                      )
                    }
                    aria-label="Select all visible leads"
                  />
                </th>
                <th>Lead Info</th>
                <th>AI Match Score</th>
                <th>Key Insights / Signals</th>
                <th>Contact</th>
                <th className="col-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => {
                const key = lead.domain || lead.company_name;
                const isSaved = saved.includes(lead.domain);
                const isChecked = checked.includes(lead.domain);
                return (
                  <tr
                    key={key}
                    className={selected?.domain === lead.domain ? 'selected' : ''}
                    onClick={() => onSelect(lead)}
                  >
                    <td className="col-check" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => onToggleCheck(lead.domain)}
                        aria-label={`Select ${lead.company_name}`}
                      />
                    </td>
                    <td>
                      <div className="lead-cell">
                        <span
                          className="lead-avatar"
                          style={{
                            background: `hsl(${hueFor(key)} 32% 24%)`,
                            color: `hsl(${hueFor(key)} 72% 72%)`,
                          }}
                        >
                          {initials(lead.company_name)}
                        </span>
                        <span className="lead-text">
                          <strong>{lead.company_name}</strong>
                          <small>
                            {lead.domain || lead.website}
                            {lead.industry ? ` · ${lead.industry}` : ''}
                          </small>
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="match-pill">{lead.score}% Match</span>
                    </td>
                    <td>
                      <SignalChips lead={lead} />
                    </td>
                    <td>
                      <div className="contact-cell">
                        <a
                          href={lead.website}
                          target="_blank"
                          rel="noreferrer"
                          title="Website"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                            <circle cx="12" cy="12" r="9" />
                            <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
                          </svg>
                        </a>
                        {lead.source_url && (
                          <a
                            href={lead.source_url}
                            target="_blank"
                            rel="noreferrer"
                            title="Source"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                              <path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.2 1.1" />
                              <path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.2-1.1" />
                            </svg>
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="col-actions" onClick={(e) => e.stopPropagation()}>
                      <div className="row-actions">
                        <button
                          type="button"
                          className={`icon-btn ${isSaved ? 'saved' : ''}`}
                          onClick={() => onToggleSave(lead)}
                          title={isSaved ? 'Remove from saved' : 'Save lead'}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill={isSaved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8">
                            <path d="M6 4h12v17l-6-4-6 4V4z" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline btn-small"
                          onClick={() => onSelect(lead)}
                        >
                          View AI Summary
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-small"
                          onClick={() => exportLeadJson(lead)}
                        >
                          Export
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
