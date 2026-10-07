import type { LeadDiscoveryRequest } from './api/types';

export interface FormValues {
  industry: string;
  location: string;
  ideal_customer: string;
  services: string[];
  company_size: string;
  limit: number;
}

export const emptyForm: FormValues = {
  industry: '',
  location: '',
  ideal_customer: '',
  services: [],
  company_size: '',
  limit: 10,
};

export type FieldErrors = Partial<Record<keyof FormValues, string>>;

export function validateForm(values: FormValues): FieldErrors {
  const errors: FieldErrors = {};

  const industry = values.industry.trim();
  if (industry.length < 2) {
    errors.industry = 'Industry must be at least 2 characters.';
  } else if (industry.length > 100) {
    errors.industry = 'Industry must be 100 characters or fewer.';
  }

  const location = values.location.trim();
  if (location.length < 2) {
    errors.location = 'Location must be at least 2 characters.';
  } else if (location.length > 100) {
    errors.location = 'Location must be 100 characters or fewer.';
  }

  const ideal = values.ideal_customer.trim();
  if (ideal.length < 10) {
    errors.ideal_customer = 'Describe your ideal customer in at least 10 characters.';
  } else if (ideal.length > 500) {
    errors.ideal_customer = 'Ideal customer must be 500 characters or fewer.';
  }

  const services = values.services.map((s) => s.trim()).filter(Boolean);
  if (services.length === 0) {
    errors.services = 'Add at least one service you offer.';
  } else if (services.length > 10) {
    errors.services = 'You can add up to 10 services.';
  }

  if (values.company_size.trim().length > 100) {
    errors.company_size = 'Company size must be 100 characters or fewer.';
  }

  if (!Number.isFinite(values.limit) || values.limit < 1 || values.limit > 20) {
    errors.limit = 'Limit must be between 1 and 20.';
  }

  return errors;
}

export function toRequest(values: FormValues): LeadDiscoveryRequest {
  const services = values.services.map((s) => s.trim()).filter(Boolean);
  return {
    industry: values.industry.trim(),
    location: values.location.trim(),
    ideal_customer: values.ideal_customer.trim(),
    services,
    company_size: values.company_size.trim() || null,
    limit: values.limit,
  };
}
