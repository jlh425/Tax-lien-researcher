import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { AlohaLiens } from "../AlohaLiens";

vi.mock("../../api/parcels", () => ({
  listParcels: vi.fn(),
  getQueueStatus: vi.fn(),
  triggerScan: vi.fn(),
  getParcel: vi.fn(),
}));

import { listParcels, getQueueStatus } from "../../api/parcels";

const mockParcel = {
  parcel_id: "351N790020",
  state: "WY",
  county: "natrona",
  address: "123 Main St, Casper",
  property_type: "residential",
  zoning: "R-1",
  acreage: 0.5,
  assessed_total: 120000,
  research_status: "scored",
  data_freshness: "fresh",
  latitude: 42.85,
  longitude: -106.32,
  instrument_type: "lien_certificate",
  lien_status: "active",
  total_owed: 1494.8,
  redemption_deadline: null,
  auction_date: null,
  overall_score: 72,
  risk_flags: [],
};

beforeEach(() => {
  vi.mocked(listParcels).mockResolvedValue([mockParcel]);
  vi.mocked(getQueueStatus).mockResolvedValue({
    pending: 0,
    processing: 0,
    failed: 0,
    complete: 0,
    agents: {},
  });
});

describe("AlohaLiens", () => {
  it("renders filter buttons", async () => {
    renderWithProviders(<AlohaLiens />);
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Lien Cert")).toBeInTheDocument();
    expect(screen.getByText("Tax Deed")).toBeInTheDocument();
  });

  it("shows loading then parcel cards", async () => {
    renderWithProviders(<AlohaLiens />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("123 Main St, Casper")).toBeInTheDocument();
    });
  });

  it("shows empty state when no parcels", async () => {
    vi.mocked(listParcels).mockResolvedValue([]);
    renderWithProviders(<AlohaLiens />);
    await waitFor(() => {
      expect(screen.getByText(/No parcels found/)).toBeInTheDocument();
    });
  });

  it("shows opportunity count", async () => {
    renderWithProviders(<AlohaLiens />);
    await waitFor(() => {
      expect(screen.getByText(/1 opportunities/)).toBeInTheDocument();
    });
  });

  it("opens scan form on + New Scan click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlohaLiens />);
    await user.click(screen.getByText("+ New Scan"));
    expect(screen.getByText("New Discovery Scan")).toBeInTheDocument();
  });

  it("shows detail placeholder when no parcel selected", async () => {
    renderWithProviders(<AlohaLiens />);
    await waitFor(() => {
      expect(screen.getByText("Select a parcel to view details")).toBeInTheDocument();
    });
  });

  it("has sort dropdown", () => {
    renderWithProviders(<AlohaLiens />);
    expect(screen.getByText("Sort: Score")).toBeInTheDocument();
  });
});
