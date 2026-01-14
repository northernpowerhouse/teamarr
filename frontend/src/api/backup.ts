/**
 * Backup and restore API functions
 */

export interface RestoreResponse {
  success: boolean
  message: string
  backup_path: string | null
}

/**
 * Download a backup of the database.
 * Opens the download in a new tab/triggers browser download.
 */
export function downloadBackup(): void {
  // Use direct URL for file download (not fetch)
  window.location.href = "/api/v1/backup"
}

/**
 * Restore database from uploaded backup file.
 */
export async function restoreBackup(file: File): Promise<RestoreResponse> {
  const formData = new FormData()
  formData.append("file", file)

  const response = await fetch("/api/v1/backup", {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || "Failed to restore backup")
  }

  return response.json()
}
