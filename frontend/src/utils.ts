import type { Lead } from './api/types';

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function hueFor(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) % 360;
  }
  return hash;
}

export function average(values: number[]): number | null {
  if (values.length === 0) return null;
  return Math.round(values.reduce((sum, v) => sum + v, 0) / values.length);
}

export function downloadFile(
  filename: string,
  content: string,
  mime: string,
): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

const CSV_COLUMNS: { key: keyof Lead; label: string }[] = [
  { key: 'company_name', label: 'company_name' },
  { key: 'domain', label: 'domain' },
  { key: 'website', label: 'website' },
  { key: 'tier', label: 'tier' },
  { key: 'score', label: 'score' },
  { key: 'fit_score', label: 'fit_score' },
  { key: 'qualified', label: 'qualified' },
  { key: 'industry', label: 'industry' },
  { key: 'location', label: 'location' },
  { key: 'company_size', label: 'company_size' },
  { key: 'recommended_service', label: 'recommended_service' },
  { key: 'outreach_subject', label: 'outreach_subject' },
];

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

export function leadsToCsv(leads: Lead[]): string {
  const header = CSV_COLUMNS.map((c) => c.label).join(',');
  const rows = leads.map((lead) =>
    CSV_COLUMNS.map((column) => csvCell(lead[column.key])).join(','),
  );
  return [header, ...rows].join('\r\n');
}

export function exportLeadsCsv(filename: string, leads: Lead[]): void {
  downloadFile(filename, leadsToCsv(leads), 'text/csv;charset=utf-8');
}

export function exportLeadJson(lead: Lead): void {
  const safeName = (lead.domain || 'lead').replace(/[^a-z0-9.-]/gi, '_');
  downloadFile(`${safeName}.json`, JSON.stringify(lead, null, 2), 'application/json');
}
