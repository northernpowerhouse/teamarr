import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

const API_BASE = "/api/v1/detection-keywords"

// Types
export type CategoryType =
  | "event_type_keywords"
  | "league_hints"
  | "sport_hints"
  | "placeholders"
  | "card_segments"
  | "exclusions"
  | "separators"

export interface DetectionKeyword {
  id: number
  category: CategoryType
  keyword: string
  is_regex: boolean
  target_value: string | null
  enabled: boolean
  priority: number
  description: string | null
  created_at: string
  updated_at: string
}

export interface DetectionKeywordCreate {
  category: CategoryType
  keyword: string
  is_regex?: boolean
  target_value?: string | null
  enabled?: boolean
  priority?: number
  description?: string | null
}

export interface DetectionKeywordUpdate {
  keyword?: string
  is_regex?: boolean
  target_value?: string | null
  enabled?: boolean
  priority?: number
  description?: string | null
  clear_target_value?: boolean
  clear_description?: boolean
}

export interface DetectionKeywordListResponse {
  total: number
  keywords: DetectionKeyword[]
}

export interface CategoryInfo {
  id: CategoryType
  name: string
  description: string
  has_target: boolean
  target_description?: string
}

export interface CategoriesResponse {
  categories: CategoryInfo[]
}

export interface BulkImportResponse {
  created: number
  updated: number
  failed: number
  errors: string[]
}

// Hooks

export function useDetectionKeywords(category?: CategoryType) {
  return useQuery<DetectionKeywordListResponse>({
    queryKey: ["detection-keywords", category],
    queryFn: async () => {
      const url = category ? `${API_BASE}/${category}` : API_BASE
      const res = await fetch(url)
      if (!res.ok) throw new Error("Failed to fetch detection keywords")
      return res.json()
    },
  })
}

export function useDetectionCategories() {
  return useQuery<CategoriesResponse>({
    queryKey: ["detection-categories"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/categories`)
      if (!res.ok) throw new Error("Failed to fetch categories")
      return res.json()
    },
    staleTime: Infinity, // Categories don't change
  })
}

export function useCreateDetectionKeyword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: DetectionKeywordCreate) => {
      const res = await fetch(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.detail || "Failed to create keyword")
      }
      return res.json() as Promise<DetectionKeyword>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["detection-keywords"] })
    },
  })
}

export function useUpdateDetectionKeyword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: DetectionKeywordUpdate }) => {
      const res = await fetch(`${API_BASE}/id/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.detail || "Failed to update keyword")
      }
      return res.json() as Promise<DetectionKeyword>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["detection-keywords"] })
    },
  })
}

export function useDeleteDetectionKeyword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`${API_BASE}/id/${id}`, { method: "DELETE" })
      if (!res.ok) throw new Error("Failed to delete keyword")
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["detection-keywords"] })
    },
  })
}

export function useBulkImportDetectionKeywords() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      keywords,
      replaceCategory = false,
    }: {
      keywords: DetectionKeywordCreate[]
      replaceCategory?: boolean
    }) => {
      const res = await fetch(`${API_BASE}/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keywords, replace_category: replaceCategory }),
      })
      if (!res.ok) throw new Error("Failed to import keywords")
      return res.json() as Promise<BulkImportResponse>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["detection-keywords"] })
    },
  })
}

export async function exportDetectionKeywords(category?: CategoryType): Promise<{
  exported_at: string
  count: number
  keywords: DetectionKeywordCreate[]
}> {
  const url = category ? `${API_BASE}/export?category=${category}` : `${API_BASE}/export`
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to export keywords")
  return res.json()
}
