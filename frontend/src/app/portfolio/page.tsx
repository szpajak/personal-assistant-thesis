"use client";

import { useDeleteProject, usePortfolioProjects } from "@/hooks/usePortfolio";
import { ProjectCard } from "@/components/portfolio/ProjectCard";
import { PortfolioEmptyState } from "@/components/portfolio/PortfolioEmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useState } from "react";
import { AddProjectSheet } from "@/components/portfolio/AddProjectSheet";
import { Project, ProjectStatus } from "@/types/portfolio";

const STATUS_FILTERS: { value: ProjectStatus | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "planned", label: "Planned" },
  { value: "in_progress", label: "In Progress" },
  { value: "finished", label: "Finished" },
];

export default function PortfolioPage() {
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | "">("");
  const { data: projects, isLoading } = usePortfolioProjects(statusFilter);
  const deleteProject = useDeleteProject();
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const openCreate = () => {
    setEditingProject(null);
    setIsSheetOpen(true);
  };

  const openEdit = (project: Project) => {
    setEditingProject(project);
    setIsSheetOpen(true);
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Portfolio</h1>
          <p className="text-sm text-gray-500">
            Manage your professional projects and achievements.
          </p>
        </div>
        <Button
          onClick={openCreate}
          className="bg-gray-900 text-white hover:bg-gray-700"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Project
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((filter) => (
          <Button
            key={filter.label}
            size="sm"
            variant={statusFilter === filter.value ? "default" : "outline"}
            onClick={() => setStatusFilter(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-[200px] w-full rounded-xl" />
          ))}
        </div>
      ) : projects && projects.length > 0 ? (
        <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-3">
          {projects.map((project: Project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={openEdit}
              onDelete={(id) => {
                setPendingDeleteId(id);
                deleteProject.mutate(id, {
                  onSettled: () => setPendingDeleteId(null),
                });
              }}
              isDeleting={
                deleteProject.isPending && pendingDeleteId === project.id
              }
            />
          ))}
        </div>
      ) : (
        <PortfolioEmptyState onAddClick={openCreate} />
      )}

      <AddProjectSheet
        open={isSheetOpen}
        onOpenChange={(open) => {
          setIsSheetOpen(open);
          if (!open) setEditingProject(null);
        }}
        project={editingProject}
      />
    </div>
  );
}
