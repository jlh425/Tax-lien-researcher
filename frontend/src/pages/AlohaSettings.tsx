import { useState } from "react";

interface ScoringWeights {
  lien_to_value: number;
  redemption_urgency: number;
  owner_motivation: number;
  contact_reachability: number;
}

const DEFAULT_WEIGHTS: ScoringWeights = {
  lien_to_value: 25,
  redemption_urgency: 25,
  owner_motivation: 25,
  contact_reachability: 25,
};

export function AlohaSettings() {
  const [mapsApiKey, setMapsApiKey] = useState("");
  const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);
  const [includeScreenshots, setIncludeScreenshots] = useState(true);
  const [saved, setSaved] = useState(false);

  function handleWeightChange(key: keyof ScoringWeights, value: string) {
    const num = parseInt(value) || 0;
    setWeights((w) => ({ ...w, [key]: Math.min(100, Math.max(0, num)) }));
  }

  function handleSave() {
    // TODO: Persist to backend when API endpoint is available
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-6 space-y-8">
        <h2 className="text-lg font-bold text-gray-900">Aloha Settings</h2>

        {/* Google Maps API Key */}
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Google Maps API Key</h3>
          <p className="text-xs text-gray-500 mb-2">
            Used for GIS map thumbnails on parcel cards. Optional.
          </p>
          <input
            type="password"
            value={mapsApiKey}
            onChange={(e) => setMapsApiKey(e.target.value)}
            placeholder="AIza..."
            className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </section>

        {/* Scoring Weights */}
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Scoring Weights (Lien Certificate)
          </h3>
          <p className="text-xs text-gray-500 mb-3">
            Adjust how each factor contributes to the overall opportunity score.
            Weights should sum to 100.
          </p>
          <div className="space-y-3">
            {([
              ["lien_to_value", "Lien-to-Value Ratio"],
              ["redemption_urgency", "Redemption Urgency"],
              ["owner_motivation", "Owner Motivation"],
              ["contact_reachability", "Contact Reachability"],
            ] as const).map(([key, label]) => (
              <label key={key} className="flex items-center gap-3">
                <span className="text-sm text-gray-600 w-44">{label}</span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={weights[key]}
                  onChange={(e) => handleWeightChange(key, e.target.value)}
                  className="w-20 border border-gray-200 rounded px-2 py-1 text-sm text-center"
                />
                <span className="text-xs text-gray-400">%</span>
              </label>
            ))}
            <p className={`text-xs ${totalWeight === 100 ? "text-green-600" : "text-red-500"}`}>
              Total: {totalWeight}%{totalWeight !== 100 && " (should be 100%)"}
            </p>
          </div>
        </section>

        {/* PDF Export */}
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">PDF Export Defaults</h3>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeScreenshots}
              onChange={(e) => setIncludeScreenshots(e.target.checked)}
              className="rounded border-gray-300"
            />
            <span className="text-sm text-gray-600">Include screenshots in reports</span>
          </label>
        </section>

        {/* Save */}
        <div className="pt-4 border-t border-gray-200">
          <button
            onClick={handleSave}
            className="bg-blue-600 text-white text-sm font-medium px-6 py-2 rounded hover:bg-blue-700 transition"
          >
            Save Settings
          </button>
          {saved && (
            <span className="ml-3 text-sm text-green-600">Settings saved</span>
          )}
        </div>
      </div>
    </div>
  );
}
