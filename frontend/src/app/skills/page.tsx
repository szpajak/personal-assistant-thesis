"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useSkills,
  useSkillAnalysis,
  useMarketDemand,
  useCachedSuggestedProjects,
  useCachedLearningRoadmap,
  regenerateSuggestedProjects,
  generateLearningRoadmap,
} from "@/hooks/useSkills";
import { useTargetRoles } from "@/hooks/useProfile";
import { MySkillsPanel } from "@/components/skills/MySkillsPanel";
import { MarketDemandPanel } from "@/components/skills/MarketDemandPanel";
import { SkillGapAnalysis } from "@/components/skills/SkillGapAnalysis";
import { SkillsToLearnPanel } from "@/components/skills/SkillsToLearnPanel";
import { TargetRoleManager } from "@/components/skills/TargetRoleManager";
import { ProjectSuggestionsCard } from "@/components/skills/ProjectSuggestionsCard";
import { LearningRoadmapCard } from "@/components/skills/LearningRoadmapCard";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/use-toast";
import type { LearningRoadmap, SuggestedProject } from "@/types/skills";

function dedupe(names: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const name of names) {
    const trimmed = name.trim();
    const key = trimmed.toLowerCase();
    if (!trimmed || seen.has(key)) continue;
    seen.add(key);
    out.push(trimmed);
  }
  return out;
}

export default function SkillsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: skills, isLoading: skillsLoading } = useSkills();
  const { data: targetRoles } = useTargetRoles();
  const [targetRoleId, setTargetRoleId] = useState<string | null>(null);

  const { data: analysis, isFetching: analysisLoading } = useSkillAnalysis(targetRoleId);
  const { data: marketDemand, isLoading: demandLoading } = useMarketDemand(20, targetRoleId);
  const { data: projectsCache } = useCachedSuggestedProjects();
  const { data: roadmapCache } = useCachedLearningRoadmap();

  const selectedRole = useMemo(
    () => (targetRoleId ? targetRoles?.find((r) => r.id === targetRoleId) ?? null : null),
    [targetRoles, targetRoleId]
  );

  // Re-fetch gaps/demand once a role's market sample finishes (transitions
  // out of scraping/ingesting) instead of waiting on the poll interval.
  const lastRoleStatus = useRef<string | null>(null);
  useEffect(() => {
    const status = selectedRole?.sample_status ?? null;
    if (lastRoleStatus.current !== null && status !== lastRoleStatus.current) {
      queryClient.invalidateQueries({ queryKey: ["skill-analysis", targetRoleId] });
      queryClient.invalidateQueries({ queryKey: ["market-demand"] });
    }
    lastRoleStatus.current = status;
  }, [selectedRole?.sample_status, targetRoleId, queryClient]);

  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [suggestedProjects, setSuggestedProjects] = useState<SuggestedProject[] | null>(null);
  const [roadmap, setRoadmap] = useState<LearningRoadmap | null>(null);
  const [includedProjectTitles, setIncludedProjectTitles] = useState<string[]>([]);
  const [isRefreshingProjects, setIsRefreshingProjects] = useState(false);
  const [isGeneratingRoadmap, setIsGeneratingRoadmap] = useState(false);

  const ownedSkillNames = useMemo(
    () => new Set((skills || []).map((s) => s.name.toLowerCase())),
    [skills]
  );

  const effectiveProjects = suggestedProjects ?? projectsCache?.suggested_projects ?? [];
  const effectiveRoadmap = roadmap ?? roadmapCache?.roadmap ?? null;

  const addSkill = (skill: string) => {
    const trimmed = skill.trim();
    if (!trimmed) return;
    setSelectedSkills((current) => dedupe([...current, trimmed]));
  };

  const removeSkill = (skill: string) => {
    setSelectedSkills((current) =>
      current.filter((item) => item.toLowerCase() !== skill.toLowerCase())
    );
    setIncludedProjectTitles((current) => current);
  };

  const toggleIncludedProject = (title: string) => {
    setIncludedProjectTitles((current) =>
      current.includes(title) ? current.filter((t) => t !== title) : [...current, title]
    );
  };

  const handleRefreshProjects = async () => {
    if (selectedSkills.length < 2) {
      toast({
        title: "Select more skills",
        description: "Choose at least 2 skills to regenerate projects.",
        variant: "destructive",
      });
      return;
    }
    setIsRefreshingProjects(true);
    try {
      const projects = await regenerateSuggestedProjects(selectedSkills);
      setSuggestedProjects(projects);
      setIncludedProjectTitles([]);
      await queryClient.invalidateQueries({ queryKey: ["suggested-projects-cache"] });
      toast({
        title: "Projects updated",
        description: `Generated ${projects.length} project brief${projects.length === 1 ? "" : "s"}.`,
      });
    } catch (error) {
      toast({
        title: "Could not regenerate projects",
        description: error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsRefreshingProjects(false);
    }
  };

  const handleGenerateRoadmap = async () => {
    if (selectedSkills.length === 0) return;
    setIsGeneratingRoadmap(true);
    try {
      const includedProjects = effectiveProjects.filter((p) =>
        includedProjectTitles.includes(p.title)
      );
      const generated = await generateLearningRoadmap(
        selectedSkills,
        targetRoleId,
        includedProjects
      );
      setRoadmap(generated);
      await queryClient.invalidateQueries({ queryKey: ["learning-roadmap-cache"] });
      toast({
        title: "Roadmap generated",
        description: `${generated.phases.length} phase${generated.phases.length === 1 ? "" : "s"} · ${generated.overall_duration || "no estimate"}.`,
      });
    } catch (error) {
      toast({
        title: "Could not generate roadmap",
        description: error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsGeneratingRoadmap(false);
    }
  };

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Knowledge & Skills</h1>
        <p className="text-sm text-gray-500">
          Benchmark your expertise against real market data and build a learning roadmap.
        </p>
      </div>

      <TargetRoleManager selectedRoleId={targetRoleId} onSelectRole={setTargetRoleId} />

      <div className="grid gap-8 lg:grid-cols-2">
        {skillsLoading ? (
          <Skeleton className="h-[400px] w-full rounded-xl" />
        ) : (
          <MySkillsPanel skills={skills || []} />
        )}

        {demandLoading ? (
          <Skeleton className="h-[400px] w-full rounded-xl" />
        ) : (
          <MarketDemandPanel
            demands={marketDemand || []}
            subtitle={
              selectedRole
                ? `Skills in ${selectedRole.sample_job_count} "${selectedRole.title}" offer${selectedRole.sample_job_count === 1 ? "" : "s"}.`
                : "Top skills across saved market offers."
            }
            selectedSkills={selectedSkills}
            onAddSkill={(skill) => {
              if (ownedSkillNames.has(skill.toLowerCase())) return;
              addSkill(skill);
            }}
          />
        )}
      </div>

      <hr className="border-gray-200" />

      <div className="grid gap-6 lg:grid-cols-2">
        {analysisLoading && !analysis ? (
          <Skeleton className="h-[300px] w-full rounded-xl" />
        ) : (
          <SkillGapAnalysis
            analysis={analysis}
            isLoading={analysisLoading}
            selectedSkills={selectedSkills}
            onAddSkill={addSkill}
          />
        )}

        <SkillsToLearnPanel
          skills={selectedSkills}
          onAdd={addSkill}
          onRemove={removeSkill}
          onRefreshProjects={handleRefreshProjects}
          isRefreshingProjects={isRefreshingProjects}
          onGenerateRoadmap={handleGenerateRoadmap}
          isGeneratingRoadmap={isGeneratingRoadmap}
        />
      </div>

      {effectiveProjects.length > 0 && (
        <ProjectSuggestionsCard
          projects={effectiveProjects}
          includedTitles={includedProjectTitles}
          onToggleInclude={toggleIncludedProject}
        />
      )}

      {effectiveRoadmap && <LearningRoadmapCard roadmap={effectiveRoadmap} />}
    </div>
  );
}
