import type { LeadDiscoveryResponse } from '../api/types';
import { average } from '../utils';

interface StatCard {
  key: string;
  label: string;
  value: string;
  sub: string;
  accent: 'violet' | 'green' | 'blue' | 'amber';
}

interface Props {
  response: LeadDiscoveryResponse | null;
}

export default function StatsRow({ response }: Props) {
  const leads = response?.leads ?? [];
  const funnel = response?.funnel;

  const avgScore = average(leads.map((l) => l.score));
  const avgFit = average(leads.map((l) => l.fit_score));
  const tierACount = leads.filter((l) => l.tier === 'A').length;

  const cards: StatCard[] = [
    {
      key: 'total',
      label: 'Total Leads Discovered',
      value: response ? String(response.total_leads) : '—',
      sub: funnel
        ? `${funnel.researched} researched · ${funnel.deduplicated} unique domains`
        : 'Run a discovery to populate',
      accent: 'violet',
    },
    {
      key: 'match',
      label: 'Average AI Match',
      value: avgScore === null ? '—' : `${avgScore}%`,
      sub:
        avgFit === null
          ? 'Weighted across returned leads'
          : `Avg ICP fit ${avgFit}% · ${tierACount} tier-A`,
      accent: 'green',
    },
    {
      key: 'opps',
      label: 'Opportunities Detected',
      value: funnel ? String(funnel.opportunities) : '—',
      sub: funnel
        ? `${funnel.icp_qualified} ICP-qualified · ${funnel.scored} scored`
        : 'Pain points and buying signals',
      accent: 'blue',
    },
    {
      key: 'outreach',
      label: 'Outreach Ready',
      value: funnel ? String(funnel.outreach_ready) : '—',
      sub: funnel
        ? `${funnel.validated} passed validation`
        : 'Personalised drafts generated',
      accent: 'amber',
    },
  ];

  return (
    <div className="stats-row">
      {cards.map((card) => (
        <div key={card.key} className={`stat-card accent-${card.accent}`}>
          <div className="stat-icon" aria-hidden="true">
            {card.key === 'total' && '◎'}
            {card.key === 'match' && '％'}
            {card.key === 'opps' && '⚡'}
            {card.key === 'outreach' && '✉'}
          </div>
          <div className="stat-content">
            <span className="stat-label">{card.label}</span>
            <span className="stat-value">{card.value}</span>
            <span className="stat-sub">{card.sub}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
