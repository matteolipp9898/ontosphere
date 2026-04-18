import { create } from "zustand";
import type { ValidationResult } from "@/types/ontology";

interface OntologyStoreState {
  selectedNodeId: string | null;
  editMode: boolean;
  searchQuery: string;
  sidePanel: "details" | "provenance" | "validation" | null;
  validationResult: ValidationResult | null;

  setSelectedNode: (id: string | null) => void;
  toggleEditMode: () => void;
  setSearchQuery: (query: string) => void;
  setSidePanel: (
    panel: "details" | "provenance" | "validation" | null,
  ) => void;
  setValidationResult: (result: ValidationResult | null) => void;
}

export const useOntologyStore = create<OntologyStoreState>((set) => ({
  selectedNodeId: null,
  editMode: false,
  searchQuery: "",
  sidePanel: null,
  validationResult: null,

  setSelectedNode: (id) => set({ selectedNodeId: id }),
  toggleEditMode: () => set((state) => ({ editMode: !state.editMode })),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSidePanel: (panel) => set({ sidePanel: panel }),
  setValidationResult: (result) => set({ validationResult: result }),
}));
