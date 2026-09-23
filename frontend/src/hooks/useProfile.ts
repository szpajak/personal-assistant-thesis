import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiUpload } from "@/lib/apiFetch";
import type {
  Education,
  EducationCreateInput,
  Employment,
  EmploymentCreateInput,
  PersonProfile,
  PersonProfileUpdateInput,
  ProfileExtractResponse,
  ProfileSummary,
  TargetRole,
  TargetRoleCreateInput,
  TargetRoleRefreshResponse,
} from "@/types/profile";

// Roles actively (re)scraping/ingesting a market sample - poll until every
// role settles into "ready" or "error".
const isRoleSampling = (role: TargetRole) =>
  role.sample_status === "scraping" || role.sample_status === "ingesting";

export function useProfileSummary() {
  return useQuery({
    queryKey: ["profile-summary"],
    queryFn: () => apiFetch<ProfileSummary>("/api/v1/profile/summary"),
  });
}

export function useProfileDetails() {
  return useQuery({
    queryKey: ["profile-details"],
    queryFn: () => apiFetch<PersonProfile>("/api/v1/profile/me"),
  });
}

export function useUpdateProfileDetails() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PersonProfileUpdateInput) =>
      apiFetch<PersonProfile>("/api/v1/profile/me", {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile-details"] });
    },
  });
}

export function useEmployment() {
  return useQuery({
    queryKey: ["employment"],
    queryFn: () => apiFetch<Employment[]>("/api/v1/profile/employment"),
  });
}

export function useCreateEmployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmploymentCreateInput) =>
      apiFetch<Employment>("/api/v1/profile/employment", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employment"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useUpdateEmployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: EmploymentCreateInput & { id: string }) =>
      apiFetch<Employment>(`/api/v1/profile/employment/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employment"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useDeleteEmployment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/profile/employment/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employment"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useEducation() {
  return useQuery({
    queryKey: ["education"],
    queryFn: () => apiFetch<Education[]>("/api/v1/profile/education"),
  });
}

export function useCreateEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EducationCreateInput) =>
      apiFetch<Education>("/api/v1/profile/education", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["education"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useUpdateEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: EducationCreateInput & { id: string }) =>
      apiFetch<Education>(`/api/v1/profile/education/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["education"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useDeleteEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/profile/education/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["education"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useTargetRoles() {
  return useQuery({
    queryKey: ["target-roles"],
    queryFn: () => apiFetch<TargetRole[]>("/api/v1/profile/target-roles"),
    // Keep polling while any role's market sample is still being scraped/
    // ingested, so the Skills page picks up "ready"/"error" without a
    // manual refresh.
    refetchInterval: (query) => {
      const roles = query.state.data as TargetRole[] | undefined;
      return roles?.some(isRoleSampling) ? 4000 : false;
    },
  });
}

export function useCreateTargetRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TargetRoleCreateInput) =>
      apiFetch<TargetRole>("/api/v1/profile/target-roles", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["target-roles"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useRefreshTargetRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<TargetRoleRefreshResponse>(
        `/api/v1/profile/target-roles/${id}/refresh`,
        {
          method: "POST",
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["target-roles"] });
    },
  });
}

export function useDeleteTargetRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/profile/target-roles/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["target-roles"] });
      queryClient.invalidateQueries({ queryKey: ["profile-summary"] });
    },
  });
}

export function useExtractProfileDrafts() {
  return useMutation({
    mutationFn: (file: File) =>
      apiUpload<ProfileExtractResponse>("/api/v1/profile/upload", file),
  });
}
