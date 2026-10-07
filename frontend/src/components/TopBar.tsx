interface Props {
  query: string;
  onQueryChange: (value: string) => void;
  running: boolean;
  health: 'checking' | 'online' | 'offline';
  apiBase: string;
  onOpenDocs: () => void;
}

export default function TopBar({
  query,
  onQueryChange,
  running,
  health,
  apiBase,
  onOpenDocs,
}: Props) {
  return (
    <header className="topbar">
      <label className="search-box">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3.5-3.5" />
        </svg>
        <input
          type="search"
          placeholder="Search leads, industries, or signals…"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
      </label>

      <div className="topbar-right">
        <span className={`pill ${running ? 'pill-running' : 'pill-idle'}`}>
          <span className="pill-dot" />
          {running ? 'Pipeline: Running' : 'Pipeline: Idle'}
        </span>

        <button type="button" className="pill pill-ghost" onClick={onOpenDocs}>
          API docs
        </button>

        <span
          className={`pill ${health === 'online' ? 'pill-ok' : health === 'offline' ? 'pill-fail' : ''}`}
          title={apiBase}
        >
          <span className="pill-dot" />
          {health === 'checking' ? 'Checking…' : health === 'online' ? 'API online' : 'API offline'}
        </span>

        <span className="topbar-avatar">LF</span>
      </div>
    </header>
  );
}
