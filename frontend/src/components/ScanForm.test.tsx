import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { ScanForm } from "./ScanForm";

vi.mock("../api/parcels", () => ({
  triggerScan: vi.fn(),
}));

import { triggerScan } from "../api/parcels";

beforeEach(() => {
  vi.mocked(triggerScan).mockReset();
});

describe("ScanForm", () => {
  it("renders form fields", () => {
    renderWithProviders(<ScanForm onClose={() => {}} onSuccess={() => {}} />);
    expect(screen.getByText("New Discovery Scan")).toBeInTheDocument();
    expect(screen.getByText("Select a state\u2026")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Select a state first")).toBeInTheDocument();
    expect(screen.getByText("Start Scan")).toBeInTheDocument();
  });

  it("submit is disabled when state/county empty", () => {
    renderWithProviders(<ScanForm onClose={() => {}} onSuccess={() => {}} />);
    const submitBtn = screen.getByText("Start Scan");
    expect(submitBtn).toBeDisabled();
  });

  it("calls onClose when Cancel clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderWithProviders(<ScanForm onClose={onClose} onSuccess={() => {}} />);
    await user.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when ✕ clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderWithProviders(<ScanForm onClose={onClose} onSuccess={() => {}} />);
    await user.click(screen.getByText("✕"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("has instrument filter dropdown", () => {
    renderWithProviders(<ScanForm onClose={() => {}} onSuccess={() => {}} />);
    expect(screen.getByText("All (lien cert + tax deed)")).toBeInTheDocument();
    expect(screen.getByText("Lien certificates only")).toBeInTheDocument();
    expect(screen.getByText("Tax deeds only")).toBeInTheDocument();
  });
});
