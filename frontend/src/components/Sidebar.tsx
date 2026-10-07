export type NavId =
  | 'dashboard'
  | 'discovery'
  | 'results'
  | 'pipeline'
  | 'saved'
  | 'settings';

interface NavItem {
  id: NavId;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: 'grid' },
  { id: 'discovery', label: 'Discovery Brief', icon: 'spark' },
  { id: 'results', label: 'Results', icon: 'list' },
  { id: 'pipeline', label: 'Pipeline', icon: 'chart' },
  { id: 'saved', label: 'Saved Leads', icon: 'bookmark' },
  { id: 'settings', label: 'Settings', icon: 'gear' },
];

function Icon({ name }: { name: string }) {
  const common = {
    width: 17,
    height: 17,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  switch (name) {
    case 'grid':
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case 'spark':
      return (
        <svg {...common}>
          <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
          <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z" />
        </svg>
      );
    case 'list':
      return (
        <svg {...common}>
          <path d="M8 6h13M8 12h13M8 18h13" />
          <circle cx="3.5" cy="6" r="1.2" />
          <circle cx="3.5" cy="12" r="1.2" />
          <circle cx="3.5" cy="18" r="1.2" />
        </svg>
      );
    case 'chart':
      return (
        <svg {...common}>
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
        </svg>
      );
    case 'bookmark':
      return (
        <svg {...common}>
          <path d="M6 4h12v17l-6-4-6 4V4z" />
        </svg>
      );
    case 'gear':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3.2" />
          <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 9 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
        </svg>
      );
    default:
      return null;
  }
}

interface Props {
  active: NavId;
  savedCount: number;
  health: 'checking' | 'online' | 'offline';
  environment: string;
  onNavigate: (id: NavId) => void;
}

export default function Sidebar({
  active,
  savedCount,
  health,
  environment,
  onNavigate,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
          </svg>
        </span>
        <div className="brand-text">
          <strong>LeadFinder AI</strong>
          <small>Lead Discovery Agent</small>
        </div>
      </div>

      <nav className="side-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-item ${active === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
            {item.id === 'saved' && savedCount > 0 && (
              <span className="nav-badge">{savedCount}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="side-user">
        <span className="side-avatar">LD</span>
        <div>
          <strong>Local workspace</strong>
          <small>
            <span className={`dot dot-${health}`} />
            {environment} · API {health === 'online' ? 'online' : health === 'offline' ? 'offline' : 'checking'}
          </small>
        </div>
      </div>
    </aside>
  );
}
