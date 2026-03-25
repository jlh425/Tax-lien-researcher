import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/utils";
import { CourtRecords } from "./CourtRecords";

vi.mock("../api/courtRecords", () => ({
  searchFederalCases: vi.fn(),
  getCaseDetails: vi.fn(),
  searchStateLiens: vi.fn(),
}));

import { searchFederalCases, getCaseDetails, searchStateLiens } from "../api/courtRecords";

const mockSearchCases = vi.mocked(searchFederalCases);
const mockGetCaseDetails = vi.mocked(getCaseDetails);
const mockSearchLiens = vi.mocked(searchStateLiens);

describe("CourtRecords", () => {
  it("renders header and tabs", () => {
    renderWithProviders(<CourtRecords />);
    expect(screen.getByText("Court Records")).toBeInTheDocument();
    expect(screen.getByText("Federal Cases")).toBeInTheDocument();
    expect(screen.getByText("State Liens")).toBeInTheDocument();
  });

  it("shows empty state before search", () => {
    renderWithProviders(<CourtRecords />);
    expect(
      screen.getByText("Enter search criteria above to find court records."),
    ).toBeInTheDocument();
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

  it("shows case detail when case is clicked", async () => {
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

  it("switches to liens tab and searches", async () => {
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
  });

  it("shows inline error for search failure", async () => {
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
});
