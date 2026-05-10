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
