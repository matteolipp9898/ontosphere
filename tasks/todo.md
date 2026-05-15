# OntoSphere — Implementation Plan

## Step 0: Spike — Cytoscape Extensions Compatibility

- **Branch**: `spike/cytoscape-extensions`
- **Timebox**: 2-3 hours max
- Install `cytoscape-edgehandles@4.0.1` + `@types/cytoscape-edgehandles@4.0.4`
- Install `cytoscape-context-menus@4.2.1` + `@types/cytoscape-context-menus@4.1.4`
- Verify both initialize without errors and basic functionality works (drag-to-connect, right-click menu shows)
- **Output**: short report (works / works-with-quirks / broken + fork available y/n)
- If spike fails: either use a fork or implement drag-to-connect manually (~100-150 lines)

## Step 1: WebSocket Reconnection — Exponential Backoff + Dormant Mode

- **Branch**: `fix/websocket-reconnection`
- **One commit**: `fix: robust WebSocket reconnection with exponential backoff`
- Refactor `useWebSocket.ts`:
  - Backoff: 1s → 2s → 4s → 8s → 16s → 30s (cap)
  - 5 active retries, then switch to dormant mode (60s interval)
  - Connection state enum: `'connecting' | 'connected' | 'disconnected' | 'dormant'`
  - Reset backoff on successful connection
  - No hard cutoff — dormant mode retries indefinitely at 60s
- No resync logic needed: REST poll (`useOntologyStatus` with `refetchInterval: 2000`) already covers state recovery

## Step 2: Connection Status Banner in Editor

- **Branch**: same as Step 1 or stacked
- **One commit**: `feat: show connection status in editor`
- Subtle banner in `OntologyEditor.tsx` for disconnected/reconnecting/dormant states
- "Reconnect now" button to wake from dormant mode
- No intrusive modals — small inline indicator

## Step 3: Drag-to-Connect Edges via cytoscape-edgehandles

- **Branch**: `feat/graph-editing`
- **Commit**: `feat: add drag-to-connect edges via cytoscape-edgehandles`
- Gate on `editMode` prop in `GraphViewer.tsx`
- Wire edge completion to existing `useAddRelationship` mutation
- **LOCK-IN**: Wrap edgehandles in an `IConnectionTool` adapter interface (single-file swap if the plugin ever breaks or needs replacing with a manual implementation)

## Step 4: Right-Click Context Menus for Graph Editing

- **Branch**: same as Step 3 or stacked
- **Commit**: `feat: add right-click context menus for graph editing`
- **LOCK-IN**: Use `cytoscape-context-menus` (traditional dropdown), NOT `cytoscape-cxtmenu` (radial)
- Node menu: edit label, delete, add relationship
- Canvas background menu: add new class
- Wire actions to existing API hooks (`useUpdateClass`, `useDeleteClass`, `useAddClass`, `useAddRelationship`)

---

## Review Notes for Steps 3-4 (pre-merge)

### Q1: AddClassDialog URI strategy

Currently **pure manual input** — the user types both URI and label from scratch. There is no auto-slug from label, no default namespace prefix, and no validation beyond "both fields required." This was the minimal viable approach. If we want a better UX, the recommended improvement is: pre-fill the URI field with `{ontology.namespace_uri}{slugify(label)}` as the user types the label, but leave it editable for override. This requires threading the ontology's `namespace_uri` into the AddClassDialog (currently it only receives `open`, `onOpenChange`, `onSubmit`, `isPending`). This is a small change (~10 lines) but was deliberately deferred to keep the Step 4 commit focused on context menu wiring.

### Q2: "Add Relationship From..." target selection

Currently this action **selects the node and opens the NodePanel side panel in edit mode**, where the existing "Add Relationship" form (with a target dropdown and relationship type selector) is already available. It does NOT activate edgehandles drag-mode from that source node. The UX is: right-click node → "Add Relationship From..." → side panel opens with the node selected → user picks target and type from dropdowns → clicks "Add Relationship." If drag-mode activation is preferred, the change would be: call `connectionToolRef.current.start(sourceNode)` via a new callback from OntologyEditor, which programmatically begins the edgehandles gesture from that node. The edgehandles API supports this via `eh.start(sourceNode)`. This is ~5 lines of wiring but changes the UX significantly — the user would drag to a target node instead of picking from a dropdown, and the relationship type would default to RELATED_TO (no type picker in the drag flow).

---

## Housekeeping (before Step 3)

- **Branch**: `chore/track-lockfile-and-eslint` (off main, after fix/websocket-reconnection merged)
- Track `frontend/package-lock.json` in git
- Create `eslint.config.js` for ESLint 9 — linter must be green before Step 3
- Atomic commits: one for lockfile, one for ESLint config

## Branch Strategy

- `fix/websocket-reconnection` → merge to main first (Steps 1-2)
- `chore/track-lockfile-and-eslint` → merge to main second
- `feat/graph-editing` → off main after both above are merged (Steps 3-4)
- No stacking. Reviews stay small and focused.

## Risks and Unknowns

- `cytoscape-edgehandles` last release was Jul 2021 — Step 0 spike validates this
- No frontend tests — changes can't be regression-tested automatically
- No CI — linting/type-checking are local only
- TypeScript `@types` packages may need version pinning to avoid forcing cytoscape upgrade

## Decisions Made

- WebSocket: dormant mode (60s) instead of hard cap at 10 retries
- WebSocket transport is ephemeral progress only; no resync needed on reconnect
- `cytoscape-node-editing` excluded: requires jQuery + Konva, only does resize grapples, not useful for ontology editing
- Dropdown context menu preferred over radial for discoverability
- If edgehandles breaks: fallback is manual implementation (~100-150 lines) behind the IConnectionTool adapter
