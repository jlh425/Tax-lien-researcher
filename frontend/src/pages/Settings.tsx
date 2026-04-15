import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type Provider,
  type ConfiguredLlm,
  addConfiguredLlm,
  deleteConfiguredLlm,
  getConfiguredLlms,
  getLlmStatus,
  setActiveLlm,
  testLlmConnection,
} from "../api/settings";

const PROVIDERS: { value: Provider; label: string; needsKey: boolean }[] = [
  { value: "anthropic", label: "Anthropic", needsKey: true },
  { value: "openai", label: "OpenAI", needsKey: true },
  { value: "groq", label: "Groq", needsKey: true },
  { value: "ollama", label: "Ollama (local)", needsKey: false },
];

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "bg-amber-500",
  openai: "bg-emerald-500",
  groq: "bg-purple-500",
  ollama: "bg-blue-500",
};

const MODEL_PLACEHOLDERS: Record<string, string> = {
  anthropic: "claude-sonnet-4-20250514",
  openai: "gpt-4o",
  groq: "llama-3.3-70b-versatile",
  ollama: "llama3.1:8b",
};

export function Settings() {
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("http://localhost:11434");
  const [testMessage, setTestMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const queryClient = useQueryClient();
  const needsKey = PROVIDERS.find((p) => p.value === provider)?.needsKey ?? true;

  const { data: llmStatus } = useQuery({
    queryKey: ["llm-status"],
    queryFn: getLlmStatus,
  });

  const { data: configuredData } = useQuery({
    queryKey: ["configured-llms"],
    queryFn: getConfiguredLlms,
  });

  const llms: ConfiguredLlm[] = configuredData?.llms ?? [];
  const needsSetup = llmStatus && !llmStatus.has_user_key && !llmStatus.has_server_llm;

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["configured-llms"] });
    queryClient.invalidateQueries({ queryKey: ["llm-status"] });
  };

  // Test & Add mutation — test first, then save on success
  const testAndAddMutation = useMutation({
    mutationFn: async () => {
      setTestMessage(null);

      // Step 1: Test connection
      const testResult = await testLlmConnection(
        provider,
        model,
        needsKey ? apiKey || undefined : undefined,
        provider === "ollama" ? baseUrl : undefined,
      );

      if (!testResult.success) {
        throw new Error(testResult.message);
      }

      // Step 2: Save on success
      const addResult = await addConfiguredLlm(
        provider,
        model,
        needsKey ? apiKey || undefined : undefined,
        provider === "ollama" ? baseUrl : undefined,
      );

      return addResult;
    },
    onSuccess: (result) => {
      setTestMessage({
        type: "success",
        text: `${result.llm.provider}/${result.llm.model} added successfully`,
      });
      setModel("");
      setApiKey("");
      invalidateAll();
    },
    onError: (err: Error) => {
      setTestMessage({ type: "error", text: err.message });
    },
  });

  const activateMutation = useMutation({
    mutationFn: (llmId: string) => setActiveLlm(llmId),
    onSuccess: invalidateAll,
  });

  const removeMutation = useMutation({
    mutationFn: (llmId: string) => deleteConfiguredLlm(llmId),
    onSuccess: invalidateAll,
  });

  function handleTestAndAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!model.trim()) return;
    if (needsKey && !apiKey) {
      // Check if we might have a stored key (allow empty for existing keys)
      // The backend will check for stored keys
    }
    testAndAddMutation.mutate();
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
          <p className="text-amber-700 text-sm">
            No AI provider is configured. Add an LLM below to enable research
            features (scanning, analysis, scoring).
          </p>
        </div>
      )}

      {/* Add LLM Form */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Add LLM</h2>
        <p className="text-sm text-gray-500 mb-4">
          Configure an AI provider. The connection will be tested before saving.
        </p>

        <form onSubmit={handleTestAndAdd} className="space-y-3">
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Provider
              </label>
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value as Provider);
                  setTestMessage(null);
                }}
                className="border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Model
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={MODEL_PLACEHOLDERS[provider] ?? "model-name"}
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          </div>

          {/* API Key — hidden for Ollama */}
          {needsKey && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Leave blank to use stored key"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <p className="text-xs text-gray-400 mt-1">
                If you already have a key stored for this provider, you can
                leave this blank.
              </p>
            </div>
          )}

          {/* Ollama URL — only shown for Ollama */}
          {provider === "ollama" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Ollama Server URL
              </label>
              <input
                type="url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:11434"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={!model.trim() || testAndAddMutation.isPending}
            className="bg-blue-600 text-white text-sm font-medium px-5 py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
          >
            {testAndAddMutation.isPending ? "Testing connection..." : "Test & Add"}
          </button>
        </form>

        {/* Test result message */}
        {testMessage && (
          <p
            className={`text-xs mt-3 ${
              testMessage.type === "success"
                ? "text-green-600"
                : "text-red-600"
            }`}
          >
            {testMessage.text}
          </p>
        )}
      </section>

      {/* Configured LLMs List */}
      <section className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Configured LLMs
        </h2>

        {llms.length === 0 ? (
          <p className="text-sm text-gray-400">
            No LLMs configured yet. Add one above to get started.
          </p>
        ) : (
          <div className="space-y-3">
            {llms.map((llm) => (
              <div
                key={llm.id}
                className={`flex items-center justify-between rounded-lg border px-4 py-3 ${
                  llm.is_active
                    ? "border-blue-300 bg-blue-50"
                    : "border-gray-200 bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-3">
                  {/* Provider color dot */}
                  <span
                    className={`inline-block w-3 h-3 rounded-full ${
                      PROVIDER_COLORS[llm.provider] ?? "bg-gray-400"
                    }`}
                    title={llm.provider}
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800">
                        {llm.model}
                      </span>
                      <span className="text-xs text-gray-400 capitalize">
                        {llm.provider}
                      </span>
                      {llm.is_active && (
                        <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full font-medium">
                          Active
                        </span>
                      )}
                    </div>
                    {llm.masked_key && (
                      <span className="text-xs text-gray-400 font-mono">
                        {llm.masked_key}
                      </span>
                    )}
                    {llm.base_url && (
                      <span className="text-xs text-gray-400 ml-1">
                        @ {llm.base_url}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {!llm.is_active && (
                    <button
                      type="button"
                      onClick={() => activateMutation.mutate(llm.id)}
                      disabled={activateMutation.isPending}
                      className="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-100 transition"
                    >
                      Set Active
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => removeMutation.mutate(llm.id)}
                    disabled={removeMutation.isPending}
                    className="text-xs text-red-600 hover:text-red-800 font-medium px-2 py-1 rounded hover:bg-red-100 transition"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
