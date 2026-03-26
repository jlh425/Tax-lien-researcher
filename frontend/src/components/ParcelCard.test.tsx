import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { ParcelCard } from "./ParcelCard";
import type { ParcelSummary } from "../types";

const baseParcel: ParcelSummary = {
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

describe("ParcelCard", () => {
  it("renders address and location", () => {
    renderWithProviders(
      <ParcelCard parcel={baseParcel} selected={false} onClick={() => {}} />
    );
    expect(screen.getByText("123 Main St")).toBeInTheDocument();
    expect(screen.getByText(/Orange Co., FL/)).toBeInTheDocument();
  });

  it("renders total owed", () => {
    renderWithProviders(
      <ParcelCard parcel={baseParcel} selected={false} onClick={() => {}} />
    );
    expect(screen.getByText(/\$5,000/)).toBeInTheDocument();
  });

  it("renders assessed value", () => {
    renderWithProviders(
      <ParcelCard parcel={baseParcel} selected={false} onClick={() => {}} />
    );
    expect(screen.getByText(/AV: \$150,000/)).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithProviders(
      <ParcelCard parcel={baseParcel} selected={false} onClick={onClick} />
    );
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("renders risk flags", () => {
    const parcel = { ...baseParcel, risk_flags: ["title_issue", "encumbrance"] };
    renderWithProviders(
      <ParcelCard parcel={parcel} selected={false} onClick={() => {}} />
    );
    expect(screen.getByText("title issue")).toBeInTheDocument();
    expect(screen.getByText("encumbrance")).toBeInTheDocument();
  });

  it("uses parcel_id when address is null", () => {
    const parcel = { ...baseParcel, address: null };
    renderWithProviders(
      <ParcelCard parcel={parcel} selected={false} onClick={() => {}} />
    );
    expect(screen.getByText("P001")).toBeInTheDocument();
  });
});
