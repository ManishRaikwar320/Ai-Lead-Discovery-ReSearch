import { useEffect, useState } from 'react';

const STAGES = [
  'Generating search queries',
  'Searching the web',
  'Deduplicating companies',
  'Researching websites',
  'Extracting company data',
  'ICP qualification',
  'Lead scoring',
  'Opportunity detection',
  'Drafting outreach',
  'Validating leads',
  'Finalizing results',
];

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

interface Props {
  onCancel: () => void;
}

export default function ProgressPanel({ onCancel }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    const stageTimer = window.setInterval(
      () => setStage((s) => (s + 1) % STAGES.length),
      2600,
    );
    return () => {
      window.clearInterval(timer);
      window.clearInterval(stageTimer);
    };
  }, []);

  return (
    <div className="progress-panel">
      <div className="progress-orb" aria-hidden="true">
        <span className="orb-ring" />
        <span className="orb-ring delay" />
        <span className="orb-core" />
      </div>

      <h2>Discovery in progress</h2>
      <p className="progress-stage" key={stage}>
        {STAGES[stage]}
      </p>

      <div className="progress-meta">
        <span className="elapsed">Elapsed {formatElapsed(elapsed)}</span>
        <span className="dot">·</span>
        <span>One long-running request — no progress endpoint yet</span>
      </div>

      <div className="progress-track">
        <div className="progress-bar" />
      </div>

      <ol className="stage-list">
        {STAGES.map((name, index) => (
          <li
            key={name}
            className={
              index === stage ? 'active' : index < stage ? 'done' : 'pending'
            }
          >
            {name}
          </li>
        ))}
      </ol>

      <button type="button" className="btn btn-ghost" onClick={onCancel}>
        Cancel discovery
      </button>
    </div>
  );
}
