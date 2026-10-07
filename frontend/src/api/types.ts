export interface LeadDiscoveryRequest {
  industry: string;
  location: string;
  ideal_customer: string;
  services: string[];
  company_size?: string | null;
  limit?: number;
}

export interface Funnel {
  search_queries: number;
  search_results: number;
  deduplicated: number;
  research_pool: number;
  researched: number;
  extracted: number;
  icp_qualified: number;
  scored: number;
  opportunities: number;
  outreach_ready: number;
  validated: number;
  final: number;
}

export interface Lead {
  domain: string;
  company_name: string;
  website: string;
  title: string | null;
  description: string | null;
  source_url: string | null;
  page_title: string | null;
  meta_description: string | null;
  summary: string | null;
  research_ok: boolean;
  industry: string | null;
  location: string | null;
  company_size: string | null;
  technologies: string[];
  signals: string[];
  qualified: boolean;
  fit_score: number;
  qualification_reason: string | null;
  score: number;
  tier: string | null;
  score_rationale: string | null;
  pain_points: string[];
  buying_signals: string[];
  recommended_service: string | null;
  opportunity_summary: string | null;
  outreach_subject: string | null;
  outreach_body: string | null;
  personalization_hook: string | null;
}

export type DiscoveryStatus = 'completed' | 'completed_with_errors' | 'failed';

export interface LeadDiscoveryResponse {
  status: DiscoveryStatus;
  total_leads: number;
  funnel: Funnel;
  errors: string[];
  leads: Lead[];
}

export interface HealthResponse {
  status: string;
  environment: string;
}
