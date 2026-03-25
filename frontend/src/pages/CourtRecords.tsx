import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchFederalCases, getCaseDetails, searchStateLiens } from "../api/courtRecords";
import type { CourtCase, Lien } from "../types";

type Tab = "cases" | "liens";

export function CourtRecords() {
  const [tab, setTab] = useState<Tab>("cases");
  const [partyName, setPartyName] = useState("");
  const [debtorName, setDebtorName] = useState("");
  const [state, setState] = useState("");
  const [caseType, setCaseType] = useState("");
  const [lienType, setLienType] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<{
    tab: Tab;
    params: Record<string, string>;
  } | null>(null);

  const casesQuery = useQuery({
    queryKey: ["federal-cases", submitted?.params],
    queryFn: () =>
      searchFederalCases({
        party_name: submitted!.params.party_name,
        state: submitted!.params.state || undefined,
        case_type: submitted!.params.case_type || undefined,
      }),
    enabled: submitted?.tab === "cases",
  });

  const liensQuery = useQuery({
    queryKey: ["state-liens", submitted?.params],
    queryFn: () =>
      searchStateLiens({
        debtor_name: submitted!.params.debtor_name,
        state: submitted!.params.state,
        lien_type: submitted!.params.lien_type || undefined,
      }),
    enabled: submitted?.tab === "liens",
  });

  const detailQuery = useQuery({
    queryKey: ["case-detail", selectedCaseId],
    queryFn: () => getCaseDetails(selectedCaseId!),
    enabled: !!selectedCaseId,
  });

  function handleCaseSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!partyName.trim()) return;
    setSelectedCaseId(null);
    setSubmitted({
      tab: "cases",
      params: { party_name: partyName, state, case_type: caseType },
    });
  }

  function handleLienSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!debtorName.trim() || !state.trim()) return;
    setSubmitted({
      tab: "liens",
      params: { debtor_name: debtorName, state, lien_type: lienType },
    });
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <a href="/" className="text-gray-400 hover:text-gray-600 text-sm">&larr; Dashboard</a>
        <h1 className="text-xl font-bold text-gray-900">Court Records</h1>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-100 px-6 flex gap-0">
        <TabBtn active={tab === "cases"} onClick={() => setTab("cases")}>
          Federal Cases
        </TabBtn>
        <TabBtn active={tab === "liens"} onClick={() => setTab("liens")}>
          State Liens
        </TabBtn>
      </div>

      {/* Search forms */}
      <div className="bg-white border-b border-gray-100 px-6 py-3">
        {tab === "cases" ? (
          <form onSubmit={handleCaseSearch} className="flex gap-3 items-end flex-wrap">
            <Field label="Party name *" value={partyName} onChange={setPartyName} placeholder="e.g. Smith" />
            <Field label="State" value={state} onChange={setState} placeholder="FL" maxLength={2} className="w-16" />
            <select
              className="border border-gray-200 rounded px-2 py-1.5 text-sm"
              value={caseType}
              onChange={(e) => setCaseType(e.target.value)}
            >
              <option value="">All types</option>
              <option value="civil">Civil</option>
              <option value="bankruptcy">Bankruptcy</option>
              <option value="criminal">Criminal</option>
            </select>
            <button
              type="submit"
              className="bg-blue-600 text-white text-sm font-medium px-4 py-1.5 rounded hover:bg-blue-700 transition"
            >
              Search
            </button>
          </form>
        ) : (
          <form onSubmit={handleLienSearch} className="flex gap-3 items-end flex-wrap">
            <Field label="Debtor name *" value={debtorName} onChange={setDebtorName} placeholder="e.g. ACME LLC" />
            <Field label="State *" value={state} onChange={setState} placeholder="FL" maxLength={2} className="w-16" />
            <select
              className="border border-gray-200 rounded px-2 py-1.5 text-sm"
              value={lienType}
              onChange={(e) => setLienType(e.target.value)}
            >
              <option value="">All types</option>
              <option value="tax">Tax Lien</option>
              <option value="judgment">Judgment Lien</option>
              <option value="mechanics">Mechanic's Lien</option>
            </select>
            <button
              type="submit"
              className="bg-blue-600 text-white text-sm font-medium px-4 py-1.5 rounded hover:bg-blue-700 transition"
            >
              Search
            </button>
          </form>
        )}
      </div>

      {/* Results */}
      <div className="flex flex-1 overflow-hidden">
        {/* List pane */}
        <div className={`overflow-y-auto p-4 ${tab === "cases" && submitted?.tab === "cases" ? "w-1/2 border-r border-gray-200" : "flex-1"}`}>
          {tab === "cases" && submitted?.tab === "cases" && (
            <>
              {casesQuery.isError && (
                <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700 mb-3">
                  {(casesQuery.error as any)?.response?.data?.detail ?? "Search request failed."}
                </div>
              )}
              {!casesQuery.isError && (
                <CaseResults
                  cases={casesQuery.data?.cases ?? []}
                  error={casesQuery.data?.error ?? null}
                  isLoading={casesQuery.isLoading}
                  selectedId={selectedCaseId}
                  onSelect={setSelectedCaseId}
                />
              )}
            </>
          )}
          {tab === "liens" && submitted?.tab === "liens" && (
            <>
              {liensQuery.isError && (
                <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700 mb-3">
                  {(liensQuery.error as any)?.response?.data?.detail ?? "Search request failed."}
                </div>
              )}
              {!liensQuery.isError && (
                <LienResults
                  liens={liensQuery.data?.liens ?? []}
                  error={liensQuery.data?.error ?? null}
                  isLoading={liensQuery.isLoading}
                />
              )}
            </>
          )}
          {!submitted && (
            <div className="text-center text-gray-400 mt-16">
              Enter search criteria above to find court records.
            </div>
          )}
        </div>

        {/* Detail pane (cases only) */}
        {tab === "cases" && submitted?.tab === "cases" && (
          <div className="w-1/2 overflow-y-auto p-4">
            {!selectedCaseId && (
              <div className="flex items-center justify-center h-full text-gray-400">
                Select a case to view details
              </div>
            )}
            {selectedCaseId && detailQuery.isLoading && (
              <div className="bg-white rounded border border-gray-200 p-5 animate-pulse">
                <div className="h-5 bg-gray-200 rounded w-2/3 mb-4" />
                <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                  {[...Array(6)].map((_, i) => (
                    <div key={i}>
                      <div className="h-3 bg-gray-100 rounded w-16 mb-1" />
                      <div className="h-4 bg-gray-200 rounded w-24" />
                    </div>
                  ))}
                </div>
              </div>
            )}
            {selectedCaseId && detailQuery.isError && (
              <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">
                {(detailQuery.error as any)?.response?.data?.detail ?? "Failed to load case details."}
              </div>
            )}
            {selectedCaseId && detailQuery.data && (
              <CaseDetail caseData={detailQuery.data} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CaseResults({
  cases,
  error,
  isLoading,
  selectedId,
  onSelect,
}: {
  cases: CourtCase[];
  error: string | null;
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (isLoading)
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-white rounded border border-gray-200 p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
            <div className="h-3 bg-gray-100 rounded w-1/3" />
          </div>
        ))}
      </div>
    );
  if (error) return <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">{error}</div>;
  if (cases.length === 0) return <div className="text-gray-400">No cases found.</div>;

  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-400">{cases.length} case(s) found</div>
      {cases.map((c, i) => (
        <div
          key={c.case_id ?? i}
          onClick={() => c.case_id && onSelect(c.case_id)}
          className={`rounded border p-4 cursor-pointer transition ${
            selectedId === c.case_id
              ? "border-blue-500 bg-blue-50"
              : "border-gray-200 bg-white hover:border-gray-300"
          }`}
        >
          <div className="flex justify-between items-start gap-4">
            <div className="min-w-0">
              <div className="font-medium text-gray-900 truncate">{c.case_title ?? "Untitled"}</div>
              <div className="text-sm text-gray-500 mt-0.5">
                {c.court && <span className="mr-3">Court: {c.court}</span>}
                {c.case_type && <span className="mr-3">Type: {c.case_type}</span>}
                {c.filing_date && <span>Filed: {c.filing_date}</span>}
              </div>
            </div>
            {c.status && (
              <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 whitespace-nowrap shrink-0">
                {c.status}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function CaseDetail({ caseData }: { caseData: CourtCase }) {
  return (
    <div className="bg-white rounded border border-gray-200 p-5">
      <h2 className="text-lg font-bold text-gray-900 mb-4">
        {caseData.case_title ?? "Untitled Case"}
      </h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <Dt label="Case ID" value={caseData.case_id} />
        <Dt label="Court" value={caseData.court} />
        <Dt label="Case Type" value={caseData.case_type} />
        <Dt label="Filing Date" value={caseData.filing_date} />
        <Dt label="Status" value={caseData.status} />
      </dl>
      {caseData.parties.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-medium text-gray-500 mb-2">Parties</div>
          <div className="space-y-1">
            {caseData.parties.map((p, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="text-gray-900">{p.name ?? "Unknown"}</span>
                {p.role && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                    {p.role}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {caseData.docket_url && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <a
            href={`https://www.courtlistener.com${caseData.docket_url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline"
          >
            View full docket on CourtListener &rarr;
          </a>
        </div>
      )}
    </div>
  );
}

function Dt({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs text-gray-500 font-medium">{label}</dt>
      <dd className="text-gray-900 mt-0.5">{value}</dd>
    </div>
  );
}

function LienResults({
  liens,
  error,
  isLoading,
}: {
  liens: Lien[];
  error: string | null;
  isLoading: boolean;
}) {
  if (isLoading)
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-white rounded border border-gray-200 p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/2 mb-2" />
            <div className="h-3 bg-gray-100 rounded w-1/4" />
          </div>
        ))}
      </div>
    );
  if (error) return <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">{error}</div>;
  if (liens.length === 0) return <div className="text-gray-400">No liens found.</div>;

  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-400">{liens.length} lien(s) found</div>
      {liens.map((l, i) => (
        <div key={l.filing_number ?? i} className="bg-white rounded border border-gray-200 p-4">
          <div className="flex justify-between items-start gap-4">
            <div>
              <div className="font-medium text-gray-900">
                {l.debtor ?? "Unknown debtor"}
              </div>
              <div className="text-sm text-gray-500 mt-0.5">
                {l.creditor && <span className="mr-3">Creditor: {l.creditor}</span>}
                {l.filing_date && <span className="mr-3">Filed: {l.filing_date}</span>}
                {l.filing_number && <span>#{l.filing_number}</span>}
              </div>
            </div>
            <div className="text-right shrink-0">
              {l.amount != null && (
                <div className="font-medium text-gray-900">
                  ${l.amount.toLocaleString()}
                </div>
              )}
              {l.lien_type && (
                <span className="text-xs px-2 py-0.5 rounded bg-orange-100 text-orange-700 mt-0.5 inline-block">
                  {l.lien_type}
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
        active
          ? "border-blue-600 text-blue-600"
          : "border-transparent text-gray-500 hover:text-gray-700"
      }`}
    >
      {children}
    </button>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  maxLength?: number;
  className?: string;
}) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-xs text-gray-500 font-medium">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        className={`border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 ${className}`}
      />
    </label>
  );
}
