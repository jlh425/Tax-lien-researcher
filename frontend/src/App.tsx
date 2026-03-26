import { Routes, Route, Navigate } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { CourtRecords } from "./pages/CourtRecords";
import { UCCFilings } from "./pages/UCCFilings";
import { Settings } from "./pages/Settings";
import { QueueHistory } from "./pages/QueueHistory";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/court-records" element={<CourtRecords />} />
      <Route path="/ucc" element={<UCCFilings />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/queue" element={<QueueHistory />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
