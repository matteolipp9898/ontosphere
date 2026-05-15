# OntoSphere — Implementation Plan

## Step 0: Spike — Cytoscape Extensions Compatibility  **DONE**

- Merged to main: 2026-05-15
- Both `cytoscape-edgehandles@4.0.1` and `cytoscape-context-menus@4.2.1` work with Cytoscape.js v3.30
- Wrapped in adapter interfaces (`IConnectionTool`, `IGraphContextMenu`) for swapability

## Step 1: WebSocket Reconnection — Exponential Backoff + Dormant Mode  **DONE**

- Merged to main: 2026-05-15 (`7f10a2b`)
- Branch: `fix/websocket-reconnection` (deleted)
- Backoff: 1s -> 2s -> 4s -> 8s -> 16s -> 30s cap, then dormant at 60s
- Bug fix: banner stays visible during retries (no flicker); dormant mode reachable on unstable connections (`2861f10`)
- Stable connection threshold: backoff only resets after 5s of sustained connection

## Step 2: Connection Status Banner in Editor  **DONE**

- Merged with Step 1 (`7f10a2b`)
- `ConnectionBanner.tsx`: amber banner for disconnected/dormant, "Reconnect Now" button in dormant mode
- Smoke tested 2026-05-15: all 4 critical checks passed

## Step 3: Drag-to-Connect Edges via cytoscape-edgehandles  **DONE**

- Merged to main: 2026-05-15 (`8bd5ddb`)
- Branch: `feat/graph-editing` (deleted)
- `IConnectionTool` adapter in `graph/ConnectionTool.ts` — single-file swap point
- Gated on `editMode`, wired to `useAddRelationship` mutation

## Step 4: Right-Click Context Menus for Graph Editing  **DONE**

- Merged with Step 3 (`8bd5ddb`)
- `IGraphContextMenu` adapter in `graph/GraphContextMenu.ts`
- Node menu: edit, delete (with confirmation dialog), add relationship
- Canvas menu: add new class (via `AddClassDialog`)

## Housekeeping  **DONE**

- Merged to main: 2026-05-15 (`4a28af9`)
- Branch: `chore/track-lockfile-and-eslint` (deleted)
- ESLint 9 flat config (`eslint.config.js`), all lint errors fixed
- `package-lock.json` tracked

---

## What's Next — Candidate Features (not started)

### N1: AddClassDialog UX improvements (small, ~1 session)
Auto-slug URI from label using `{ontology.namespace_uri}{slugify(label)}`, editable for override. Thread `namespace_uri` into dialog. See Q1 review notes below.

### N2: Relationship type picker in drag-to-connect flow (small, ~1 session)
Currently drag-to-connect defaults to `RELATED_TO`. Add a small popover after edge drop to pick from available relationship types (subClassOf, partOf, etc.). Alternatively, activate edgehandles from the context menu "Add Relationship From..." action (see Q2 below).

### N3: Undo/redo for graph editing operations (medium, ~2-3 sessions)
Track mutations in a client-side stack. Undo calls the inverse API operation (delete edge that was added, re-add class that was deleted). Scoped to the current editing session. Requires careful thought about conflict with server-side state from other clients.

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

- All branches merged to main as of 2026-05-15. No open branches.
- Future work: new branches off main, no stacking, small focused PRs.

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
