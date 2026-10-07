import { useState, type FormEvent } from 'react';
import type { FieldErrors, FormValues } from '../validation';

interface Props {
  values: FormValues;
  errors: FieldErrors;
  serverFieldErrors: Record<string, string>;
  loading: boolean;
  onChange: (values: FormValues) => void;
  onSubmit: () => void;
}

interface Preset {
  label: string;
  industry?: string;
  company_size?: string;
}

const PRESETS: Preset[] = [
  { label: 'Dental clinics', industry: 'dental clinics' },
  { label: 'B2B SaaS', industry: 'B2B SaaS companies' },
  { label: 'E-commerce', industry: 'e-commerce stores' },
  { label: 'Marketing agencies', industry: 'marketing agencies' },
  { label: 'Law firms', industry: 'law firms' },
  { label: 'Small business', company_size: 'small business' },
];

const LIMIT_PRESETS = [5, 10, 15, 20];

export default function DiscoveryForm({
  values,
  errors,
  serverFieldErrors,
  loading,
  onChange,
  onSubmit,
}: Props) {
  const [serviceDraft, setServiceDraft] = useState('');
  const [serviceError, setServiceError] = useState<string | null>(null);

  const errorFor = (field: keyof FormValues): string | undefined =>
    errors[field] ?? serverFieldErrors[field];

  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) =>
    onChange({ ...values, [key]: value });

  const applyPreset = (preset: Preset) => {
    const next = { ...values };
    if (preset.industry) next.industry = preset.industry;
    if (preset.company_size) next.company_size = preset.company_size;
    onChange(next);
  };

  const isPresetActive = (preset: Preset): boolean => {
    if (preset.industry) {
      return values.industry.trim().toLowerCase() === preset.industry.toLowerCase();
    }
    if (preset.company_size) {
      return (
        values.company_size.trim().toLowerCase() ===
        preset.company_size.toLowerCase()
      );
    }
    return false;
  };

  const addService = () => {
    const draft = serviceDraft.trim();
    if (!draft) return;
    if (values.services.length >= 10) {
      setServiceError('You can add up to 10 services.');
      return;
    }
    if (values.services.includes(draft)) {
      setServiceError('That service is already added.');
      return;
    }
    setServiceError(null);
    setServiceDraft('');
    onChange({ ...values, services: [...values.services, draft] });
  };

  const removeService = (service: string) => {
    setServiceError(null);
    onChange({
      ...values,
      services: values.services.filter((s) => s !== service),
    });
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  const handleServiceKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addService();
    }
  };

  return (
    <form className="discover-form" onSubmit={handleSubmit} noValidate id="discovery">
      <div className="hero-bar">
        <span className="hero-icon" aria-hidden="true">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.9"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
          </svg>
        </span>

        <div className="hero-fields">
          <div className="hero-field">
            <label htmlFor="industry">Industry</label>
            <input
              id="industry"
              type="text"
              placeholder="e.g. dental clinics"
              maxLength={100}
              value={values.industry}
              onChange={(e) => set('industry', e.target.value)}
              disabled={loading}
            />
          </div>

          <span className="hero-divider" />

          <div className="hero-field">
            <label htmlFor="location">Location</label>
            <input
              id="location"
              type="text"
              placeholder="e.g. Austin, Texas"
              maxLength={100}
              value={values.location}
              onChange={(e) => set('location', e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        <button type="submit" className="btn btn-gradient" disabled={loading}>
          {loading ? 'Discovering…' : 'Discover Leads'}
        </button>
      </div>

      {(errorFor('industry') || errorFor('location')) && (
        <p className="hero-errors">
          {errorFor('industry') ?? errorFor('location')}
        </p>
      )}

      <div className="quick-filters">
        <span className="quick-label">Quick filter:</span>
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className={`filter-chip ${isPresetActive(preset) ? 'active' : ''}`}
            onClick={() => applyPreset(preset)}
            disabled={loading}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <section className="card brief-card">
        <div className="card-head">
          <h3>Discovery brief</h3>
          <span className="muted">POST /api/leads/discover</span>
        </div>

        <div className="field">
          <label htmlFor="ideal_customer">
            Who is your ideal customer?{' '}
            <span className="counter">{values.ideal_customer.length}/500</span>
          </label>
          <textarea
            id="ideal_customer"
            rows={3}
            maxLength={500}
            placeholder="Independent dental practices with 2-10 dentists looking to modernize patient intake…"
            value={values.ideal_customer}
            onChange={(e) => set('ideal_customer', e.target.value)}
            disabled={loading}
          />
          {errorFor('ideal_customer') && (
            <p className="field-error">{errorFor('ideal_customer')}</p>
          )}
        </div>

        <div className="field">
          <label htmlFor="service-input">Services you offer</label>
          <div className="service-input-row">
            <input
              id="service-input"
              type="text"
              placeholder="Type a service and press Enter"
              value={serviceDraft}
              onChange={(e) => setServiceDraft(e.target.value)}
              onKeyDown={handleServiceKeyDown}
              disabled={loading}
            />
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={addService}
              disabled={loading || !serviceDraft.trim()}
            >
              Add
            </button>
          </div>
          {values.services.length > 0 && (
            <ul className="chip-list">
              {values.services.map((service) => (
                <li key={service} className="chip">
                  <span>{service}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${service}`}
                    onClick={() => removeService(service)}
                    disabled={loading}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          {(errorFor('services') ?? serviceError) && (
            <p className="field-error">{errorFor('services') ?? serviceError}</p>
          )}
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="company_size">
              Company size <span className="muted">optional</span>
            </label>
            <input
              id="company_size"
              type="text"
              maxLength={100}
              placeholder="e.g. small business"
              value={values.company_size}
              onChange={(e) => set('company_size', e.target.value)}
              disabled={loading}
            />
            {errorFor('company_size') && (
              <p className="field-error">{errorFor('company_size')}</p>
            )}
          </div>

          <div className="field">
            <label htmlFor="limit">Max leads</label>
            <div className="limit-row">
              <input
                id="limit"
                type="range"
                min={1}
                max={20}
                value={values.limit}
                onChange={(e) => set('limit', Number(e.target.value))}
                disabled={loading}
              />
              <output className="limit-value">{values.limit}</output>
            </div>
            <div className="limit-presets">
              {LIMIT_PRESETS.map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`preset ${values.limit === n ? 'active' : ''}`}
                  onClick={() => set('limit', n)}
                  disabled={loading}
                >
                  {n}
                </button>
              ))}
            </div>
            {errorFor('limit') && <p className="field-error">{errorFor('limit')}</p>}
          </div>
        </div>

        <p className="form-hint">
          11-stage AI pipeline: search → website research → ICP fit → scoring →
          opportunities → outreach. Expect 30 seconds to a few minutes.
        </p>
      </section>
    </form>
  );
}
