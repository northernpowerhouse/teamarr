/**
 * TemplateAssignmentModal — manage template assignments for multi-league groups.
 *
 * Allows assigning different templates based on sport/league filters:
 * - leagues match (most specific) → sports match → default (fallback)
 */

import { useState, useCallback, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  getGroupTemplates,
  addGroupTemplate,
  updateGroupTemplate,
  deleteGroupTemplate,
} from "@/api/groups"
import type { GroupTemplate } from "@/api/groups"
import { useTemplates } from "@/hooks/useTemplates"
import { useSports } from "@/hooks/useSports"
import { getLeagues } from "@/api/teams"
import { Loader2, Plus, Pencil, Trash2, Layers } from "lucide-react"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TemplateAssignmentModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupId: number
  groupName: string
  groupLeagues: string[] // Leagues configured in this group
}

interface EditingAssignment {
  id?: number // undefined for new, number for edit
  template_id: number | null
  sports: string[]
  leagues: string[]
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TemplateAssignmentModal({
  open,
  onOpenChange,
  groupId,
  groupName,
  groupLeagues,
}: TemplateAssignmentModalProps) {
  const queryClient = useQueryClient()

  // Form state for add/edit
  const [editing, setEditing] = useState<EditingAssignment | null>(null)

  // Fetch current assignments
  const {
    data: assignments,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["groupTemplates", groupId],
    queryFn: () => getGroupTemplates(groupId),
    enabled: open,
  })

  // Fetch templates for dropdown
  const { data: templates } = useTemplates()
  const eventTemplates = templates?.filter((t) => t.template_type === "event") || []

  // Fetch sports for dropdown
  const { data: sportsData } = useSports()
  const sportsMap = sportsData?.sports || {}

  // Fetch leagues for display
  const { data: leaguesData } = useQuery({
    queryKey: ["leagues"],
    queryFn: () => getLeagues(),
    enabled: open,
  })
  const allLeagues = leaguesData?.leagues || []

  // Get unique sports from group's leagues
  const groupSports = [...new Set(
    allLeagues
      .filter((l) => groupLeagues.includes(l.slug))
      .map((l) => l.sport)
  )]

  // Mutations
  const addMutation = useMutation({
    mutationFn: (data: { template_id: number; sports?: string[]; leagues?: string[] }) =>
      addGroupTemplate(groupId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groupTemplates", groupId] })
      setEditing(null)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      assignmentId,
      data,
    }: {
      assignmentId: number
      data: { template_id?: number; sports?: string[]; leagues?: string[] }
    }) => updateGroupTemplate(groupId, assignmentId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groupTemplates", groupId] })
      setEditing(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (assignmentId: number) => deleteGroupTemplate(groupId, assignmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groupTemplates", groupId] })
    },
  })

  // Reset editing state when modal closes
  useEffect(() => {
    if (!open) {
      setEditing(null)
    }
  }, [open])

  const handleAdd = useCallback(() => {
    setEditing({
      template_id: null,
      sports: [],
      leagues: [],
    })
  }, [])

  const handleEdit = useCallback((assignment: GroupTemplate) => {
    setEditing({
      id: assignment.id,
      template_id: assignment.template_id,
      sports: assignment.sports || [],
      leagues: assignment.leagues || [],
    })
  }, [])

  const handleDelete = useCallback(
    (assignmentId: number) => {
      if (confirm("Delete this template assignment?")) {
        deleteMutation.mutate(assignmentId)
      }
    },
    [deleteMutation]
  )

  const handleSave = useCallback(() => {
    if (!editing || !editing.template_id) return

    const data = {
      template_id: editing.template_id,
      sports: editing.sports.length > 0 ? editing.sports : undefined,
      leagues: editing.leagues.length > 0 ? editing.leagues : undefined,
    }

    if (editing.id) {
      updateMutation.mutate({ assignmentId: editing.id, data })
    } else {
      addMutation.mutate(data)
    }
  }, [editing, addMutation, updateMutation])

  const handleCancel = useCallback(() => {
    setEditing(null)
  }, [])

  const toggleSport = useCallback((sport: string) => {
    setEditing((prev) =>
      prev
        ? {
            ...prev,
            sports: prev.sports.includes(sport)
              ? prev.sports.filter((s) => s !== sport)
              : [...prev.sports, sport],
          }
        : null
    )
  }, [])

  const toggleLeague = useCallback((league: string) => {
    setEditing((prev) =>
      prev
        ? {
            ...prev,
            leagues: prev.leagues.includes(league)
              ? prev.leagues.filter((l) => l !== league)
              : [...prev.leagues, league],
          }
        : null
    )
  }, [])

  const getSpecificityLabel = (assignment: GroupTemplate) => {
    if (assignment.leagues && assignment.leagues.length > 0) {
      return "League"
    }
    if (assignment.sports && assignment.sports.length > 0) {
      return "Sport"
    }
    return "Default"
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4" />
            Template Assignments
          </DialogTitle>
          <DialogDescription>
            Assign templates to {groupName} by sport or league. More specific matches take priority.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Current assignments */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <div className="text-sm text-destructive py-4">
              Failed to load template assignments.
            </div>
          )}

          {!isLoading && !error && (
            <>
              {/* Assignments table */}
              {assignments && assignments.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Template</th>
                        <th className="text-left px-3 py-2 font-medium">Filter</th>
                        <th className="text-left px-3 py-2 font-medium">Specificity</th>
                        <th className="text-right px-3 py-2 font-medium w-24">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assignments.map((a) => (
                        <tr key={a.id} className="border-t">
                          <td className="px-3 py-2">{a.template_name || `Template ${a.template_id}`}</td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1">
                              {a.leagues?.map((l) => (
                                <Badge key={l} variant="secondary" className="text-xs">
                                  {allLeagues.find((lg) => lg.slug === l)?.name || l}
                                </Badge>
                              ))}
                              {a.sports?.map((s) => (
                                <Badge key={s} variant="outline" className="text-xs">
                                  {sportsMap[s] || s}
                                </Badge>
                              ))}
                              {!a.leagues?.length && !a.sports?.length && (
                                <span className="text-muted-foreground text-xs">All events</span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <Badge
                              variant={
                                getSpecificityLabel(a) === "League"
                                  ? "default"
                                  : getSpecificityLabel(a) === "Sport"
                                  ? "secondary"
                                  : "outline"
                              }
                              className="text-xs"
                            >
                              {getSpecificityLabel(a)}
                            </Badge>
                          </td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0"
                                onClick={() => handleEdit(a)}
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                                onClick={() => handleDelete(a.id)}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  No template assignments yet. Add one to get started.
                </div>
              )}

              {/* Add/Edit form */}
              {editing && (
                <div className="border rounded-lg p-4 space-y-4 bg-muted/30">
                  <h4 className="font-medium text-sm">
                    {editing.id ? "Edit Assignment" : "New Assignment"}
                  </h4>

                  {/* Template select */}
                  <div className="space-y-2">
                    <Label>Template</Label>
                    <Select
                      value={editing.template_id?.toString() || ""}
                      onChange={(e) =>
                        setEditing({
                          ...editing,
                          template_id: e.target.value ? Number(e.target.value) : null,
                        })
                      }
                    >
                      <option value="">Select template...</option>
                      {eventTemplates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  {/* Sports filter */}
                  {groupSports.length > 1 && (
                    <div className="space-y-2">
                      <Label>Sports (optional - leave empty for all)</Label>
                      <div className="flex flex-wrap gap-2">
                        {groupSports.map((sport) => (
                          <Badge
                            key={sport}
                            variant={editing.sports.includes(sport) ? "default" : "outline"}
                            className="cursor-pointer"
                            onClick={() => toggleSport(sport)}
                          >
                            {sportsMap[sport] || sport}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Leagues filter */}
                  <div className="space-y-2">
                    <Label>Leagues (optional - leave empty for all)</Label>
                    <div className="flex flex-wrap gap-2">
                      {groupLeagues.map((slug) => {
                        const league = allLeagues.find((l) => l.slug === slug)
                        return (
                          <Badge
                            key={slug}
                            variant={editing.leagues.includes(slug) ? "default" : "outline"}
                            className="cursor-pointer"
                            onClick={() => toggleLeague(slug)}
                          >
                            {league?.name || slug}
                          </Badge>
                        )
                      })}
                    </div>
                  </div>

                  {/* Form actions */}
                  <div className="flex justify-end gap-2 pt-2">
                    <Button variant="outline" size="sm" onClick={handleCancel}>
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleSave}
                      disabled={!editing.template_id || addMutation.isPending || updateMutation.isPending}
                    >
                      {addMutation.isPending || updateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin mr-1" />
                      ) : null}
                      {editing.id ? "Update" : "Add"}
                    </Button>
                  </div>
                </div>
              )}

              {/* Add button */}
              {!editing && (
                <Button variant="outline" size="sm" onClick={handleAdd} className="w-full">
                  <Plus className="h-4 w-4 mr-1" />
                  Add Template Assignment
                </Button>
              )}
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
