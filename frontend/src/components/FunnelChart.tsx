import type { Funnel } from '../api/types';

interface FunnelStep {
  key: keyof Funnel;
  label: string;
  hint: string;
}

const STEPS: FunnelStep[] = [
  { key: 'search_queries', label: 'Search queries', hint: 'LLM-generated queries' },
  { key: 'search_results', label: 'Search results', hint: 'Tavily hits per query' },
  { key: 'deduplicated', label: 'Deduplicated', hint: 'Unique company domains' },
  { key: 'research_pool', label: 'Research pool', hint: 'Sites sent to fetch' },
  { key: 'researched', label: 'Researched', hint: 'Pages fetched OK' },
  { key: 'extracted', label: 'Extracted', hint: 'Companies profiled' },
  { key: 'icp_qualified', label: 'ICP qualified', hint: 'Fit your profile' },
  { key: 'scored', label: 'Scored', hint: 'Ranked 0–100' },
  { key: 'opportunities', label: 'Opportunities', hint: 'Pain points detected' },
  { key: 'outreach_ready', label: 'Outreach ready', hint: 'Message generated' },
  { key: 'validated', label: 'Validated', hint: 'Survived checks' },
  { key: 'final', label: 'Final leads', hint: 'Returned to you' },
];

interface Props {
  funnel: Funnel;
}

export default function FunnelChart({ funnel }: Props) {
  const max = Math.max(1, ...STEPS.map((step) => funnel[step.key]));

  return (
    <section className="card" id="pipeline">
      <div className="card-head">
        <h3>Pipeline funnel</h3>
        <span className="muted">counts per stage</span>
      </div>
      <ul className="funnel">
        {STEPS.map((step, index) => {
          const value = funnel[step.key];
          const width = Math.max(2, Math.round((value / max) * 100));
          return (
            <li key={step.key} className="funnel-row">
              <span className="funnel-index">{index + 1}</span>
              <span className="funnel-label">
                {step.label}
                <small>{step.hint}</small>
              </span>
              <span className="funnel-bar-track">
                <span
                  className={`funnel-bar ${step.key === 'final' ? 'final' : ''}`}
                  style={{ width: `${width}%` }}
                />
              </span>
              <span className="funnel-value">{value}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
