/**
 * GraphContextMenu — sets up right-click context menus on the graph.
 *
 * Node menu: Edit, Delete, Add Relationship From...
 * Canvas menu: Add Class
 *
 * Uses cytoscape-context-menus (dropdown style).
 */

import type { Core, NodeSingular } from "cytoscape";
import contextMenus from "cytoscape-context-menus";

// Register the extension once
let registered = false;
function ensureRegistered(cy: typeof import("cytoscape").default) {
  if (!registered) {
    try {
      cy.use(contextMenus);
    } catch {
      // Already registered
    }
    registered = true;
  }
}

export interface GraphMenuActions {
  /** Select a node and open its detail panel in edit mode. */
  onSelectForEdit: (nodeId: string) => void;
  /** Delete a node by its URI. */
  onDeleteNode: (nodeId: string, nodeUri: string, nodeLabel: string) => void;
  /** Select a node and open the "Add Relationship" form with it as source. */
  onAddRelationshipFrom: (nodeId: string) => void;
  /** Open the "Add Class" dialog. */
  onAddClass: () => void;
}

export interface IGraphContextMenu {
  enable(): void;
  disable(): void;
  destroy(): void;
}

const EDIT_ITEMS = ["ctx-edit", "ctx-delete", "ctx-add-rel", "ctx-add-class"];

export function createGraphContextMenu(
  cy: Core,
  cytoscape: typeof import("cytoscape").default,
  actions: GraphMenuActions,
): IGraphContextMenu {
  ensureRegistered(cytoscape);

  const menu = cy.contextMenus({
    menuItems: [
      {
        id: "ctx-edit",
        content: "Edit",
        selector: "node",
        show: false,
        onClickFunction: (event) => {
          const node = event.target as NodeSingular;
          actions.onSelectForEdit(node.id());
        },
        hasTrailingDivider: false,
      },
      {
        id: "ctx-add-rel",
        content: "Add Relationship From...",
        selector: "node",
        show: false,
        onClickFunction: (event) => {
          const node = event.target as NodeSingular;
          actions.onAddRelationshipFrom(node.id());
        },
        hasTrailingDivider: true,
      },
      {
        id: "ctx-delete",
        content: "Delete",
        selector: "node",
        show: false,
        onClickFunction: (event) => {
          const node = event.target as NodeSingular;
          actions.onDeleteNode(
            node.id(),
            node.data("uri") as string,
            (node.data("label") as string) || node.id(),
          );
        },
      },
      {
        id: "ctx-add-class",
        content: "Add Class",
        selector: "node",
        coreAsWell: true,
        show: false,
        onClickFunction: () => {
          actions.onAddClass();
        },
      },
    ],
  });

  return {
    enable() {
      for (const id of EDIT_ITEMS) {
        menu.showMenuItem(id);
      }
    },
    disable() {
      for (const id of EDIT_ITEMS) {
        menu.hideMenuItem(id);
      }
    },
    destroy() {
      menu.destroy();
    },
  };
}
