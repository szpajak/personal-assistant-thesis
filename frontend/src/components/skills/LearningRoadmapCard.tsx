"use client";

import React from "react";
import { LearningRoadmap } from "@/types/skills";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Clock, Laptop, ListChecks, Loader2, Plus } from "lucide-react";
import { useCreateProjectFromPlan } from "@/hooks/usePortfolio";
import { useToast } from "@/components/ui/use-toast";

interface LearningRoadmapCardProps {
  roadmap: LearningRoadmap;
}

export const LearningRoadmapCard: React.FC<LearningRoadmapCardProps> = ({
  roadmap,
}) => {
  const { toast } = useToast();
  const startMutation = useCreateProjectFromPlan();
  const [pendingIndex, setPendingIndex] = React.useState<number | null>(null);

  if (!roadmap || !roadmap.phases || roadmap.phases.length === 0) return null;

  const startPhase = (index: number) => {
    const phase = roadmap.phases[index];
    setPendingIndex(index);
    startMutation.mutate(
      {
        title: phase.title,
        description: [phase.goal, ...(phase.concepts || [])]
          .filter(Boolean)
          .join("\n"),
        skill_name: phase.concepts?.[0] || "",
      },
      {
        onSuccess: () => {
          toast({
            title: "Project started!",
            description: "Added to your portfolio as an in-progress project.",
          });
        },
        onSettled: () => setPendingIndex(null),
      },
    );
  };

  return (
    <Card className="w-full border-primary/20 bg-primary/5">
      <CardHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-2xl font-bold">
              Personalized Learning Roadmap
            </CardTitle>
            {roadmap.overview && (
              <CardDescription>{roadmap.overview}</CardDescription>
            )}
          </div>
          {roadmap.overall_duration && (
            <div className="flex items-center gap-1.5 text-sm font-medium bg-background px-3 py-1 rounded-full border shadow-sm shrink-0">
              <Clock className="h-4 w-4 text-primary" />
              {roadmap.overall_duration}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-6 border-l-2 border-primary/20 pl-6">
          {roadmap.phases.map((phase, index) => (
            <li key={`${phase.title}-${index}`} className="relative">
              <span className="absolute -left-[31px] flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                {index + 1}
              </span>
              <div className="rounded-xl border bg-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-bold">{phase.title}</h4>
                  {phase.duration && (
                    <Badge variant="outline" className="text-[10px] gap-1">
                      <Clock className="h-3 w-3" /> {phase.duration}
                    </Badge>
                  )}
                </div>
                {phase.goal && (
                  <p className="text-sm text-muted-foreground mt-1">
                    {phase.goal}
                  </p>
                )}

                {phase.concepts && phase.concepts.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {phase.concepts.map((concept) => (
                      <Badge
                        key={concept}
                        variant="secondary"
                        className="text-[10px]"
                      >
                        {concept}
                      </Badge>
                    ))}
                  </div>
                )}

                {phase.steps && phase.steps.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold flex items-center gap-1 mb-1 text-muted-foreground">
                      <ListChecks className="h-3 w-3" /> Steps
                    </p>
                    <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
                      {phase.steps.map((step, stepIndex) => (
                        <li key={`${phase.title}-step-${stepIndex}`}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {phase.project_title && (
                  <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald-700">
                    <Laptop className="h-3.5 w-3.5" />
                    Includes project:{" "}
                    <span className="font-medium">{phase.project_title}</span>
                  </div>
                )}

                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-3 h-8 gap-1 text-xs"
                  onClick={() => startPhase(index)}
                  disabled={startMutation.isPending && pendingIndex === index}
                >
                  {startMutation.isPending && pendingIndex === index ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Plus className="h-3 w-3" />
                  )}
                  Start as project
                </Button>
              </div>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
};
