import { Routes, Route, Navigate } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { CourtRecords } from "./pages/CourtRecords";
import { UCCFilings } from "./pages/UCCFilings";
import { Settings } from "./pages/Settings";
import { QueueHistory } from "./pages/QueueHistory";
import { Login } from "./pages/Login";
import { useAuthStore } from "./stores/authStore";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/court-records" element={<RequireAuth><CourtRecords /></RequireAuth>} />
      <Route path="/ucc" element={<RequireAuth><UCCFilings /></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
      <Route path="/queue" element={<RequireAuth><QueueHistory /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
