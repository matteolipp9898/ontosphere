/**
 * IConnectionTool — thin adapter for drag-to-connect behaviour.
 *
 * Currently backed by cytoscape-edgehandles. If that plugin breaks or
 * needs replacing, swap this single file with a manual implementation
 * (~100-150 lines using cytoscape core events).
 */

import type { Core, EdgeSingular, NodeSingular } from "cytoscape";
import edgehandles from "cytoscape-edgehandles";

// Register the extension once
let registered = false;
function ensureRegistered(cy: typeof import("cytoscape").default) {
  if (!registered) {
    try {
      cy.use(edgehandles);
    } catch {
      // Already registered
    }
    registered = true;
  }
}

export interface EdgeCreateEvent {
  sourceId: string;
  targetId: string;
  sourceUri: string;
  targetUri: string;
}

export interface IConnectionTool {
  enable(): void;
  disable(): void;
  destroy(): void;
}

export interface ConnectionToolOptions {
  /** Called when the user completes a drag-to-connect gesture. */
  onEdgeCreate: (event: EdgeCreateEvent) => void;
}

/**
 * Create a connection tool attached to the given Cytoscape instance.
 * Starts in disabled state — call `.enable()` to activate.
 */
export function createConnectionTool(
  cy: Core,
  cytoscape: typeof import("cytoscape").default,
  options: ConnectionToolOptions,
): IConnectionTool {
  ensureRegistered(cytoscape);

  const eh = cy.edgehandles({
    canConnect: (source: NodeSingular, target: NodeSingular) =>
      source.id() !== target.id(),
    edgeParams: (source: NodeSingular, target: NodeSingular) => ({
      data: {
        id: `_tmp_${source.id()}_${target.id()}`,
        source: source.id(),
        target: target.id(),
        edge_type: "RELATED_TO",
        label: "RELATED_TO",
      },
    }),
    snap: true,
    snapThreshold: 50,
    hoverDelay: 150,
  });

  // When the user completes a drag, edgehandles adds a temporary edge.
  // We remove it immediately and fire our callback — the real edge will
  // appear when React Query refetches graph data from the backend.
  cy.on(
    "ehcomplete",
    (
      _event: unknown,
      source: NodeSingular,
      target: NodeSingular,
      addedEdge: EdgeSingular,
    ) => {
      addedEdge.remove();
      options.onEdgeCreate({
        sourceId: source.id(),
        targetId: target.id(),
        sourceUri: source.data("uri") as string,
        targetUri: target.data("uri") as string,
      });
    },
  );

  // Start disabled
  eh.disable();
  eh.disableDrawMode();

  return {
    enable() {
      eh.enable();
      eh.enableDrawMode();
    },
    disable() {
      eh.disable();
      eh.disableDrawMode();
    },
    destroy() {
      eh.destroy();
    },
  };
}
