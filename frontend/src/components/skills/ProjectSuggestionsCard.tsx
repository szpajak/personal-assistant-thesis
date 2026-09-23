"use client";

import React from "react";
import { SuggestedProject } from "@/types/skills";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Laptop, Loader2, Plus, ChevronDown, ChevronUp, Check } from "lucide-react";
import { useCreateProjectFromSuggestion } from "@/hooks/usePortfolio";
import { useToast } from "@/components/ui/use-toast";

interface ProjectSuggestionsCardProps {
  projects: SuggestedProject[];
  includedTitles?: string[];
  onToggleInclude?: (title: string) => void;
}

function ProjectBrief({ project }: { project: SuggestedProject }) {
  const [expanded, setExpanded] = React.useState(false);
  const keySteps = project.key_steps || [];
  const deliverables = project.deliverables || [];
  const hasDetails = keySteps.length > 0 || deliverables.length > 0;

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{project.description}</p>
      {hasDetails && (
        <>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-muted-foreground"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? (
              <>
                <ChevronUp className="mr-1 h-3 w-3" /> Hide plan
              </>
            ) : (
              <>
                <ChevronDown className="mr-1 h-3 w-3" /> View steps & deliverables
              </>
            )}
          </Button>
          {expanded && (
            <div className="space-y-3 text-sm">
              {keySteps.length > 0 && (
                <div>
                  <p className="font-medium mb-1">Key steps</p>
                  <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                    {keySteps.map((step, index) => (
                      <li key={`${project.title}-step-${index}`}>{step}</li>
                    ))}
                  </ol>
                </div>
              )}
              {deliverables.length > 0 && (
                <div>
                  <p className="font-medium mb-1">Deliverables / outcome</p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                    {deliverables.map((item, index) => (
                      <li key={`${project.title}-deliv-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function ProjectSuggestionsCard({
  projects,
  includedTitles = [],
  onToggleInclude,
}: ProjectSuggestionsCardProps) {
  const { toast } = useToast();
  const startMutation = useCreateProjectFromSuggestion();
  const [pendingTitle, setPendingTitle] = React.useState<string | null>(null);
  const includedSet = React.useMemo(() => new Set(includedTitles), [includedTitles]);

  if (!projects || projects.length === 0) return null;

  return (
    <Card className="w-full border-emerald-200 bg-emerald-50/40">
      <CardHeader>
        <CardTitle className="text-2xl font-bold flex items-center gap-2">
          <Laptop className="h-5 w-5" />
          Suggested Projects
        </CardTitle>
        <CardDescription>
          Portfolio briefs with steps and deliverables that batch related skill gaps.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project, index) => (
            <div
              key={`${project.title}-${index}`}
              className="flex flex-col p-4 rounded-xl border bg-card"
            >
              <h4 className="font-bold mb-2">{project.title}</h4>
              <div className="mb-3 flex-1">
                <ProjectBrief project={project} />
              </div>
              <div className="flex flex-wrap gap-1 mb-4">
                {(project.skills_covered || project.tech_stack || []).map((skill) => (
                  <Badge key={skill} variant="secondary" className="text-[10px]">
                    {skill}
                  </Badge>
                ))}
              </div>
              <div className="mt-auto flex items-center gap-2">
                {onToggleInclude && (
                  <Button
                    size="sm"
                    variant={includedSet.has(project.title) ? "secondary" : "outline"}
                    className="gap-1"
                    onClick={() => onToggleInclude(project.title)}
                  >
                    {includedSet.has(project.title) ? (
                      <>
                        <Check className="h-3 w-3" /> In roadmap
                      </>
                    ) : (
                      "Include in roadmap"
                    )}
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="gap-1"
                  disabled={startMutation.isPending && pendingTitle === project.title}
                  onClick={() => {
                    setPendingTitle(project.title);
                    startMutation.mutate(project, {
                      onSuccess: () => {
                        toast({
                          title: "Project added",
                          description: "Saved as Planned in your portfolio.",
                        });
                      },
                      onSettled: () => setPendingTitle(null),
                    });
                  }}
                >
                  {startMutation.isPending && pendingTitle === project.title ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Plus className="h-3 w-3" />
                  )}
                  Start Project
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
