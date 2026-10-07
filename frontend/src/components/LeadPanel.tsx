import { useEffect, useState } from 'react';
import type { Lead } from '../api/types';
import { hueFor, initials } from '../utils';

interface Props {
  lead: Lead;
  saved: boolean;
  onToggleSave: (lead: Lead) => void;
  onClose: () => void;
}

function Bullets({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ul className="bullets">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button type="button" className="btn btn-ghost btn-small" onClick={copy}>
      {copied ? 'Copied!' : label}
    </button>
  );
}

export default function LeadPanel({ lead, saved, onToggleSave, onClose }: Props) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const outreach = [lead.outreach_subject, lead.outreach_body]
    .filter(Boolean)
    .join('\n\n');

  return (
    <aside className="lead-panel" aria-label="AI lead summary">
      <div className="panel-head">
        <h3>AI Lead Summary</h3>
        <button type="button" className="icon-btn" onClick={onClose} title="Close panel">
          ×
        </button>
      </div>

      <div className="panel-identity">
        <span
          className="lead-avatar lg"
          style={{
            background: `hsl(${hueFor(lead.domain || lead.company_name)} 32% 24%)`,
            color: `hsl(${hueFor(lead.domain || lead.company_name)} 72% 72%)`,
          }}
        >
          {initials(lead.company_name)}
        </span>
        <div className="panel-identity-text">
          <strong>{lead.company_name}</strong>
          <a href={lead.website} target="_blank" rel="noreferrer">
            {lead.domain || lead.website}
          </a>
        </div>
        <span className={`tier tier-${(lead.tier ?? 'C').toLowerCase()}`}>
          {lead.tier ?? '—'}
        </span>
      </div>

      <div className="panel-stats">
        <div className="panel-stat">
          <span>{lead.score}</span>
          <small>Match</small>
        </div>
        <div className="panel-stat">
          <span>{lead.fit_score}</span>
          <small>ICP fit</small>
        </div>
        <div className="panel-stat">
          <span>{lead.qualified ? 'Yes' : 'No'}</span>
          <small>Qualified</small>
        </div>
        <div className="panel-stat">
          <span>{lead.research_ok ? 'OK' : 'No'}</span>
          <small>Researched</small>
        </div>
      </div>

      <div className="panel-body">
        <section className="panel-section">
          <h4>AI summary & pitch recommendation</h4>
          <p>
            {lead.summary ??
              lead.meta_description ??
              lead.description ??
              'No summary was generated for this company.'}
          </p>
        </section>

        <section className="panel-section">
          <h4>Opportunity</h4>
          <p>{lead.opportunity_summary ?? 'No opportunity detected.'}</p>
          {lead.recommended_service && (
            <p className="muted">Recommended service: {lead.recommended_service}</p>
          )}
        </section>

        <section className="panel-section">
          <h4>Buying signals</h4>
          <Bullets items={lead.buying_signals} empty="None detected." />
        </section>

        <section className="panel-section">
          <h4>Pain points</h4>
          <Bullets items={lead.pain_points} empty="None detected." />
        </section>

        <section className="panel-section">
          <h4>Company signals</h4>
          <Bullets items={lead.signals} empty="No extra signals found." />
        </section>

        <section className="panel-section">
          <h4>Tech stack</h4>
          {lead.technologies.length > 0 ? (
            <div className="tag-list">
              {lead.technologies.map((tech) => (
                <span key={tech}>{tech}</span>
              ))}
            </div>
          ) : (
            <p className="muted">Not detected.</p>
          )}
        </section>

        <section className="panel-section">
          <h4>Why this score</h4>
          <p>{lead.score_rationale ?? 'No rationale provided.'}</p>
          {lead.qualification_reason && (
            <p className="muted">ICP: {lead.qualification_reason}</p>
          )}
        </section>

        <section className="panel-section">
          <h4>Company details</h4>
          <dl className="detail-list">
            <div>
              <dt>Industry</dt>
              <dd>{lead.industry ?? '—'}</dd>
            </div>
            <div>
              <dt>Location</dt>
              <dd>{lead.location ?? '—'}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{lead.company_size ?? '—'}</dd>
            </div>
            <div>
              <dt>Page title</dt>
              <dd>{lead.page_title ?? '—'}</dd>
            </div>
          </dl>
        </section>

        <section className="panel-section">
          <h4>Outreach draft</h4>
          {lead.outreach_subject ? (
            <div className="outreach-block">
              <div className="outreach-line">
                <strong>Subject:</strong> {lead.outreach_subject}
                <CopyButton text={lead.outreach_subject ?? ''} label="Copy subject" />
              </div>
              {lead.personalization_hook && (
                <p className="muted">Hook: {lead.personalization_hook}</p>
              )}
              <p className="outreach-body">{lead.outreach_body ?? ''}</p>
            </div>
          ) : (
            <p className="muted">No outreach was drafted for this lead.</p>
          )}
        </section>
      </div>

      <div className="panel-footer">
        <button
          type="button"
          className={`btn btn-ghost ${saved ? 'active' : ''}`}
          onClick={() => onToggleSave(lead)}
        >
          {saved ? 'Saved ✓' : 'Save lead'}
        </button>
        <button
          type="button"
          className="btn btn-gradient"
          disabled={!outreach}
          onClick={() => {
            if (outreach) void navigator.clipboard.writeText(outreach);
          }}
        >
          {outreach ? 'Copy outreach message' : 'No outreach yet'}
        </button>
      </div>
    </aside>
  );
}
