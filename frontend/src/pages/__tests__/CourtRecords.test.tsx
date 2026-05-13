import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { CourtRecords } from "../CourtRecords";

vi.mock("../../api/courtRecords", () => ({
  searchFederalCases: vi.fn(),
  getCaseDetails: vi.fn(),
  searchStateLiens: vi.fn(),
}));

import { searchFederalCases, getCaseDetails, searchStateLiens } from "../../api/courtRecords";

const mockSearchCases = vi.mocked(searchFederalCases);
const mockGetCaseDetails = vi.mocked(getCaseDetails);
const mockSearchLiens = vi.mocked(searchStateLiens);

beforeEach(() => {
  mockSearchCases.mockReset();
  mockGetCaseDetails.mockReset();
  mockSearchLiens.mockReset();
});

describe("CourtRecords", () => {
  it("renders heading and back link", () => {
    renderWithProviders(<CourtRecords />);
    expect(screen.getByText("Court Records")).toBeInTheDocument();
  });

  it("renders Federal Cases and State Liens tabs", () => {
    renderWithProviders(<CourtRecords />);
    expect(screen.getByText("Federal Cases")).toBeInTheDocument();
    expect(screen.getByText("State Liens")).toBeInTheDocument();
  });

  it("shows search form with party name field on cases tab", () => {
    renderWithProviders(<CourtRecords />);
    expect(screen.getByPlaceholderText("e.g. Smith")).toBeInTheDocument();
  });

  it("shows empty state before any search", () => {
    renderWithProviders(<CourtRecords />);
    expect(
      screen.getByText("Enter search criteria above to find court records."),
    ).toBeInTheDocument();
  });

  it("has case type dropdown on cases tab", () => {
    renderWithProviders(<CourtRecords />);
    expect(screen.getByText("All types")).toBeInTheDocument();
    expect(screen.getByText("Civil")).toBeInTheDocument();
    expect(screen.getByText("Bankruptcy")).toBeInTheDocument();
    expect(screen.getByText("Criminal")).toBeInTheDocument();
  });

  it("renders Search button", () => {
    renderWithProviders(<CourtRecords />);
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("does not search when party name is empty", async () => {
    renderWithProviders(<CourtRecords />);
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(mockSearchCases).not.toHaveBeenCalled();
  });

  it("searches federal cases on form submit", async () => {
    mockSearchCases.mockResolvedValue({
      cases: [
        {
          case_id: "123",
          case_title: "Smith v. Jones",
          court: "flsd",
          case_type: "civil",
          filing_date: "2023-01-15",
          status: "Open",
          parties: [],
          docket_url: null,
        },
      ],
      error: null,
    });

    renderWithProviders(<CourtRecords />);

    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Smith");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("Smith v. Jones")).toBeInTheDocument();
    });
    expect(screen.getByText("1 case(s) found")).toBeInTheDocument();
  });

  it("shows case metadata (court, type, date)", async () => {
    mockSearchCases.mockResolvedValue({
      cases: [
        {
          case_id: "123",
          case_title: "Smith v. Jones",
          court: "flsd",
          case_type: "civil",
          filing_date: "2023-01-15",
          status: "Open",
          parties: [],
          docket_url: null,
        },
      ],
      error: null,
    });

    renderWithProviders(<CourtRecords />);
    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Smith");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText(/Court: flsd/)).toBeInTheDocument();
      expect(screen.getByText(/Type: civil/)).toBeInTheDocument();
      expect(screen.getByText(/Filed: 2023-01-15/)).toBeInTheDocument();
    });
  });

  it("shows no cases found message for empty results", async () => {
    mockSearchCases.mockResolvedValue({
      cases: [],
      error: null,
    });

    renderWithProviders(<CourtRecords />);
    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Smith");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("No cases found.")).toBeInTheDocument();
    });
  });

  it("shows case detail when a case is clicked", async () => {
    mockSearchCases.mockResolvedValue({
      cases: [
        {
          case_id: "123",
          case_title: "Smith v. Jones",
          court: "flsd",
          case_type: null,
          filing_date: null,
          status: null,
          parties: [],
          docket_url: null,
        },
      ],
      error: null,
    });
    mockGetCaseDetails.mockResolvedValue({
      case_id: "123",
      case_title: "Smith v. Jones",
      court: "flsd",
      case_type: "civil",
      filing_date: "2023-01-15",
      status: "Open",
      parties: [{ name: "Smith", role: "Plaintiff" }],
      docket_url: "/docket/123/",
    });

    renderWithProviders(<CourtRecords />);

    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Smith");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("Smith v. Jones")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText("Smith v. Jones"));

    await waitFor(() => {
      expect(screen.getByText("Plaintiff")).toBeInTheDocument();
    });
  });

  it("shows select case placeholder in detail pane", async () => {
    mockSearchCases.mockResolvedValue({
      cases: [
        {
          case_id: "123",
          case_title: "Test Case",
          court: "test",
          case_type: null,
          filing_date: null,
          status: null,
          parties: [],
          docket_url: null,
        },
      ],
      error: null,
    });

    renderWithProviders(<CourtRecords />);
    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Test");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("Test Case")).toBeInTheDocument();
    });
    expect(screen.getByText("Select a case to view details")).toBeInTheDocument();
  });

  it("shows inline error for search API error response", async () => {
    mockSearchCases.mockResolvedValue({
      cases: [],
      error: "API error 403",
    });

    renderWithProviders(<CourtRecords />);
    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Smith");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("API error 403")).toBeInTheDocument();
    });
  });

  it("shows error when search request fails", async () => {
    mockSearchCases.mockRejectedValue(new Error("Network failure"));

    renderWithProviders(<CourtRecords />);
    await userEvent.type(screen.getByPlaceholderText("e.g. Smith"), "Smith");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("Search request failed.")).toBeInTheDocument();
    });
  });

  it("switches to State Liens tab and shows lien search form", async () => {
    renderWithProviders(<CourtRecords />);

    await userEvent.click(screen.getByText("State Liens"));

    expect(screen.getByPlaceholderText("e.g. ACME LLC")).toBeInTheDocument();
  });

  it("has lien type dropdown on liens tab", async () => {
    renderWithProviders(<CourtRecords />);
    await userEvent.click(screen.getByText("State Liens"));

    expect(screen.getByText("Tax Lien")).toBeInTheDocument();
    expect(screen.getByText("Judgment Lien")).toBeInTheDocument();
    expect(screen.getByText("Mechanic's Lien")).toBeInTheDocument();
  });

  it("searches state liens on form submit", async () => {
    mockSearchLiens.mockResolvedValue({
      liens: [
        {
          filing_number: "LN-001",
          debtor: "ACME LLC",
          creditor: "IRS",
          amount: 50000,
          filing_date: "2023-06-01",
          lien_type: "tax",
          state: "FL",
        },
      ],
      error: null,
    });

    renderWithProviders(<CourtRecords />);

    await userEvent.click(screen.getByText("State Liens"));
    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME LLC");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("ACME LLC")).toBeInTheDocument();
    });
    expect(screen.getByText("$50,000")).toBeInTheDocument();
    expect(screen.getByText("1 lien(s) found")).toBeInTheDocument();
  });

  it("shows no liens found for empty lien results", async () => {
    mockSearchLiens.mockResolvedValue({
      liens: [],
      error: null,
    });

    renderWithProviders(<CourtRecords />);
    await userEvent.click(screen.getByText("State Liens"));
    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME LLC");
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("No liens found.")).toBeInTheDocument();
    });
  });

  it("does not search liens when debtor name is empty", async () => {
    renderWithProviders(<CourtRecords />);
    await userEvent.click(screen.getByText("State Liens"));
    await userEvent.type(screen.getByPlaceholderText("FL"), "FL");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(mockSearchLiens).not.toHaveBeenCalled();
  });

  it("does not search liens when state is empty", async () => {
    renderWithProviders(<CourtRecords />);
    await userEvent.click(screen.getByText("State Liens"));
    await userEvent.type(screen.getByPlaceholderText("e.g. ACME LLC"), "ACME");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(mockSearchLiens).not.toHaveBeenCalled();
  });
});
