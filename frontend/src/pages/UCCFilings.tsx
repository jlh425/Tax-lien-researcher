import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchUCCFilings, getFilingDetails } from "../api/ucc";
import { Dt, Field } from "../components/common";
import type { UCCFiling } from "../types";

export function UCCFilings() {
  const [debtorName, setDebtorName] = useState("");
  const [state, setState] = useState("");
  const [filingType, setFilingType] = useState("");
  const [submitted, setSubmitted] = useState<Record<string, string> | null>(null);
  const [selectedFiling, setSelectedFiling] = useState<{
    filing_number: string;
    state: string;
  } | null>(null);

  const searchQuery = useQuery({
    queryKey: ["ucc-filings", submitted],
    queryFn: () =>
      searchUCCFilings({
        debtor_name: submitted!.debtor_name,
        state: submitted!.state,
        filing_type: submitted!.filing_type || undefined,
      }),
    enabled: !!submitted,
  });

  const detailQuery = useQuery({
    queryKey: ["ucc-detail", selectedFiling],
    queryFn: () =>
      getFilingDetails(selectedFiling!.filing_number, selectedFiling!.state),
    enabled: !!selectedFiling,
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!debtorName.trim() || !state.trim()) return;
    setSelectedFiling(null);
    setSubmitted({ debtor_name: debtorName, state, filing_type: filingType });
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <a href="/" className="text-gray-400 hover:text-gray-600 text-sm">&larr; Dashboard</a>
        <h1 className="text-xl font-bold text-gray-900">UCC Filings</h1>
      </header>

      {/* Search form */}
      <div className="bg-white border-b border-gray-100 px-6 py-3">
        <form onSubmit={handleSearch} className="flex gap-3 items-end flex-wrap">
          <Field label="Debtor name *" value={debtorName} onChange={setDebtorName} placeholder="e.g. ACME LLC" />
          <Field label="State *" value={state} onChange={setState} placeholder="FL" maxLength={2} className="w-16" />
          <select
            className="border border-gray-200 rounded px-2 py-1.5 text-sm"
            value={filingType}
            onChange={(e) => setFilingType(e.target.value)}
          >
            <option value="">All types</option>
            <option value="initial">Initial</option>
            <option value="amendment">Amendment</option>
            <option value="continuation">Continuation</option>
          </select>
          <button
            type="submit"
            className="bg-blue-600 text-white text-sm font-medium px-4 py-1.5 rounded hover:bg-blue-700 transition"
          >
            Search
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="flex flex-1 overflow-hidden">
        {/* Filing list */}
        <div className="w-1/2 overflow-y-auto border-r border-gray-200 p-4">
          {!submitted && (
            <div className="text-center text-gray-400 mt-16">
              Enter search criteria above to find UCC filings.
            </div>
          )}
          {submitted && searchQuery.isLoading && (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="rounded border border-gray-200 bg-white p-3 animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-1/2 mb-2" />
                  <div className="h-3 bg-gray-100 rounded w-1/3" />
                </div>
              ))}
            </div>
          )}
          {submitted && searchQuery.isError && (
            <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">
              {(searchQuery.error as any)?.response?.data?.detail ?? "Search request failed."}
            </div>
          )}
          {submitted && searchQuery.data?.error && (
            <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">{searchQuery.data.error}</div>
          )}
          {submitted && !searchQuery.isLoading && !searchQuery.data?.error && (
            <>
              <div className="text-xs text-gray-400 mb-3">
                {searchQuery.data?.filings.length ?? 0} filing(s) found
              </div>
              {searchQuery.data?.filings.length === 0 && (
                <div className="text-gray-400">No filings found.</div>
              )}
              <div className="space-y-2">
                {searchQuery.data?.filings.map((f, i) => (
                  <FilingCard
                    key={f.filing_number ?? i}
                    filing={f}
                    selected={selectedFiling?.filing_number === f.filing_number}
                    onClick={() =>
                      f.filing_number && f.state
                        ? setSelectedFiling({
                            filing_number: f.filing_number,
                            state: f.state,
                          })
                        : undefined
                    }
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Detail pane */}
        <div className="w-1/2 overflow-y-auto p-4">
          {!selectedFiling && (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a filing to view details
            </div>
          )}
          {selectedFiling && detailQuery.isLoading && (
            <div className="bg-white rounded border border-gray-200 p-5 animate-pulse">
              <div className="h-5 bg-gray-200 rounded w-1/3 mb-4" />
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
          {selectedFiling && detailQuery.isError && (
            <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">
              {(detailQuery.error as any)?.response?.data?.detail ?? "Failed to load filing details."}
            </div>
          )}
          {selectedFiling && detailQuery.data && (
            <FilingDetail filing={detailQuery.data} />
          )}
        </div>
      </div>
    </div>
  );
}

function FilingCard({
  filing,
  selected,
  onClick,
}: {
  filing: UCCFiling;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded border p-3 cursor-pointer transition ${
        selected
          ? "border-blue-500 bg-blue-50"
          : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex justify-between items-start gap-2">
        <div className="min-w-0">
          <div className="font-medium text-gray-900 text-sm truncate">
            {filing.debtor_name ?? "Unknown debtor"}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            {filing.secured_party && <>Secured: {filing.secured_party}</>}
          </div>
        </div>
        <div className="text-right shrink-0">
          {filing.filing_number && (
            <div className="text-xs font-mono text-gray-600">{filing.filing_number}</div>
          )}
          {filing.filing_type && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 mt-0.5 inline-block">
              {filing.filing_type}
            </span>
          )}
        </div>
      </div>
      <div className="text-xs text-gray-400 mt-1">
        {filing.filing_date && <span className="mr-3">Filed: {filing.filing_date}</span>}
        {filing.state && <span>State: {filing.state}</span>}
      </div>
    </div>
  );
}

function FilingDetail({ filing }: { filing: UCCFiling }) {
  return (
    <div className="bg-white rounded border border-gray-200 p-5">
      <h2 className="text-lg font-bold text-gray-900 mb-4">Filing Details</h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <Dt label="Filing Number" value={filing.filing_number} />
        <Dt label="Filing Date" value={filing.filing_date} />
        <Dt label="Lapse Date" value={filing.lapse_date} />
        <Dt label="Filing Type" value={filing.filing_type} />
        <Dt label="Debtor" value={filing.debtor_name} />
        <Dt label="Secured Party" value={filing.secured_party} />
        <Dt label="State" value={filing.state} />
      </dl>
      {filing.collateral && (
        <div className="mt-4">
          <div className="text-xs font-medium text-gray-500 mb-1">Collateral</div>
          <div className="text-sm text-gray-900 bg-gray-50 rounded p-3">{filing.collateral}</div>
        </div>
      )}
    </div>
  );
}

