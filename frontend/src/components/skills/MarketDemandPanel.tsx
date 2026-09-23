"use client"

import React from "react"
import { SkillDemand } from "@/types/skills"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Check, Plus, TrendingUp } from "lucide-react"

interface MarketDemandPanelProps {
  demands: SkillDemand[]
  subtitle?: string
  selectedSkills?: string[]
  onAddSkill?: (skill: string) => void
}

export const MarketDemandPanel: React.FC<MarketDemandPanelProps> = ({
  demands,
  subtitle,
  selectedSkills = [],
  onAddSkill,
}) => {
  const maxDemand = Math.max(...demands.map((d) => d.demand), 1)
  const selectedKeys = React.useMemo(
    () => new Set(selectedSkills.map((s) => s.toLowerCase())),
    [selectedSkills]
  )

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xl font-bold">Market Demand</CardTitle>
        <TrendingUp className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {subtitle || "Top skills requested in recent job offers."}
        </p>
        <ScrollArea className="h-[min(360px,50vh)] pr-3">
          <div className="space-y-4">
            {demands.map((item) => {
              const alreadySelected = selectedKeys.has(item.name.toLowerCase())
              const canAdd = !item.is_owned && !!onAddSkill
              return (
                <div key={item.name} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="font-medium truncate">{item.name}</span>
                      {item.is_owned && (
                        <Badge
                          variant="secondary"
                          className="gap-1 text-[10px] px-1.5 py-0 h-4 shrink-0"
                        >
                          <Check className="h-2.5 w-2.5" /> You have this
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-muted-foreground text-xs">
                        {item.demand} offer{item.demand === 1 ? "" : "s"}
                      </span>
                      {canAdd && (
                        <button
                          type="button"
                          onClick={() => onAddSkill?.(item.name)}
                          disabled={alreadySelected}
                          title={alreadySelected ? "Already in your skills to learn" : "Add to skills to learn"}
                          className={`flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                            alreadySelected
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-input hover:bg-accent"
                          }`}
                        >
                          {alreadySelected ? (
                            <Check className="h-3 w-3" />
                          ) : (
                            <Plus className="h-3 w-3" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                  <Progress
                    value={(item.demand / maxDemand) * 100}
                    className={`h-2 ${item.is_owned ? "opacity-50" : ""}`}
                  />
                </div>
              )
            })}
            {demands.length === 0 && (
              <p className="text-muted-foreground text-center py-4">
                No demand data available.
              </p>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
