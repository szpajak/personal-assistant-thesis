export interface Application {
  id: string;
  job_offer_id: string;
  status: string;
  applied_at?: string | null;
  notes?: string | null;
  job_offer?: {
    id?: string;
    title?: string;
    company?: string;
  } | null;
}
