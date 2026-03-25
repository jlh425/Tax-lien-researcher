import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/utils";
import { UCCFilings } from "./UCCFilings";

vi.mock("../api/ucc", () => ({
  searchUCCFilings: vi.fn(),
  getFilingDetails: vi.fn(),
}));

import { searchUCCFilings, getFilingDetails } from "../api/ucc";

const mockSearchFilings = vi.mocked(searchUCCFilings);
const mockGetDetail = vi.mocked(getFilingDetails);

describe("UCCFilings", () => {
  it("renders header and search form", () => {
    renderWithProviders(<UCCFilings />);
    expect(screen.getByText("UCC Filings")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g. ACME LLC")).toBeInTheDocument();
  });

  it("shows empty state before search", () => {
    renderWithProviders(<UCCFilings />);
    expect(
      screen.getByText("Enter search criteria above to find UCC filings."),
    ).toBeInTheDocument();
  });

  it("requires debtor name and state", async () => {
    renderWithProviders(<UCCFilings />);
    // Click search with empty fields — should not trigger query
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(mockSearchFilings).not.toHaveBeenCalled();
  });

  it("searches and displays results", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [
        {
          filing_number: "UCC-2023-001",
          filing_date: "2023-01-15",
          lapse_date: null,
          filing_type: "initial",
          debtor_name: "ACME LLC",
          secured_party: "First National Bank",
          collateral: null,
          state: "FL",
        },
      ],
      error: null,
    });

    renderWithProviders(<UCCFilings />);

    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME LLC");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("ACME LLC")).toBeInTheDocument();
    });
    expect(screen.getByText("1 filing(s) found")).toBeInTheDocument();
    expect(screen.getByText("UCC-2023-001")).toBeInTheDocument();
    expect(screen.getByText("initial")).toBeInTheDocument();
  });

  it("shows filing detail when card is clicked", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [
        {
          filing_number: "UCC-2023-001",
          filing_date: "2023-01-15",
          lapse_date: null,
          filing_type: null,
          debtor_name: "ACME LLC",
          secured_party: "First National Bank",
          collateral: null,
          state: "FL",
        },
      ],
      error: null,
    });
    mockGetDetail.mockResolvedValue({
      filing_number: "UCC-2023-001",
      filing_date: "2023-01-15",
      lapse_date: "2028-01-15",
      filing_type: "initial",
      debtor_name: "ACME LLC",
      secured_party: "First National Bank",
      collateral: "All inventory and equipment",
      state: "FL",
      error: null,
    });

    renderWithProviders(<UCCFilings />);

    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME LLC");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("ACME LLC")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText("ACME LLC"));

    await waitFor(() => {
      expect(screen.getByText("Filing Details")).toBeInTheDocument();
    });
    expect(screen.getByText("All inventory and equipment")).toBeInTheDocument();
    expect(screen.getByText("2028-01-15")).toBeInTheDocument();
  });

  it("shows inline error from API", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [],
      error: "Cobalt Intelligence API key not configured",
    });

    renderWithProviders(<UCCFilings />);

    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(
        screen.getByText("Cobalt Intelligence API key not configured"),
      ).toBeInTheDocument();
    });
  });

  it("handles detail fetch error", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [
        {
          filing_number: "UCC-001",
          filing_date: null,
          lapse_date: null,
          filing_type: null,
          debtor_name: "Test Corp",
          secured_party: null,
          collateral: null,
          state: "FL",
        },
      ],
      error: null,
    });
    mockGetDetail.mockRejectedValue({
      response: { data: { detail: "Filing UCC-001 not found in FL" } },
    });

    renderWithProviders(<UCCFilings />);

    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "Test");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("Test Corp")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText("Test Corp"));

    await waitFor(() => {
      expect(
        screen.getByText("Filing UCC-001 not found in FL"),
      ).toBeInTheDocument();
    });
  });
});
