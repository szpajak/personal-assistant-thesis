"use client";

import { 
  FolderKanban, 
  BarChart2, 
  Mail, 
  Briefcase,
  AlertCircle,
  ArrowRight
} from "lucide-react";
import { useKGStats } from "@/hooks/useKG";
import { useApplications } from "@/hooks/useApplications";
import { useSkillAnalysis } from "@/hooks/useSkills";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";
import { SkillAnalysis } from "@/types/skills";
import { Application } from "@/types/applications";
import { Button } from "@/components/ui/button";
import { useUser } from "@/hooks/useAuth";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useKGStats();
  const { data: applications, isLoading: appsLoading } = useApplications();
  const { data: rawAnalysis, isLoading: analysisLoading } = useSkillAnalysis();
  const { data: user } = useUser();
  const analysis = rawAnalysis as SkillAnalysis | undefined;

  const firstName = user?.full_name?.split(" ")[0] || "";

  const statCards = [
    { 
      name: "Active Projects", 
      value: stats?.active_projects ?? 0, 
      icon: FolderKanban, 
      color: "border-l-blue-500",
      href: "/portfolio"
    },
    { 
      name: "Skills Tracked", 
      value: stats?.skills_tracked ?? 0, 
      icon: BarChart2, 
      color: "border-l-green-500",
      href: "/skills"
    },
    { 
      name: "Open Applications", 
      value: stats?.open_applications ?? 0, 
      icon: Mail, 
      color: "border-l-amber-500",
      href: "/applications"
    },
    { 
      name: "New Job Matches", 
      value: stats?.job_matches ?? 0, 
      icon: Briefcase, 
      color: "border-l-purple-500",
      href: "/jobs"
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {firstName ? `Welcome back, ${firstName}!` : "Dashboard"}
        </h1>
        <p className="text-sm text-gray-500">Overview of your professional knowledge graph.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Link key={card.name} href={card.href}>
            <Card className={`border-l-4 ${card.color} hover:shadow-md transition-shadow`}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
                  {card.name}
                </CardTitle>
                <card.icon className="h-4 w-4 text-gray-400" />
              </CardHeader>
              <CardContent>
                {statsLoading ? (
                  <Skeleton className="h-9 w-16" />
                ) : (
                  <div className="text-3xl font-bold">{card.value}</div>
                )}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
              Recent Applications
            </CardTitle>
          </CardHeader>
          <CardContent>
            {appsLoading ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : applications && applications.length > 0 ? (
              <div className="space-y-4">
                {[...applications]
                  .sort((a, b) => {
                    const aTime = a.applied_at ? new Date(a.applied_at).getTime() : 0;
                    const bTime = b.applied_at ? new Date(b.applied_at).getTime() : 0;
                    return bTime - aTime;
                  })
                  .slice(0, 5)
                  .map((app: Application) => {
                    const title = app.job_offer?.title?.trim() || "Untitled role";
                    const company = app.job_offer?.company?.trim();
                    return (
                      <div key={app.id} className="flex items-center justify-between border-b pb-3 last:border-0 last:pb-0">
                        <div className="min-w-0 pr-3">
                          <p className="text-sm font-semibold truncate">{title}</p>
                          <p className="text-xs text-gray-500 truncate">
                            {company ? `${company} · ` : ""}
                            {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "N/A"}
                          </p>
                        </div>
                        <Badge variant={app.status.toLowerCase() === "rejected" ? "destructive" : "secondary"}>
                          {app.status}
                        </Badge>
                      </div>
                    );
                  })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <Mail className="h-8 w-8 text-gray-300 mb-2" />
                <p className="text-sm text-gray-500">No applications yet</p>
                <Button variant="outline" size="sm" className="mt-4" asChild>
                  <Link href="/jobs">Find Jobs</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
              Top Skill Gaps
            </CardTitle>
          </CardHeader>
          <CardContent>
            {analysisLoading ? (
              <div className="flex flex-wrap gap-2">
                {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-6 w-20" />)}
              </div>
            ) : analysis?.skill_gaps && analysis.skill_gaps.length > 0 ? (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {analysis.skill_gaps.slice(0, 5).map((gap) => (
                    <Badge key={gap.skill} variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                      {gap.skill}
                    </Badge>
                  ))}
                </div>
                <Button variant="ghost" size="sm" className="w-full justify-between" asChild>
                  <Link href="/skills">
                    View full analysis
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <AlertCircle className="h-8 w-8 text-gray-300 mb-2" />
                <p className="text-sm text-gray-500">No skill gaps identified</p>
                <Button variant="outline" size="sm" className="mt-4" asChild>
                  <Link href="/skills">Check Skills</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
