import { useState } from "react";

export function Settings() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [saved, setSaved] = useState(false);

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          Back to Dashboard
        </a>
      </div>

      {/* Profile */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Profile</h2>
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded hover:bg-blue-700 transition"
            >
              Save Changes
            </button>
            {saved && <span className="text-green-600 text-sm">Saved!</span>}
          </div>
        </form>
      </section>

      {/* Subscription */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Subscription</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">
              Current plan: <span className="font-semibold text-gray-900">Free</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">10 scans/month, 50 parcels max</p>
          </div>
          <button className="bg-gray-100 text-gray-700 text-sm font-medium px-4 py-2 rounded hover:bg-gray-200 transition">
            Upgrade to Pro
          </button>
        </div>
      </section>

      {/* API Keys */}
      <section className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">API Keys</h2>
        <p className="text-sm text-gray-500">
          API keys are configured via environment variables on the server. Contact your
          administrator to update external service credentials.
        </p>
      </section>
    </div>
  );
}
