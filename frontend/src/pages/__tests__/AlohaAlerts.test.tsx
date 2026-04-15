import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import { AlohaAlerts } from "../AlohaAlerts";

vi.mock("../../api/parcels", () => ({
  listParcels: vi.fn(),
  getQueueStatus: vi.fn(),
}));

import { listParcels, getQueueStatus } from "../../api/parcels";

const today = new Date();
const in15Days = new Date(today.getTime() + 15 * 86_400_000).toISOString().split("T")[0];
const in60Days = new Date(today.getTime() + 60 * 86_400_000).toISOString().split("T")[0];
const in180Days = new Date(today.getTime() + 180 * 86_400_000).toISOString().split("T")[0];

const urgentParcel = {
  parcel_id: "P001",
  state: "WY",
  county: "natrona",
  address: "123 Urgent St",
  property_type: "residential",
  zoning: null,
  acreage: null,
  assessed_total: null,
  research_status: "scored",
  data_freshness: "fresh",
  latitude: null,
  longitude: null,
  instrument_type: "lien_certificate",
  lien_status: "active",
  total_owed: 5000,
  redemption_deadline: in15Days,
  auction_date: null,
  overall_score: 80,
  risk_flags: [],
};

const warningParcel = {
  ...urgentParcel,
  parcel_id: "P002",
  address: "456 Warning Ave",
  redemption_deadline: in60Days,
};

const noDeadlineParcel = {
  ...urgentParcel,
  parcel_id: "P003",
  address: "789 No Deadline Rd",
  redemption_deadline: in180Days,
};

beforeEach(() => {
  vi.mocked(listParcels).mockResolvedValue([urgentParcel, warningParcel, noDeadlineParcel]);
  vi.mocked(getQueueStatus).mockResolvedValue({
    pending: 0,
    processing: 0,
    failed: 0,
    complete: 0,
    agents: {},
  });
});

describe("AlohaAlerts", () => {
  it("renders heading", async () => {
    renderWithProviders(<AlohaAlerts />);
    expect(screen.getByText("Deadline Alerts")).toBeInTheDocument();
  });

  it("shows urgent and warning alerts", async () => {
    renderWithProviders(<AlohaAlerts />);
    await waitFor(() => {
      expect(screen.getByText("123 Urgent St")).toBeInTheDocument();
      expect(screen.getByText("456 Warning Ave")).toBeInTheDocument();
    });
  });

  it("does not show parcels beyond 90 days", async () => {
    renderWithProviders(<AlohaAlerts />);
    await waitFor(() => {
      expect(screen.getByText("123 Urgent St")).toBeInTheDocument();
    });
    expect(screen.queryByText("789 No Deadline Rd")).not.toBeInTheDocument();
  });

  it("shows alert level badges", async () => {
    renderWithProviders(<AlohaAlerts />);
    await waitFor(() => {
      expect(screen.getByText("urgent")).toBeInTheDocument();
      expect(screen.getByText("warning")).toBeInTheDocument();
    });
  });

  it("shows empty state when no alerts", async () => {
    vi.mocked(listParcels).mockResolvedValue([]);
    renderWithProviders(<AlohaAlerts />);
    await waitFor(() => {
      expect(screen.getByText(/No upcoming deadlines/)).toBeInTheDocument();
    });
  });

  it("shows alert counts in header", async () => {
    renderWithProviders(<AlohaAlerts />);
    await waitFor(() => {
      expect(screen.getByText("1 urgent")).toBeInTheDocument();
      expect(screen.getByText("1 warnings")).toBeInTheDocument();
    });
  });
});
