# OntoSphere — Lessons Learned

<!-- Append entries as work progresses. Each entry: date, step, what happened. -->

## 2026-05-10 — Step 0: Spike — cytoscape-edgehandles + cytoscape-context-menus

**Result: GREEN (works)**

Both `cytoscape-edgehandles@4.0.1` and `cytoscape-context-menus@4.2.1` install, type-check, and bundle through Vite without errors. The `@types/cytoscape-edgehandles@4.0.4` and `@types/cytoscape-context-menus@4.1.4` packages provide clean type declarations that augment the `cytoscape.Core` interface with `.edgehandles()` and `.contextMenus()` methods. CSS for context-menus imports cleanly. No runtime test was possible without the full Docker stack (Postgres + Redis), but compile-time validation is complete and strong — imports, types, and bundling all succeeded on first try.

**Surprises:**
- ESLint is broken project-wide (ESLint 9 installed but no `eslint.config.js` exists). Pre-existing, not related to the spike.
- Several pre-existing TS strict errors exist when type-checking with `tsconfig.app.json` (unused imports, missing `@types/cytoscape-dagre`, `import.meta.env` not recognized). The project relies on Vite's looser TS handling for builds.
- No active forks of edgehandles exist with real code changes. The 2021 release is the only viable package version.

## 2026-05-10 — Steps 1-2: WebSocket reconnection + connection banner

Both steps went cleanly, no surprises. The `useWebSocket` hook was rewritten to use exponential backoff (1s→30s) with 5 active retries before entering dormant mode (60s interval). The hook now exports a `ConnectionState` union type and a `reconnectNow()` function. The old `isConnected` boolean is preserved as deprecated for backward compatibility. A new `ConnectionBanner` component floats at the top of the graph area when the connection is lost — it shows "Reconnecting..." during active backoff and "Live updates unavailable" with a Retry button in dormant mode. The banner is hidden when connected. Server heartbeat pings (`{"type": "ping"}`) are now filtered out of `lastMessage` to avoid triggering spurious re-renders in consumers.

## 2026-05-10 — Steps 3-4: Graph editing (edgehandles + context menus)

Both extensions integrate cleanly with Cytoscape v3.30. The IConnectionTool adapter pattern works well — `ConnectionTool.ts` is 105 lines that wrap edgehandles, and `GraphContextMenu.ts` is 110 lines that wrap context-menus, both with enable/disable/destroy lifecycle. Key design decisions: (1) edgehandles creates a temporary edge on drag-complete which is immediately removed — the real edge appears after the API call and React Query refetch; (2) context menu items are created on init but hidden, then shown/hidden via the enable/disable methods; (3) delete from context menu goes through a confirmation dialog; (4) "Add Class" from canvas right-click opens a standalone dialog rather than trying to reuse the NodePanel's add form.

No surprises. Both extensions initialized without errors, TypeScript types matched the runtime API, and the CSS for context-menus imported cleanly. The `feat/graph-editing` branch is off `main` and has some duplicated lint fixes that also exist on `chore/track-lockfile-and-eslint` — these will need conflict resolution when merging both branches.
