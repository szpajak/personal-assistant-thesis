export interface Email {
  id: string;
  subject: string;
  sender: string;
  received_at: string | null;
  summary: string | null;
  classification: string | null;
  action_required?: boolean;
  entity_name?: string | null;
}
