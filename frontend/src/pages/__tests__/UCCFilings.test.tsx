import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { UCCFilings } from "../UCCFilings";

vi.mock("../../api/ucc", () => ({
  searchUCCFilings: vi.fn(),
  getFilingDetails: vi.fn(),
}));

import { searchUCCFilings, getFilingDetails } from "../../api/ucc";

const mockSearchFilings = vi.mocked(searchUCCFilings);
const mockGetDetail = vi.mocked(getFilingDetails);

beforeEach(() => {
  mockSearchFilings.mockReset();
  mockGetDetail.mockReset();
});

describe("UCCFilings", () => {
  it("renders heading", () => {
    renderWithProviders(<UCCFilings />);
    expect(screen.getByText("UCC Filings")).toBeInTheDocument();
  });

  it("renders search form with debtor name field", () => {
    renderWithProviders(<UCCFilings />);
    expect(screen.getByPlaceholderText("e.g. ACME LLC")).toBeInTheDocument();
  });

  it("renders state input field", () => {
    renderWithProviders(<UCCFilings />);
    expect(screen.getByPlaceholderText("FL")).toBeInTheDocument();
  });

  it("has filing type dropdown", () => {
    renderWithProviders(<UCCFilings />);
    expect(screen.getByText("All types")).toBeInTheDocument();
    expect(screen.getByText("Initial")).toBeInTheDocument();
    expect(screen.getByText("Amendment")).toBeInTheDocument();
    expect(screen.getByText("Continuation")).toBeInTheDocument();
  });

  it("renders Search button", () => {
    renderWithProviders(<UCCFilings />);
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("shows empty state before search", () => {
    renderWithProviders(<UCCFilings />);
    expect(
      screen.getByText("Enter search criteria above to find UCC filings."),
    ).toBeInTheDocument();
  });

  it("shows detail pane placeholder before selection", () => {
    renderWithProviders(<UCCFilings />);
    expect(
      screen.getByText("Select a filing to view details"),
    ).toBeInTheDocument();
  });

  it("does not search when debtor name and state are empty", async () => {
    renderWithProviders(<UCCFilings />);
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(mockSearchFilings).not.toHaveBeenCalled();
  });

  it("does not search when only debtor name is filled", async () => {
    renderWithProviders(<UCCFilings />);
    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(mockSearchFilings).not.toHaveBeenCalled();
  });

  it("searches and displays filing results", async () => {
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

  it("shows secured party in filing card", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [
        {
          filing_number: "UCC-001",
          filing_date: null,
          lapse_date: null,
          filing_type: null,
          debtor_name: "Test Corp",
          secured_party: "Big Bank",
          collateral: null,
          state: "FL",
        },
      ],
      error: null,
    });

    renderWithProviders(<UCCFilings />);
    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "Test");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText(/Secured: Big Bank/)).toBeInTheDocument();
    });
  });

  it("shows no filings found for empty results", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [],
      error: null,
    });

    renderWithProviders(<UCCFilings />);
    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "Unknown");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("No filings found.")).toBeInTheDocument();
    });
    expect(screen.getByText("0 filing(s) found")).toBeInTheDocument();
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

  it("shows inline error from API response", async () => {
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

  it("shows error when search request rejects", async () => {
    mockSearchFilings.mockRejectedValue(new Error("Network error"));

    renderWithProviders(<UCCFilings />);

    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("Search request failed.")).toBeInTheDocument();
    });
  });

  it("shows error when detail fetch fails", async () => {
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

  it("shows multiple filing results", async () => {
    mockSearchFilings.mockResolvedValue({
      filings: [
        {
          filing_number: "UCC-001",
          filing_date: "2023-01-15",
          lapse_date: null,
          filing_type: "initial",
          debtor_name: "ACME LLC",
          secured_party: "Bank A",
          collateral: null,
          state: "FL",
        },
        {
          filing_number: "UCC-002",
          filing_date: "2023-06-01",
          lapse_date: null,
          filing_type: "amendment",
          debtor_name: "ACME LLC",
          secured_party: "Bank B",
          collateral: null,
          state: "FL",
        },
      ],
      error: null,
    });

    renderWithProviders(<UCCFilings />);

    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("2 filing(s) found")).toBeInTheDocument();
    });
    expect(screen.getByText("UCC-001")).toBeInTheDocument();
    expect(screen.getByText("UCC-002")).toBeInTheDocument();
  });
});
