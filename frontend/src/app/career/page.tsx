"use client";

import { useEffect, useRef, useState } from "react";
import {
  useCreateEducation,
  useCreateEmployment,
  useDeleteEducation,
  useDeleteEmployment,
  useEducation,
  useEmployment,
  useExtractProfileDrafts,
  useProfileDetails,
  useProfileSummary,
  useTargetRoles,
  useUpdateEducation,
  useUpdateEmployment,
  useUpdateProfileDetails,
} from "@/hooks/useProfile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Briefcase,
  Contact,
  GraduationCap,
  Target,
  Upload,
  Trash2,
  Pencil,
  Plus,
  MapPin,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { Education, Employment } from "@/types/profile";

const emptyProfileForm = {
  bio: "",
  phone: "",
  location: "",
  linkedin_url: "",
  github_url: "",
  website_url: "",
  languages_spoken: "",
  interests: "",
  awards: "",
};

const emptyEmployment = {
  title: "",
  company: "",
  start_date: "",
  end_date: "",
  description: "",
  skills: "",
};

const emptyEducation = {
  institution: "",
  degree: "",
  field_of_study: "",
  start_date: "",
  end_date: "",
  description: "",
};

export default function CareerPage() {
  const { data: summary, isLoading: summaryLoading } = useProfileSummary();
  const { data: employment, isLoading: empLoading } = useEmployment();
  const { data: education, isLoading: eduLoading } = useEducation();
  const { data: roles, isLoading: rolesLoading } = useTargetRoles();
  const { data: profileDetails, isLoading: profileLoading } = useProfileDetails();

  const createEmp = useCreateEmployment();
  const updateEmp = useUpdateEmployment();
  const deleteEmp = useDeleteEmployment();
  const createEdu = useCreateEducation();
  const updateEdu = useUpdateEducation();
  const deleteEdu = useDeleteEducation();
  const extractDraft = useExtractProfileDrafts();
  const updateProfileDetails = useUpdateProfileDetails();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [empForm, setEmpForm] = useState(emptyEmployment);
  const [eduForm, setEduForm] = useState(emptyEducation);
  const [editingEmpId, setEditingEmpId] = useState<string | null>(null);
  const [editingEduId, setEditingEduId] = useState<string | null>(null);
  const [profileForm, setProfileForm] = useState(emptyProfileForm);

  useEffect(() => {
    if (!profileDetails) return;
    setProfileForm({
      bio: profileDetails.bio || "",
      phone: profileDetails.phone || "",
      location: profileDetails.location || "",
      linkedin_url: profileDetails.linkedin_url || "",
      github_url: profileDetails.github_url || "",
      website_url: profileDetails.website_url || "",
      languages_spoken: profileDetails.languages_spoken || "",
      interests: profileDetails.interests || "",
      awards: (profileDetails.awards || []).join("\n"),
    });
  }, [profileDetails]);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await extractDraft.mutateAsync(file);
      const draft = result.employment[0];
      if (draft) {
        setEmpForm({
          title: draft.title || "",
          company: draft.company || "",
          start_date: draft.start_date || "",
          end_date: draft.end_date || "",
          description: draft.description || "",
          skills: (draft.skills || []).join(", "),
        });
        setEditingEmpId(null);
      }
      const eduDraft = result.education[0];
      if (eduDraft && !draft) {
        setEduForm({
          institution: eduDraft.institution || "",
          degree: eduDraft.degree || "",
          field_of_study: eduDraft.field_of_study || "",
          start_date: eduDraft.start_date || "",
          end_date: eduDraft.end_date || "",
          description: eduDraft.description || "",
        });
      }
    } finally {
      e.target.value = "";
    }
  };

  const startEditEmployment = (item: Employment) => {
    setEditingEmpId(item.id);
    setEmpForm({
      title: item.title,
      company: item.company,
      start_date: item.start_date,
      end_date: item.end_date || "",
      description: item.description || "",
      skills: (item.skills || []).join(", "),
    });
  };

  const startEditEducation = (item: Education) => {
    setEditingEduId(item.id);
    setEduForm({
      institution: item.institution,
      degree: item.degree,
      field_of_study: item.field_of_study || "",
      start_date: item.start_date,
      end_date: item.end_date || "",
      description: item.description || "",
    });
  };

  const submitEmployment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!empForm.title.trim() || !empForm.company.trim() || !empForm.start_date) return;
    const payload = {
      title: empForm.title.trim(),
      company: empForm.company.trim(),
      start_date: empForm.start_date,
      end_date: empForm.end_date || null,
      description: empForm.description,
      skills: empForm.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (editingEmpId) {
      await updateEmp.mutateAsync({ id: editingEmpId, ...payload });
    } else {
      await createEmp.mutateAsync(payload);
    }
    setEmpForm(emptyEmployment);
    setEditingEmpId(null);
  };

  const submitEducation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eduForm.institution.trim() || !eduForm.degree.trim() || !eduForm.start_date) return;
    const payload = {
      institution: eduForm.institution.trim(),
      degree: eduForm.degree.trim(),
      field_of_study: eduForm.field_of_study,
      start_date: eduForm.start_date,
      end_date: eduForm.end_date || null,
      description: eduForm.description,
    };
    if (editingEduId) {
      await updateEdu.mutateAsync({ id: editingEduId, ...payload });
    } else {
      await createEdu.mutateAsync(payload);
    }
    setEduForm(emptyEducation);
    setEditingEduId(null);
  };

  const submitProfileDetails = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateProfileDetails.mutateAsync({
      bio: profileForm.bio,
      phone: profileForm.phone,
      location: profileForm.location,
      linkedin_url: profileForm.linkedin_url,
      github_url: profileForm.github_url,
      website_url: profileForm.website_url,
      languages_spoken: profileForm.languages_spoken,
      interests: profileForm.interests,
      awards: profileForm.awards
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
    });
  };

  return (
    <div className="space-y-8 pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Career Experience</h1>
          <p className="text-sm text-gray-500">
            Track employment, education, and target roles — stored in your knowledge graph.
          </p>
        </div>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.docx"
            className="hidden"
            onChange={handleFileSelected}
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={extractDraft.isPending}
          >
            <Upload className="mr-2 h-4 w-4" />
            {extractDraft.isPending ? "Extracting…" : "Upload CV"}
          </Button>
        </div>
      </div>

      {summaryLoading ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Years of experience</p>
              <p className="text-3xl font-bold mt-1">{summary?.total_years_experience ?? 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Roles</p>
              <p className="text-3xl font-bold mt-1">{summary?.employment_count ?? 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Education</p>
              <p className="text-3xl font-bold mt-1">{summary?.education_count ?? 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Current</p>
              <p className="text-sm font-semibold mt-2 line-clamp-2">
                {summary?.current_title
                  ? `${summary.current_title} @ ${summary.current_company}`
                  : "—"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Contact className="h-5 w-5" />
            Contact &amp; Profile Details
          </CardTitle>
          <p className="text-sm text-gray-500">
            Shown on your generated CV header, Certifications &amp; Awards, and Additional
            Information sections.
          </p>
        </CardHeader>
        <CardContent>
          {profileLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <form onSubmit={submitProfileDetails} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Phone</Label>
                  <Input
                    value={profileForm.phone}
                    onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                    placeholder="(555) 123-4567"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Location</Label>
                  <Input
                    value={profileForm.location}
                    onChange={(e) => setProfileForm({ ...profileForm, location: e.target.value })}
                    placeholder="San Francisco, CA"
                  />
                </div>
                <div className="space-y-1">
                  <Label>LinkedIn URL</Label>
                  <Input
                    value={profileForm.linkedin_url}
                    onChange={(e) =>
                      setProfileForm({ ...profileForm, linkedin_url: e.target.value })
                    }
                    placeholder="https://linkedin.com/in/..."
                  />
                </div>
                <div className="space-y-1">
                  <Label>GitHub URL</Label>
                  <Input
                    value={profileForm.github_url}
                    onChange={(e) =>
                      setProfileForm({ ...profileForm, github_url: e.target.value })
                    }
                    placeholder="https://github.com/..."
                  />
                </div>
                <div className="space-y-1">
                  <Label>Personal Website</Label>
                  <Input
                    value={profileForm.website_url}
                    onChange={(e) =>
                      setProfileForm({ ...profileForm, website_url: e.target.value })
                    }
                    placeholder="https://..."
                  />
                </div>
                <div className="space-y-1">
                  <Label>Languages Spoken</Label>
                  <Input
                    value={profileForm.languages_spoken}
                    onChange={(e) =>
                      setProfileForm({ ...profileForm, languages_spoken: e.target.value })
                    }
                    placeholder="English (Native), Mandarin (Conversational)"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Interests</Label>
                <Input
                  value={profileForm.interests}
                  onChange={(e) => setProfileForm({ ...profileForm, interests: e.target.value })}
                  placeholder="Contributing to open source, technical writing, ..."
                />
              </div>
              <div className="space-y-1">
                <Label>Bio</Label>
                <Textarea
                  value={profileForm.bio}
                  onChange={(e) => setProfileForm({ ...profileForm, bio: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-1">
                <Label>Awards (one per line)</Label>
                <Textarea
                  value={profileForm.awards}
                  onChange={(e) => setProfileForm({ ...profileForm, awards: e.target.value })}
                  rows={3}
                  placeholder={"AWS Certified Solutions Architect - Associate (2023)\nEmployee of the Quarter (Q3 2022)"}
                />
              </div>
              <Button type="submit" disabled={updateProfileDetails.isPending}>
                {updateProfileDetails.isPending ? "Saving…" : "Save"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Briefcase className="h-5 w-5" />
              {editingEmpId ? "Edit Employment" : "Add Employment"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submitEmployment} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Title</Label>
                  <Input
                    value={empForm.title}
                    onChange={(e) => setEmpForm({ ...empForm, title: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <Label>Company</Label>
                  <Input
                    value={empForm.company}
                    onChange={(e) => setEmpForm({ ...empForm, company: e.target.value })}
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Start</Label>
                  <Input
                    type="date"
                    value={empForm.start_date}
                    onChange={(e) => setEmpForm({ ...empForm, start_date: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <Label>End (blank = current)</Label>
                  <Input
                    type="date"
                    value={empForm.end_date}
                    onChange={(e) => setEmpForm({ ...empForm, end_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Description</Label>
                <Textarea
                  value={empForm.description}
                  onChange={(e) => setEmpForm({ ...empForm, description: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="space-y-1">
                <Label>Skills (comma-separated)</Label>
                <Input
                  value={empForm.skills}
                  onChange={(e) => setEmpForm({ ...empForm, skills: e.target.value })}
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={createEmp.isPending || updateEmp.isPending}>
                  <Plus className="mr-2 h-4 w-4" />
                  {editingEmpId ? "Update" : "Add"}
                </Button>
                {editingEmpId && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setEditingEmpId(null);
                      setEmpForm(emptyEmployment);
                    }}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <GraduationCap className="h-5 w-5" />
              {editingEduId ? "Edit Education" : "Add Education"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submitEducation} className="space-y-3">
              <div className="space-y-1">
                <Label>Institution</Label>
                <Input
                  value={eduForm.institution}
                  onChange={(e) => setEduForm({ ...eduForm, institution: e.target.value })}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Degree</Label>
                  <Input
                    value={eduForm.degree}
                    onChange={(e) => setEduForm({ ...eduForm, degree: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <Label>Field</Label>
                  <Input
                    value={eduForm.field_of_study}
                    onChange={(e) => setEduForm({ ...eduForm, field_of_study: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Start</Label>
                  <Input
                    type="date"
                    value={eduForm.start_date}
                    onChange={(e) => setEduForm({ ...eduForm, start_date: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <Label>End</Label>
                  <Input
                    type="date"
                    value={eduForm.end_date}
                    onChange={(e) => setEduForm({ ...eduForm, end_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={createEdu.isPending || updateEdu.isPending}>
                  <Plus className="mr-2 h-4 w-4" />
                  {editingEduId ? "Update" : "Add"}
                </Button>
                {editingEduId && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setEditingEduId(null);
                      setEduForm(emptyEducation);
                    }}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Briefcase className="h-5 w-5" /> Employment history
        </h2>
        {empLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : employment && employment.length > 0 ? (
          <div className="space-y-3">
            {employment.map((item) => (
              <Card key={item.id}>
                <CardContent className="pt-4 flex justify-between gap-4">
                  <div>
                    <p className="font-semibold">{item.title}</p>
                    <p className="text-sm text-muted-foreground">{item.company}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {item.start_date} – {item.end_date || "Present"}
                    </p>
                    {item.description && (
                      <p className="text-sm mt-2 line-clamp-2">{item.description}</p>
                    )}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button variant="ghost" size="icon" onClick={() => startEditEmployment(item)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-600"
                      onClick={() => deleteEmp.mutate(item.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No employment entries yet.</p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <GraduationCap className="h-5 w-5" /> Education
        </h2>
        {eduLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : education && education.length > 0 ? (
          <div className="space-y-3">
            {education.map((item) => (
              <Card key={item.id}>
                <CardContent className="pt-4 flex justify-between gap-4">
                  <div>
                    <p className="font-semibold">{item.degree}</p>
                    <p className="text-sm text-muted-foreground">
                      {item.institution}
                      {item.field_of_study ? ` · ${item.field_of_study}` : ""}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {item.start_date} – {item.end_date || "Present"}
                    </p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button variant="ghost" size="icon" onClick={() => startEditEducation(item)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-600"
                      onClick={() => deleteEdu.mutate(item.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No education entries yet.</p>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Target className="h-5 w-5" /> Target roles
          </h2>
          <Button variant="outline" size="sm" asChild>
            <Link href="/skills">
              <Sparkles className="mr-2 h-4 w-4" />
              Set or refresh on Skills
            </Link>
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Read-only here — required skills are derived from real job postings sampled for
          each role. Add, refresh, or remove roles from the Skills page.
        </p>
        {rolesLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : roles && roles.length > 0 ? (
          <div className="flex flex-wrap gap-3">
            {roles.map((role) => (
              <Card key={role.id} className="min-w-[240px]">
                <CardContent className="pt-4 space-y-2">
                  <div>
                    <p className="font-semibold">{role.title}</p>
                    {role.location && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <MapPin className="h-3 w-3" /> {role.location}
                      </p>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {role.sample_status === "ready"
                      ? `${role.sample_job_count} offer${role.sample_job_count === 1 ? "" : "s"} sampled`
                      : role.sample_status === "error"
                        ? "Sample refresh failed"
                        : role.sample_status === "idle"
                          ? "Not sampled yet"
                          : "Sampling in progress…"}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {(role.required_skills || []).slice(0, 12).map((s) => (
                      <Badge key={s} variant="secondary" className="text-[10px]">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No target roles yet — add one from the Skills page.
          </p>
        )}
      </section>
    </div>
  );
}
