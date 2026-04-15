import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listParcels } from "../api/parcels";
import { QueueStatusBar } from "../components/QueueStatusBar";
import { useAuthStore } from "../stores/authStore";

const NAV_ITEMS = [
  { to: "/aloha/liens", label: "Liens" },
  { to: "/aloha/scans", label: "Scans" },
  { to: "/aloha/alerts", label: "Alerts" },
  { to: "/aloha/settings", label: "Settings" },
] as const;

export function AlohaLayout() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  const { data: parcels = [] } = useQuery({
    queryKey: ["parcels", {}],
    queryFn: () => listParcels({ limit: 200 }),
  });

  const lienCount = parcels.filter((p) => p.instrument_type === "lien_certificate").length;
  const deedCount = parcels.filter((p) => p.instrument_type === "tax_deed").length;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <a href="/" className="text-xl font-bold text-gray-900 hover:opacity-80 transition">
          Aloha <span className="text-blue-600">Tax Research</span>
        </a>

        {/* Aloha nav tabs */}
        <nav className="flex gap-1 ml-6">
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3 py-1.5 text-sm rounded-md transition ${
                  isActive
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Context indicator */}
        <span className="ml-auto text-xs text-gray-400">
          {parcels.length} opportunities
          {lienCount > 0 && <> &middot; {lienCount} lien certs</>}
          {deedCount > 0 && <> &middot; {deedCount} tax deeds</>}
        </span>

        <QueueStatusBar />

        <button
          onClick={() => { logout(); navigate("/login"); }}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          Sign Out
        </button>
      </header>

      {/* Content area */}
      <Outlet />
    </div>
  );
}
