"use client";

import { useRef, useState } from "react";
import {
  useCertificates,
  useCreateCertificate,
  useExtractCertificateDraft,
} from "@/hooks/useCertificates";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, Award, Plus } from "lucide-react";

const emptyForm = { title: "", issuer: "", issued_at: "", document_url: "", skills: "" };

export default function CertificatesPage() {
  const { data: certificates, isLoading } = useCertificates();
  const createCertificate = useCreateCertificate();
  const extractDraft = useExtractCertificateDraft();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState(emptyForm);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await extractDraft.mutateAsync(file);
      const draft = result.drafts[0];
      if (draft) {
        setForm({
          title: draft.title || "",
          issuer: draft.issuer || "",
          issued_at: draft.issued_at || "",
          document_url: "",
          skills: (draft.validated_skills || []).join(", "),
        });
      }
    } finally {
      e.target.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    await createCertificate.mutateAsync({
      title: form.title.trim(),
      issuer: form.issuer.trim(),
      issued_at: form.issued_at || null,
      document_url: form.document_url.trim(),
      validated_skills: form.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    });
    setForm(emptyForm);
  };

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Certificates</h1>
        <p className="text-sm text-gray-500">
          Credentials that validate your skills — linked into your knowledge graph.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Add a Certificate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.docx"
                className="hidden"
                onChange={handleFileSelected}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={extractDraft.isPending}
              >
                <Upload className="mr-2 h-4 w-4" />
                {extractDraft.isPending ? "Extracting…" : "Upload to auto-fill"}
              </Button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="cert-title">Title</Label>
                <Input
                  id="cert-title"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. AWS Certified Solutions Architect"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="cert-issuer">Issuer</Label>
                <Input
                  id="cert-issuer"
                  value={form.issuer}
                  onChange={(e) => setForm({ ...form, issuer: e.target.value })}
                  placeholder="e.g. Amazon Web Services"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="cert-issued-at">Issued date</Label>
                  <Input
                    id="cert-issued-at"
                    type="date"
                    value={form.issued_at}
                    onChange={(e) => setForm({ ...form, issued_at: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="cert-url">Document URL</Label>
                  <Input
                    id="cert-url"
                    value={form.document_url}
                    onChange={(e) => setForm({ ...form, document_url: e.target.value })}
                    placeholder="https://…"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="cert-skills">Skills validated (comma-separated)</Label>
                <Input
                  id="cert-skills"
                  value={form.skills}
                  onChange={(e) => setForm({ ...form, skills: e.target.value })}
                  placeholder="AWS, Kubernetes, Terraform"
                />
              </div>
              <Button type="submit" disabled={createCertificate.isPending}>
                <Plus className="mr-2 h-4 w-4" />
                {createCertificate.isPending ? "Saving…" : "Add Certificate"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">My Certificates</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <Skeleton className="h-40 w-full rounded-lg" />
            ) : certificates && certificates.length > 0 ? (
              certificates.map((cert) => (
                <div key={cert.id} className="rounded-lg border p-4 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Award className="h-4 w-4 text-gray-500 shrink-0" />
                      <span className="font-medium">{cert.title}</span>
                    </div>
                    {cert.issued_at && (
                      <span className="text-xs text-gray-500 shrink-0">{cert.issued_at}</span>
                    )}
                  </div>
                  {cert.issuer && <p className="text-sm text-gray-500">{cert.issuer}</p>}
                  {cert.validated_skills.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {cert.validated_skills.map((skill) => (
                        <Badge key={skill} variant="secondary">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="text-sm text-gray-500 text-center py-8">
                No certificates yet — add one to strengthen your skill evidence.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
