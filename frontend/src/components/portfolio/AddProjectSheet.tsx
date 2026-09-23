"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { Loader2, Upload, X, Check, Trash2, Plus } from "lucide-react";

import { PortfolioService } from "@/lib/api";
import { apiFetch } from "@/lib/apiFetch";
import { useUser } from "@/hooks/useAuth";
import { normalizeSkillDraft } from "@/hooks/usePortfolio";
import type { Project, ProjectDraft, ProjectStatus, SkillDraft, SkillLevel } from "@/types/portfolio";

const SKILL_LEVEL_OPTIONS: SkillLevel[] = ["beginner", "intermediate", "advanced", "expert"];

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function emptySkillDraft(name: string, level: SkillLevel): SkillDraft {
  return { name, canonical_name: null, category: "technical", level, confidence: 1.0 };
}

/**
 * Backend ProjectDraft fields with defaults are optional in the generated
 * OpenAPI type even though the API always populates them. Normalize to the
 * app's ProjectDraft shape so the editable draft state can rely on required
 * arrays.
 */
function normalizeDraft(draft: import("@/lib/api").ProjectDraft): ProjectDraft {
  return {
    title: draft.title,
    description: draft.description,
    skills: (draft.skills ?? []).map(normalizeSkillDraft),
    tech_stack: draft.tech_stack ?? [],
    start_date: draft.start_date ?? null,
    end_date: draft.end_date ?? null,
    media_urls: draft.media_urls ?? [],
    achievements: draft.achievements ?? [],
    seniority: draft.seniority ?? null,
    source: draft.source === "upload" ? "upload" : "form",
  };
}

const projectSchema = z.object({
  title: z.string().min(2, "Title is required"),
  description: z.string().min(10, "Description is too short"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().optional(),
  status: z.enum(["planned", "in_progress", "finished"]),
});

type ProjectFormValues = z.infer<typeof projectSchema>;

const SENIORITY_OPTIONS = ["junior", "mid", "senior", "lead"] as const;
const STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "in_progress", label: "In Progress" },
  { value: "finished", label: "Finished" },
];

interface AddProjectSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When set, the sheet edits an existing project instead of creating. */
  project?: Project | null;
}

export function AddProjectSheet({ open, onOpenChange, project = null }: AddProjectSheetProps) {
  const queryClient = useQueryClient();
  const { data: user } = useUser();
  const [file, setFile] = useState<File | null>(null);
  const [drafts, setDrafts] = useState<ProjectDraft[]>([]);
  const isEdit = Boolean(project?.id);

  // Manual-form skills: the user picks the name AND self-assesses the level
  // for each skill directly (replacing a free-text "tech stack" field).
  // Category and project seniority are still filled in automatically on save.
  const [formSkills, setFormSkills] = useState<SkillDraft[]>([]);
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillLevel, setNewSkillLevel] = useState<SkillLevel>("intermediate");

  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      title: "",
      description: "",
      start_date: new Date().toISOString().split('T')[0],
      end_date: "",
      status: "in_progress",
    },
  });

  React.useEffect(() => {
    if (!open) return;
    if (project) {
      form.reset({
        title: project.title,
        description: project.description,
        start_date: project.start_date,
        end_date: project.end_date || "",
        status: project.status || "in_progress",
      });
      setFormSkills(
        (project.skills && project.skills.length > 0
          ? project.skills
          : (project.tech_stack || []).map((name) => emptySkillDraft(name, "intermediate")))
      );
    } else {
      form.reset({
        title: "",
        description: "",
        start_date: new Date().toISOString().split("T")[0],
        end_date: "",
        status: "in_progress",
      });
      setFormSkills([]);
    }
  }, [open, project, form]);

  const invalidatePortfolioQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    queryClient.invalidateQueries({ queryKey: ["skills"] });
    queryClient.invalidateQueries({ queryKey: ["skill-analysis"] });
    queryClient.invalidateQueries({ queryKey: ["kg-stats"] });
    queryClient.invalidateQueries({ queryKey: ["kg-graph"] });
  };

  const createMutation = useMutation({
    mutationFn: (values: ProjectFormValues) => {
      const payload = {
        ...values,
        tech_stack: formSkills.map((s) => s.name),
        end_date: values.end_date || null,
        skills: formSkills,
        skip_enrichment: false,
        status: values.status,
      };
      if (isEdit && project?.id) {
        return apiFetch(`/api/v1/portfolio/${project.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            title: payload.title,
            description: payload.description,
            tech_stack: payload.tech_stack,
            start_date: payload.start_date,
            end_date: payload.end_date,
            status: payload.status,
          }),
        });
      }
      return apiFetch("/api/v1/portfolio/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      invalidatePortfolioQueries();
      onOpenChange(false);
      form.reset();
      setFormSkills([]);
      setNewSkillName("");
      setNewSkillLevel("intermediate");
    },
  });

  const extractMutation = useMutation({
    mutationFn: (file: File) => {
      return PortfolioService.uploadProjectDocumentApiV1PortfolioUploadPost({
        file: file as any
      });
    },
    onSuccess: (response) => {
      setDrafts((response.drafts ?? []).map(normalizeDraft));
      setFile(null);
    },
  });

  // Keyed by draft index so multiple drafts (e.g. from a CV) can be
  // confirmed/discarded independently.
  const confirmMutation = useMutation({
    mutationFn: ({ draft }: { index: number; draft: ProjectDraft }) => {
      const payload = {
        title: draft.title,
        description: draft.description,
        tech_stack: draft.skills.map((s) => s.canonical_name || s.name),
        start_date: draft.start_date || new Date().toISOString().split('T')[0],
        end_date: draft.end_date || null,
        media_urls: draft.media_urls,
        seniority: draft.seniority,
        achievements: draft.achievements,
        skills: draft.skills,
        skip_enrichment: true,
        status: "finished" as const,
      };
      return apiFetch("/api/v1/portfolio/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (_data, { index }) => {
      invalidatePortfolioQueries();
      setDrafts((prev) => prev.filter((_, i) => i !== index));
    },
  });

  const onSubmit = (values: ProjectFormValues) => {
    createMutation.mutate(values);
  };

  const handleFileUpload = () => {
    if (file) {
      extractMutation.mutate(file);
    }
  };

  const addFormSkill = () => {
    const name = newSkillName.trim();
    if (!name) return;
    if (formSkills.some((s) => s.name.toLowerCase() === name.toLowerCase())) {
      setNewSkillName("");
      return;
    }
    setFormSkills((prev) => [...prev, emptySkillDraft(name, newSkillLevel)]);
    setNewSkillName("");
    setNewSkillLevel("intermediate");
  };

  const removeFormSkill = (index: number) => {
    setFormSkills((prev) => prev.filter((_, i) => i !== index));
  };

  const updateFormSkillLevel = (index: number, level: SkillLevel) => {
    setFormSkills((prev) => prev.map((s, i) => (i === index ? { ...s, level } : s)));
  };

  const updateDraft = (index: number, patch: Partial<ProjectDraft>) => {
    setDrafts((prev) => prev.map((d, i) => (i === index ? { ...d, ...patch } : d)));
  };

  const removeDraftSkill = (index: number, skillIndex: number) => {
    setDrafts((prev) =>
      prev.map((d, i) =>
        i === index
          ? { ...d, skills: d.skills.filter((_, si) => si !== skillIndex) }
          : d
      )
    );
  };

  const updateDraftSkillLevel = (index: number, skillIndex: number, level: SkillLevel) => {
    setDrafts((prev) =>
      prev.map((d, i) =>
        i === index
          ? {
              ...d,
              skills: d.skills.map((s, si) => (si === skillIndex ? { ...s, level } : s)),
            }
          : d
      )
    );
  };

  const discardDraft = (index: number) => {
    setDrafts((prev) => prev.filter((_, i) => i !== index));
  };

  const isPending = createMutation.isPending || extractMutation.isPending;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[500px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{isEdit ? "Edit Project" : "Add Project"}</SheetTitle>
          <SheetDescription>
            {isEdit
              ? "Update project details and status. Skills count toward your skillset only when status is Finished."
              : "Add a new project to your portfolio or upload a document to auto-extract projects."}
          </SheetDescription>
        </SheetHeader>

        <div className="grid gap-6 py-6">
          {!isEdit && (
            <div className="space-y-4 rounded-lg border border-dashed p-4">
              <Label>Quick Extract from Document</Label>
              <div className="flex items-center gap-4">
                <Input
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="cursor-pointer"
                />
                <Button
                  onClick={handleFileUpload}
                  disabled={!file || isPending}
                  size="sm"
                  variant="outline"
                >
                  {extractMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4 mr-2" />
                  )}
                  Extract
                </Button>
              </div>
              <p className="text-[10px] text-gray-500">
                Supported: PDF, DOCX, TXT. A CV may yield several projects &mdash; review and
                confirm each one below before it is saved.
              </p>
            </div>
          )}

          {!isEdit && drafts.length > 0 && (
            <div className="space-y-4">
              {drafts.map((draft, index) => (
                <div key={index} className="space-y-3 rounded-lg border p-4">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs uppercase tracking-wide text-gray-500">
                      Extracted draft {index + 1} of {drafts.length}
                    </Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => discardDraft(index)}
                      disabled={confirmMutation.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label>Title</Label>
                    <Input
                      value={draft.title}
                      onChange={(e) => updateDraft(index, { title: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Description</Label>
                    <Textarea
                      value={draft.description}
                      onChange={(e) => updateDraft(index, { description: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Skills</Label>
                    <p className="text-[10px] text-gray-500">
                      Levels are assessed automatically &mdash; adjust any that don&apos;t look right.
                    </p>
                    <div className="space-y-1.5">
                      {draft.skills.length === 0 && (
                        <span className="text-xs text-gray-500">No skills detected.</span>
                      )}
                      {draft.skills.map((skill: SkillDraft, skillIndex: number) => (
                        <div
                          key={skillIndex}
                          className="flex items-center gap-2 rounded-md border px-2 py-1.5"
                        >
                          <div className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">
                              {skill.canonical_name || skill.name}
                            </span>
                            <span className="text-[10px] text-gray-500">{skill.category}</span>
                          </div>
                          <Select
                            value={skill.level}
                            onValueChange={(value) =>
                              updateDraftSkillLevel(index, skillIndex, value as SkillLevel)
                            }
                          >
                            <SelectTrigger className="h-8 w-[125px] shrink-0">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {SKILL_LEVEL_OPTIONS.map((level) => (
                                <SelectItem key={level} value={level}>
                                  {capitalize(level)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <button
                            type="button"
                            onClick={() => removeDraftSkill(index, skillIndex)}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Start Date</Label>
                      <Input
                        type="date"
                        value={draft.start_date ?? ""}
                        onChange={(e) => updateDraft(index, { start_date: e.target.value || null })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>End Date</Label>
                      <Input
                        type="date"
                        value={draft.end_date ?? ""}
                        onChange={(e) => updateDraft(index, { end_date: e.target.value || null })}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Seniority</Label>
                    <Select
                      value={draft.seniority ?? "none"}
                      onValueChange={(value) =>
                        updateDraft(index, { seniority: value === "none" ? null : value })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Not assessed" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Not assessed</SelectItem>
                        {SENIORITY_OPTIONS.map((level) => (
                          <SelectItem key={level} value={level}>
                            {level.charAt(0).toUpperCase() + level.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {draft.achievements.length > 0 && (
                    <div className="space-y-1">
                      <Label>Achievements</Label>
                      <ul className="list-disc pl-4 text-xs text-gray-600">
                        {draft.achievements.map((achievement, i) => (
                          <li key={i}>{achievement}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <Button
                    type="button"
                    size="sm"
                    className="w-full"
                    onClick={() => confirmMutation.mutate({ index, draft })}
                    disabled={confirmMutation.isPending}
                  >
                    {confirmMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="mr-2 h-4 w-4" />
                    )}
                    Confirm &amp; Save Project
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-gray-500">Or Manual Entry</span>
            </div>
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Project Title</Label>
              <Input id="title" {...form.register("title")} placeholder="e.g. Personal Portfolio" />
              {form.formState.errors.title && <p className="text-xs text-red-500">{form.formState.errors.title.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" {...form.register("description")} placeholder="Describe what you built..." />
              {form.formState.errors.description && <p className="text-xs text-red-500">{form.formState.errors.description.message}</p>}
            </div>

            <div className="space-y-2">
              <Label>Skills</Label>
              <div className="space-y-1.5">
                {formSkills.length === 0 && (
                  <p className="text-xs text-gray-500">
                    Add each skill you used and rate your own proficiency with it.
                  </p>
                )}
                {formSkills.map((skill, index) => (
                  <div key={index} className="flex items-center gap-2 rounded-md border px-2 py-1.5">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{skill.name}</span>
                    <Select
                      value={skill.level}
                      onValueChange={(value) => updateFormSkillLevel(index, value as SkillLevel)}
                    >
                      <SelectTrigger className="h-8 w-[125px] shrink-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SKILL_LEVEL_OPTIONS.map((level) => (
                          <SelectItem key={level} value={level}>
                            {capitalize(level)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <button type="button" onClick={() => removeFormSkill(index)}>
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <Input
                  placeholder="e.g. React"
                  value={newSkillName}
                  onChange={(e) => setNewSkillName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addFormSkill();
                    }
                  }}
                  className="flex-1"
                />
                <Select value={newSkillLevel} onValueChange={(value) => setNewSkillLevel(value as SkillLevel)}>
                  <SelectTrigger className="h-9 w-[125px] shrink-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SKILL_LEVEL_OPTIONS.map((level) => (
                      <SelectItem key={level} value={level}>
                        {capitalize(level)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button type="button" size="sm" variant="outline" onClick={addFormSkill}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-[10px] text-gray-500">
                Skill categories and project seniority are assessed automatically on save.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <Select
                value={form.watch("status")}
                onValueChange={(v) => form.setValue("status", v as ProjectStatus)}
              >
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[10px] text-gray-500">
                Skills from Planned / In Progress projects are not added to your verified skillset until Finished.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_date">Start Date</Label>
                <Input id="start_date" type="date" {...form.register("start_date")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_date">End Date (Optional)</Label>
                <Input id="end_date" type="date" {...form.register("end_date")} />
              </div>
            </div>

            <SheetFooter className="pt-4">
              <Button type="submit" disabled={isPending} className="w-full">
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Project
              </Button>
            </SheetFooter>
          </form>
        </div>
      </SheetContent>
    </Sheet>
  );
}
