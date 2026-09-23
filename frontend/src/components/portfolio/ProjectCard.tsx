"use client";

import { Calendar, Pencil, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Project, ProjectStatus } from "@/types/portfolio";

const STATUS_STYLES: Record<ProjectStatus, string> = {
  planned: "bg-slate-100 text-slate-700 border-slate-200",
  in_progress: "bg-amber-100 text-amber-800 border-amber-200",
  finished: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

const STATUS_LABELS: Record<ProjectStatus, string> = {
  planned: "Planned",
  in_progress: "In Progress",
  finished: "Finished",
};

interface ProjectCardProps {
  project: Project;
  onEdit?: (project: Project) => void;
  onDelete?: (projectId: string) => void;
  isDeleting?: boolean;
}

export function ProjectCard({
  project,
  onEdit,
  onDelete,
  isDeleting,
}: ProjectCardProps) {
  const status: ProjectStatus = project.status || "in_progress";

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      year: "numeric",
    });
  };

  return (
    <Card className="flex flex-col h-full overflow-hidden transition-all hover:shadow-md">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-xl font-bold line-clamp-1">
            {project.title}
          </CardTitle>
          <Badge className={STATUS_STYLES[status]}>
            {STATUS_LABELS[status]}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex-1 pb-2">
        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
          {project.description}
        </p>
        <div className="flex flex-wrap gap-1 mb-4">
          {project.tech_stack.slice(0, 5).map((tech) => (
            <Badge
              key={tech}
              variant="secondary"
              className="text-[10px] px-1.5 py-0"
            >
              {tech}
            </Badge>
          ))}
          {project.tech_stack.length > 5 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
              +{project.tech_stack.length - 5}
            </Badge>
          )}
        </div>
      </CardContent>
      <CardFooter className="pt-0 border-t bg-muted/50 py-3 mt-auto flex items-center justify-between gap-2">
        <div className="flex items-center text-xs text-muted-foreground">
          <Calendar className="mr-1 h-3 w-3" />
          <span>
            {formatDate(project.start_date)} –{" "}
            {project.end_date ? formatDate(project.end_date) : "Present"}
          </span>
        </div>
        <div className="flex gap-1">
          {onEdit && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => onEdit(project)}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          )}
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-red-600"
              disabled={isDeleting}
              onClick={() => onDelete(project.id)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
