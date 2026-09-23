"use client"

import React from "react"
import { SkillAnalysis } from "@/types/skills"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, Check, Plus } from "lucide-react"

interface SkillGapAnalysisProps {
  analysis?: SkillAnalysis
  isLoading?: boolean
  selectedSkills: string[]
  onAddSkill: (skill: string) => void
}

export const SkillGapAnalysis: React.FC<SkillGapAnalysisProps> = ({
  analysis,
  isLoading = false,
  selectedSkills,
  onAddSkill,
}) => {
  const skillGaps = analysis?.skill_gaps ?? []
  const coreStrengths = analysis?.core_strengths ?? []
  const selectedKeys = React.useMemo(
    () => new Set(selectedSkills.map((s) => s.toLowerCase())),
    [selectedSkills]
  )

  const waitingOnSample =
    !!analysis && !analysis.target_role_ready && analysis.sample_status !== "error"
  const sampleFailed = !!analysis && analysis.sample_status === "error"

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xl font-bold">Skill Gap Analysis</CardTitle>
        <AlertTriangle className="h-4 w-4 text-amber-500" />
      </CardHeader>
      <CardContent className="space-y-5">
        {analysis?.error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Analysis could not be completed. Please try again.
          </div>
        )}

        {sampleFailed && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            The market sample for &quot;{analysis?.target_role_title}&quot; failed to refresh.
            Try refreshing it again from the Target roles panel above.
          </div>
        )}

        {waitingOnSample && !sampleFailed && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Sampling market offers for &quot;{analysis?.target_role_title}&quot;
            {analysis?.sample_status ? ` (${analysis.sample_status})` : ""}… gaps will
            appear automatically once the sample is ready.
          </div>
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Computing gaps…</p>
        ) : (
          <>
            {coreStrengths.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold flex items-center gap-2 text-emerald-700">
                  <Check className="h-4 w-4" />
                  Core strengths
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {coreStrengths.map((skill) => (
                    <Badge key={skill} variant="secondary" className="text-[11px]">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Identified gaps</h3>
              {skillGaps.length === 0 ? (
                !waitingOnSample && (
                  <p className="text-sm text-muted-foreground italic">
                    No major gaps identified — you already cover the tracked demand skills.
                  </p>
                )
              ) : (
                <div className="grid max-h-96 gap-2 overflow-y-auto pr-1">
                  {skillGaps.map((gap, index) => {
                    const added = selectedKeys.has(gap.skill.toLowerCase())
                    return (
                      <div
                        key={`${gap.skill}-${index}`}
                        className="flex items-start justify-between gap-3 rounded-lg border bg-muted/30 p-3"
                      >
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{gap.skill}</span>
                            <Badge
                              variant={
                                gap.priority === "high"
                                  ? "destructive"
                                  : gap.priority === "medium"
                                    ? "default"
                                    : "secondary"
                              }
                              className="text-[10px] px-1 py-0 h-4"
                            >
                              {gap.priority}
                            </Badge>
                            <Badge variant="outline" className="text-[10px] px-1 py-0 h-4 capitalize">
                              {gap.kind === "underleveled" ? "Underleveled" : "Missing"}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{gap.gap_reason}</p>
                        </div>
                        <Button
                          type="button"
                          variant={added ? "secondary" : "outline"}
                          size="sm"
                          className="h-7 shrink-0 gap-1 text-xs"
                          disabled={added}
                          onClick={() => onAddSkill(gap.skill)}
                        >
                          {added ? (
                            <>
                              <Check className="h-3 w-3" /> Added
                            </>
                          ) : (
                            <>
                              <Plus className="h-3 w-3" /> Add to learn
                            </>
                          )}
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
