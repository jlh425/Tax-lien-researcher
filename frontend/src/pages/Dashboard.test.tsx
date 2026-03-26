import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { Dashboard } from "./Dashboard";

// Mock API calls
vi.mock("../api/parcels", () => ({
  listParcels: vi.fn(),
  getQueueStatus: vi.fn(),
  triggerScan: vi.fn(),
  getParcel: vi.fn(),
}));

import { listParcels, getQueueStatus } from "../api/parcels";

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
});

describe("Dashboard", () => {
  it("renders header and navigation links", async () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Tax Research")).toBeInTheDocument();
    expect(screen.getByText("Court Records")).toBeInTheDocument();
    expect(screen.getByText("UCC Filings")).toBeInTheDocument();
  });

  it("shows loading then parcel cards", async () => {
    renderWithProviders(<Dashboard />);
    // Initially shows loading
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    // After data loads
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

  it("shows result count in filter bar", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("1 results")).toBeInTheDocument();
    });
  });

  it("opens scan form when + New Scan clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Dashboard />);
    await user.click(screen.getByText("+ New Scan"));
    expect(screen.getByText("New Discovery Scan")).toBeInTheDocument();
  });

  it("shows detail pane placeholder when no parcel selected", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(
        screen.getByText("Select a parcel to view details")
      ).toBeInTheDocument();
    });
  });

  it("has filter inputs for state and county", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByPlaceholderText("e.g. FL")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g. orange")).toBeInTheDocument();
  });
});
