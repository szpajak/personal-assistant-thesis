"use client"

import React from "react"
import { Skill } from "@/types/skills"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"

interface MySkillsPanelProps {
  skills: Skill[]
}

const levelToValue = (level: string): number => {
  switch (level.toLowerCase()) {
    case "beginner":
      return 25
    case "intermediate":
      return 50
    case "advanced":
      return 75
    case "expert":
      return 100
    default:
      return 0
  }
}

export const MySkillsPanel: React.FC<MySkillsPanelProps> = ({ skills }) => {
  const groupedSkills = skills.reduce((acc, skill) => {
    if (!acc[skill.category]) {
      acc[skill.category] = []
    }
    acc[skill.category].push(skill)
    return acc
  }, {} as Record<string, Skill[]>)

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle>My Skills</CardTitle>
        {skills.length > 0 && (
          <span className="text-sm text-muted-foreground">{skills.length}</span>
        )}
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[min(360px,50vh)] pr-3">
          <div className="space-y-6">
            {Object.entries(groupedSkills).map(([category, categorySkills]) => (
              <div key={category} className="space-y-3">
                <h3 className="font-semibold text-lg border-b pb-1">{category}</h3>
                <div className="space-y-4">
                  {categorySkills.map((skill) => (
                    <div key={skill.id} className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="font-medium">{skill.name}</span>
                        <Badge variant="secondary">{skill.level}</Badge>
                      </div>
                      <Progress value={levelToValue(skill.level)} className="h-2" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {skills.length === 0 && (
              <p className="text-muted-foreground text-center py-4">No skills added yet.</p>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
