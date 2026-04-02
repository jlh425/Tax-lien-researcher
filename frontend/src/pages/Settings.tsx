import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type Provider,
  deleteApiKey,
  getApiKeys,
  getLlmStatus,
  saveApiKey,
  setLlmPreference,
} from "../api/settings";

const KEY_PROVIDERS: { value: Provider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "groq", label: "Groq" },
];

const ALL_PROVIDERS: { value: Provider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "groq", label: "Groq" },
  { value: "ollama", label: "Ollama (local)" },
];

export function Settings() {
  // BYOK state
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [prefProvider, setPrefProvider] = useState<Provider>("anthropic");
  const [prefModel, setPrefModel] = useState("");
  const [prefBaseUrl, setPrefBaseUrl] = useState("http://localhost:11434");

  const queryClient = useQueryClient();

  const { data: keysData } = useQuery({
    queryKey: ["api-keys"],
    queryFn: getApiKeys,
  });

  const { data: llmStatus } = useQuery({
    queryKey: ["llm-status"],
    queryFn: getLlmStatus,
  });

  const needsSetup = llmStatus && !llmStatus.has_user_key && !llmStatus.has_server_llm;

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    queryClient.invalidateQueries({ queryKey: ["llm-status"] });
  };

  const saveMutation = useMutation({
    mutationFn: () => saveApiKey(provider, apiKey),
    onSuccess: () => {
      setApiKey("");
      invalidateAll();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (p: Provider) => deleteApiKey(p),
    onSuccess: invalidateAll,
  });

  const prefMutation = useMutation({
    mutationFn: () =>
      setLlmPreference(
        prefProvider,
        prefModel,
        prefProvider === "ollama" ? prefBaseUrl : undefined,
      ),
    onSuccess: invalidateAll,
  });

  function handleSaveKey(e: React.FormEvent) {
    e.preventDefault();
    if (apiKey.length >= 10) saveMutation.mutate();
  }

  function handleSavePref(e: React.FormEvent) {
    e.preventDefault();
    if (prefModel.trim()) prefMutation.mutate();
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          Back to Dashboard
        </a>
      </div>

      {/* Setup Required Banner */}
      {needsSetup && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 mb-6">
          <h2 className="text-amber-800 font-semibold text-base mb-1">
            LLM Configuration Required
          </h2>
          <p className="text-amber-700 text-sm mb-3">
            No AI provider is configured. Research features (scanning, analysis, scoring)
            require an AI model to function. Please complete one of the following:
          </p>
          <ul className="text-amber-700 text-sm list-disc list-inside space-y-1">
            <li>
              <strong>Add an API key below</strong> for Anthropic, OpenAI, or Groq, then set
              your LLM preference.
            </li>
            <li>
              <strong>Or select Ollama</strong> in the LLM Preference section below and enter
              your Ollama server URL.
            </li>
          </ul>
        </div>
      )}

      {/* API Keys — BYOK */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">API Keys</h2>
        <p className="text-sm text-gray-500 mb-4">
          Add your own LLM API keys so research tasks use your billing account.
          Keys are encrypted at rest and never exposed via the API.
        </p>

        {/* Stored keys list */}
        {keysData?.keys && keysData.keys.length > 0 && (
          <div className="mb-4 space-y-2">
            {keysData.keys.map((k) => (
              <div
                key={k.provider}
                className="flex items-center justify-between bg-gray-50 rounded px-3 py-2"
              >
                <div>
                  <span className="text-sm font-medium text-gray-800 capitalize">
                    {k.provider}
                  </span>
                  <span className="ml-2 text-xs text-gray-400 font-mono">{k.masked_key}</span>
                </div>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(k.provider as Provider)}
                  disabled={deleteMutation.isPending}
                  className="text-xs text-red-600 hover:text-red-800 font-medium"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Add key form */}
        <form onSubmit={handleSaveKey} className="flex items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as Provider)}
              className="border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {KEY_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-ant-..."
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <button
            type="submit"
            disabled={apiKey.length < 10 || saveMutation.isPending}
            className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
          >
            {saveMutation.isPending ? "Saving..." : "Save Key"}
          </button>
        </form>
        {saveMutation.isError && (
          <p className="text-xs text-red-600 mt-2">
            Failed to save key. Please check the key and try again.
          </p>
        )}
        {saveMutation.isSuccess && (
          <p className="text-xs text-green-600 mt-2">Key saved successfully.</p>
        )}
      </section>

      {/* LLM Preference */}
      <section className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">LLM Preference</h2>
        <p className="text-sm text-gray-500 mb-4">
          Choose which provider and model to use for your research tasks.
          For cloud providers you must have a saved API key. For Ollama, provide your server URL.
        </p>
        {keysData?.llm_provider && (
          <p className="text-sm text-gray-600 mb-3">
            Current:{" "}
            <span className="font-medium capitalize">{keysData.llm_provider}</span>
            {keysData.llm_model && (
              <span className="ml-1 text-gray-400">({keysData.llm_model})</span>
            )}
            {keysData.llm_provider === "ollama" && keysData.ollama_base_url && (
              <span className="ml-1 text-gray-400">@ {keysData.ollama_base_url}</span>
            )}
          </p>
        )}
        <form onSubmit={handleSavePref} className="space-y-3">
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Provider</label>
              <select
                value={prefProvider}
                onChange={(e) => setPrefProvider(e.target.value as Provider)}
                className="border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {ALL_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Model</label>
              <input
                type="text"
                value={prefModel}
                onChange={(e) => setPrefModel(e.target.value)}
                placeholder={
                  prefProvider === "ollama" ? "llama3.1:8b" : "claude-sonnet-4-20250514"
                }
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <button
              type="submit"
              disabled={!prefModel.trim() || prefMutation.isPending}
              className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
            >
              {prefMutation.isPending ? "Saving..." : "Set Preference"}
            </button>
          </div>

          {/* Ollama URL input — only visible when Ollama is selected */}
          {prefProvider === "ollama" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Ollama Server URL
              </label>
              <input
                type="url"
                value={prefBaseUrl}
                onChange={(e) => setPrefBaseUrl(e.target.value)}
                placeholder="http://localhost:11434"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <p className="text-xs text-gray-400 mt-1">
                The base URL of your running Ollama instance (no trailing slash).
              </p>
            </div>
          )}
        </form>
        {prefMutation.isSuccess && (
          <p className="text-xs text-green-600 mt-2">Preference updated.</p>
        )}
      </section>
    </div>
  );
}
