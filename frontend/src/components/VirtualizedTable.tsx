/**
 * VirtualizedTable — efficient table rendering for large datasets.
 *
 * Uses @tanstack/react-virtual to render only visible rows,
 * enabling smooth scrolling through thousands of items.
 */

import { useRef } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Column<T> {
  /** Column header text */
  header: string
  /** CSS width (e.g., "w-56", "w-20", "flex-1 min-w-0") */
  width: string
  /** Render function for cell content */
  render: (item: T, index: number) => React.ReactNode
}

interface VirtualizedTableProps<T> {
  /** Data array to render */
  data: T[]
  /** Column definitions */
  columns: Column<T>[]
  /** Unique key extractor for each row */
  getRowKey: (item: T, index: number) => string | number
  /** Estimated row height in pixels (default: 48) */
  rowHeight?: number
  /** Number of rows to render outside visible area (default: 10) */
  overscan?: number
  /** Optional className for the container */
  className?: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VirtualizedTable<T>({
  data,
  columns,
  getRowKey,
  rowHeight = 48,
  overscan = 10,
  className = "",
}: VirtualizedTableProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan,
  })

  return (
    <div className={`flex flex-col flex-1 min-h-0 ${className}`}>
      {/* Fixed header - uses same flex layout as rows */}
      <div className="flex items-center border-b border-border bg-muted/50 text-sm font-medium text-muted-foreground">
        {columns.map((col, i) => (
          <div key={i} className={`${col.width} px-4 py-3`}>
            {col.header}
          </div>
        ))}
      </div>

      {/* Virtualized body */}
      <div ref={parentRef} className="flex-1 overflow-auto">
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const item = data[virtualRow.index]
            return (
              <div
                key={getRowKey(item, virtualRow.index)}
                className="flex items-center border-b border-border hover:bg-muted/50"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                {columns.map((col, i) => (
                  <div key={i} className={`${col.width} px-4 py-2 overflow-hidden`}>
                    {col.render(item, virtualRow.index)}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
