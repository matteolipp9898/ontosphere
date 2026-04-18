import { Routes, Route } from "react-router-dom";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import NewOntologyWizard from "@/pages/NewOntologyWizard";
import OntologyEditor from "@/pages/OntologyEditor";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/ontologies/new" element={<NewOntologyWizard />} />
        <Route path="/ontologies/:id" element={<OntologyEditor />} />
      </Route>
    </Routes>
  );
}

export default App;
