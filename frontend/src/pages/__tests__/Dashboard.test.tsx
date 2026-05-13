import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { Dashboard } from "../Dashboard";

vi.mock("../../api/parcels", () => ({
  listParcels: vi.fn(),
  getQueueStatus: vi.fn(),
  triggerScan: vi.fn(),
  getParcel: vi.fn(),
}));

vi.mock("../../api/settings", () => ({
  getLlmStatus: vi.fn(),
}));

import { listParcels, getQueueStatus } from "../../api/parcels";
import { getLlmStatus } from "../../api/settings";

const mockParcel = {
  parcel_id: "P001",
  state: "FL",
  county: "orange",
  address: "123 Main St",
  property_type: "residential",
  zoning: "R-1",
  acreage: 0.25,
  assessed_total: 150000,
  research_status: "scored",
  data_freshness: "current",
  latitude: 28.54,
  longitude: -81.38,
  instrument_type: "lien_certificate",
  lien_status: "active",
  total_owed: 5000,
  redemption_deadline: null,
  auction_date: null,
  overall_score: 85,
  risk_flags: [],
};

beforeEach(() => {
  vi.mocked(listParcels).mockResolvedValue([mockParcel]);
  vi.mocked(getQueueStatus).mockResolvedValue({
    pending: 0,
    processing: 0,
    failed: 0,
    complete: 5,
    agents: {},
  });
  vi.mocked(getLlmStatus).mockResolvedValue({
    has_user_key: true,
    has_server_llm: true,
    server_provider: "anthropic",
  });
});

describe("Dashboard", () => {
  it("renders header with app title", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Tax Research")).toBeInTheDocument();
  });

  it("renders navigation links", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Court Records")).toBeInTheDocument();
    expect(screen.getByText("UCC Filings")).toBeInTheDocument();
    expect(screen.getByText("Queue")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Loading\u2026")).toBeInTheDocument();
  });

  it("renders parcel cards after data loads", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("123 Main St")).toBeInTheDocument();
    });
  });

  it("shows empty state when no parcels found", async () => {
    vi.mocked(listParcels).mockResolvedValue([]);
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/No parcels found/)).toBeInTheDocument();
    });
  });

  it("shows Start a scan link in empty state", async () => {
    vi.mocked(listParcels).mockResolvedValue([]);
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Start a scan.")).toBeInTheDocument();
    });
  });

  it("shows result count in filter bar", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("1 results")).toBeInTheDocument();
    });
  });

  it("shows result count of 0 when no parcels", async () => {
    vi.mocked(listParcels).mockResolvedValue([]);
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("0 results")).toBeInTheDocument();
    });
  });

  it("opens scan modal when + New Scan clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Dashboard />);
    await user.click(screen.getByText("+ New Scan"));
    expect(screen.getByText("New Discovery Scan")).toBeInTheDocument();
  });

  it("shows detail pane placeholder when no parcel selected", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(
        screen.getByText("Select a parcel to view details"),
      ).toBeInTheDocument();
    });
  });

  it("has filter inputs for state and county", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByPlaceholderText("e.g. FL")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g. orange")).toBeInTheDocument();
  });

  it("has instrument type filter dropdown", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("All instruments")).toBeInTheDocument();
    expect(screen.getByText("Lien Certificate")).toBeInTheDocument();
    expect(screen.getByText("Tax Deed")).toBeInTheDocument();
  });

  it("has min score filter input", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByPlaceholderText("0\u2013100")).toBeInTheDocument();
  });

  it("has Clear button for filters", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Clear")).toBeInTheDocument();
  });

  it("shows Sign Out button", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
  });

  it("shows LLM setup banner when no LLM configured", async () => {
    vi.mocked(getLlmStatus).mockResolvedValue({
      has_user_key: false,
      has_server_llm: false,
      server_provider: null,
    });
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("LLM Configuration Required")).toBeInTheDocument();
    });
    expect(screen.getByText("Go to Settings")).toBeInTheDocument();
  });

  it("does not show LLM setup banner when LLM is configured", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("123 Main St")).toBeInTheDocument();
    });
    expect(screen.queryByText("LLM Configuration Required")).not.toBeInTheDocument();
  });

  it("renders multiple parcel cards", async () => {
    const secondParcel = {
      ...mockParcel,
      parcel_id: "P002",
      address: "456 Oak Ave",
      overall_score: 72,
    };
    vi.mocked(listParcels).mockResolvedValue([mockParcel, secondParcel]);
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("123 Main St")).toBeInTheDocument();
      expect(screen.getByText("456 Oak Ave")).toBeInTheDocument();
    });
    expect(screen.getByText("2 results")).toBeInTheDocument();
  });

  it("calls listParcels on initial render", () => {
    renderWithProviders(<Dashboard />);
    expect(listParcels).toHaveBeenCalled();
  });
});
