# Settings Tab Audit & Reorganization Proposal

## Current Organization (7 Tabs)

### 1. General
**Header:** "General Settings - Configure timezone, time format, and display preferences"

| Card | Settings |
|------|----------|
| System Settings | UI Display Timezone (read-only), EPG Output Timezone, Time Format (12h/24h), Show Timezone Abbreviation |

**Issues:**
- Tab name "General" is vague
- Only contains display/timezone settings - feels thin

---

### 2. Teams
**Header:** "Team Based Streams - Configure settings for team-based EPG generation"

| Card | Settings |
|------|----------|
| Channel Settings | Schedule Days Ahead, Midnight Crossover, Channel ID Format |

**Issues:**
- Card labeled "Channel Settings" but contains team EPG settings
- "Midnight Crossover" is an edge case, buried here
- Only applies to Team-based channels, not Event Groups

---

### 3. Event Groups
**Header:** "Event Based Streams - Configure settings for event-based EPG generation"

| Card | Settings |
|------|----------|
| Event Matching | Event Lookahead, Duplicate Handling |
| Exception Keywords | Keywords table with label/terms/behavior (conditional on consolidate) |
| Default Team Filter | Enable, Mode (include/exclude), TeamPicker |

**Issues:**
- "Default Team Filter" doesn't belong here - it's not an "Event Group" setting
- Tab has 3 unrelated cards (matching, keywords, filtering)
- Overloaded with different concerns

---

### 4. Channel Management
**Header:** "Channel Management - Configure channel lifecycle, numbering, and sorting"

| Card | Settings |
|------|----------|
| Channel Lifecycle | Create Timing, Delete Timing |
| Channel Numbering | Range Start/End, Numbering Mode, Sorting Scope, Sort By, Priority Manager |
| Stream Ordering Manager | (separate component) |

**Assessment:** Well-organized, cohesive

---

### 5. EPG Generation
**Header:** "EPG Generation - Configure EPG output, scheduling, and game durations"

| Card | Settings |
|------|----------|
| Output Settings | Output Path, Days Ahead, Lookback Hours, Include Final Events, Scheduled Generation, Cron Expression |
| Default Durations | Per-sport duration inputs |

**Assessment:** Well-organized, cohesive

---

### 6. Dispatcharr
**Header:** "Dispatcharr Integration - Configure connection to Dispatcharr"

| Card | Settings |
|------|----------|
| Connection Settings | Enable, URL, Username, Password |
| EPG Source | Source dropdown |
| Default Channel Profiles | Profile selector |
| Default Stream Profile | Profile selector |
| Logo Cleanup | Cleanup unused logos switch |

**Assessment:** Well-organized, all integration settings together

---

### 7. Advanced
**Header:** "Advanced - Advanced configuration options"

| Card | Settings |
|------|----------|
| Update Notifications | Version display, Check Now, Auto-check enable, Notify stable/dev |
| Backup & Restore | Download/Restore buttons |
| Local Caching | Cache stats, Refresh button |
| Scheduled Channel Reset | Enable, Cron expression |

**Issues:**
- "Scheduled Channel Reset" is a scheduling setting, not advanced maintenance
- "Update Notifications" could be in General

---

## Key Problems

1. **Vague naming**: "General" and "Advanced" don't convey content
2. **Misplaced settings**: Team Filter in Event Groups, Channel Reset in Advanced
3. **Teams tab is confusing**: Contains "Channel Settings" but for team EPG
4. **Thin tabs**: General only has 4 settings, Teams only has 3
5. **Scattered scheduling**: EPG scheduling is in EPG tab, Channel Reset is in Advanced

---

## Proposed Reorganization (7 Tabs)

The tab order mirrors the application's main navigation: Templates → Teams → Event Groups → EPG → Channels, with General at the start (global preferences) and System at the end (maintenance).

### 1. General (keep, rename card)
**New Header:** "General - Timezone, format, and display preferences"

| Card | Settings |
|------|----------|
| Display Settings | UI Timezone (read-only), EPG Output Timezone, Time Format, Show Timezone Abbreviation |

**What belongs in General:**
- Settings that affect the entire application's display/behavior
- Preferences every user interacts with regularly
- Global defaults that apply across all features

**Rationale:** Keep "General" name (intuitive for users), but rename card from "System Settings" to "Display Settings" for clarity.

---

### 2. Teams (keep, rename card)
**New Header:** "Teams - Settings for team-based EPG generation"

| Card | Settings |
|------|----------|
| Team EPG Settings | Schedule Days Ahead, Midnight Crossover, Channel ID Format |

**Rationale:**
- Mirrors app nav (Teams tab)
- Rename card from "Channel Settings" to "Team EPG Settings" - clearer about purpose
- These settings only apply to Team-based streams, so keep them separate

---

### 3. Event Groups (keep, reorganize)
**New Header:** "Event Groups - Settings for event-based EPG generation"

| Card | Settings |
|------|----------|
| Event Matching | Event Lookahead, Duplicate Handling |
| Exception Keywords | Keywords table (conditional on consolidate) |
| Default Team Filter | Enable, Mode, TeamPicker |

**Rationale:**
- Mirrors app nav (Event Groups tab)
- Keep Team Filter here - it's a default for new event groups, so conceptually belongs
- All cards relate to how event groups find and match events

---

### 4. EPG (was EPG Generation)
**New Header:** "EPG - Output settings, scheduling, and durations"

| Card | Settings |
|------|----------|
| Output Settings | Path, Days Ahead, Lookback, Include Final |
| Scheduled Generation | Enable, Cron, Presets, Run Now |
| Scheduled Reset | Enable, Cron, Presets |
| Default Durations | Per-sport durations |

**Rationale:**
- Mirrors app nav (EPG tab)
- Move "Scheduled Channel Reset" here from Advanced - it's a scheduling operation
- All EPG generation and scheduling behavior together

---

### 5. Channels (was Channel Management)
**New Header:** "Channels - Lifecycle, numbering, and organization"

| Card | Settings |
|------|----------|
| Channel Lifecycle | Create Timing, Delete Timing |
| Channel Numbering | Range, Mode, Sorting, Priority Manager |
| Stream Ordering | (component) |

**Rationale:**
- Mirrors app nav (Channels tab)
- Focused on channel behavior in Dispatcharr
- Keep Team EPG settings in Teams tab (they're about EPG content, not channel management)

---

### 6. Dispatcharr (unchanged)
**Header:** "Dispatcharr - Integration with Dispatcharr"

| Card | Settings |
|------|----------|
| Connection | Enable, URL, Credentials |
| EPG Source | Source dropdown |
| Channel Profiles | Profile selector |
| Stream Profile | Profile selector |
| Logo Cleanup | Cleanup switch |

**Rationale:** External integration, naturally comes after core feature settings.

---

### 7. System (was Advanced)
**New Header:** "System - Updates, backup, and maintenance"

| Card | Settings |
|------|----------|
| Updates | Version, Check Now, Auto-check settings |
| Backup & Restore | Download/Restore |
| Cache | Stats, Refresh |

**What belongs in System (not General):**
- Administrative/maintenance operations done infrequently
- Destructive or impactful actions (restore, cache clear)
- System information (version, cache stats)
- Power user features

**Rationale:**
- "System" is clearer than "Advanced"
- Moved Channel Reset to EPG tab (it's a scheduling operation)
- Pure maintenance/admin tasks that most users rarely need

---

## General vs System: Decision Guide

| Put in General | Put in System |
|----------------|---------------|
| Affects everyday display/behavior | Administrative/maintenance tasks |
| Changed once, affects everything | Done occasionally or for troubleshooting |
| User preferences | System operations |
| No risk of data loss | May affect data (backup/restore) |

**Examples:**
- Timezone → General (affects all time displays)
- Time format → General (user preference)
- Backup/Restore → System (administrative, affects data)
- Cache refresh → System (maintenance task)
- Version updates → System (occasional check)

---

## Tab Order Rationale

Order mirrors the application's main navigation flow:

| # | Settings Tab | Mirrors App Tab | Purpose |
|---|--------------|-----------------|---------|
| 1 | General | — | Global preferences (first, like most apps) |
| 2 | Teams | Teams | Team-based stream settings |
| 3 | Event Groups | Event Groups | Event-based stream settings |
| 4 | EPG | EPG | Output and scheduling |
| 5 | Channels | Channels | Channel lifecycle/numbering |
| 6 | Dispatcharr | — | External integration |
| 7 | System | — | Maintenance (last, used least) |

---

## Changes Summary

| Current | Proposed | Change |
|---------|----------|--------|
| General | General | Rename card to "Display Settings" |
| Teams | Teams | Rename card to "Team EPG Settings" |
| Event Groups | Event Groups | Keep as-is |
| Channel Management | Channels | Shorter name |
| EPG Generation | EPG | Shorter name, add Scheduled Reset |
| Dispatcharr | Dispatcharr | No change |
| Advanced | System | Rename, remove Scheduled Reset |

---

## Implementation Notes

- Rename tabs but preserve URL query param values (`?tab=general` etc.)
- Update card names as specified above
- Move "Scheduled Channel Reset" from Advanced to EPG tab
- Update any documentation referencing old tab/card names
