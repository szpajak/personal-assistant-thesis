import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiUpload } from "@/lib/apiFetch";
import {
  Certificate,
  CertificateCreateInput,
  CertificateDraft,
} from "@/types/certificates";

export function useCertificates() {
  return useQuery({
    queryKey: ["certificates"],
    queryFn: () => apiFetch<Certificate[]>("/api/v1/certificates/"),
  });
}

export function useCreateCertificate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CertificateCreateInput) =>
      apiFetch<Certificate>("/api/v1/certificates/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["certificates"] });
    },
  });
}

export function useExtractCertificateDraft() {
  return useMutation({
    mutationFn: (file: File) =>
      apiUpload<{ drafts: CertificateDraft[] }>(
        "/api/v1/certificates/upload",
        file,
      ),
  });
}
