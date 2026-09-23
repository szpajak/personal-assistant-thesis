export interface Certificate {
  id: string;
  title: string;
  issuer: string;
  issued_at?: string | null;
  document_url?: string;
  validated_skills: string[];
}

export interface CertificateCreateInput {
  title: string;
  issuer: string;
  issued_at?: string | null;
  document_url?: string;
  validated_skills: string[];
}

export interface CertificateDraft {
  title: string;
  issuer: string;
  issued_at?: string | null;
  validated_skills: string[];
}
