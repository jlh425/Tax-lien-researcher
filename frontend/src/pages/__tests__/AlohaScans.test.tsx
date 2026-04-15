import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { AlohaScans } from "../AlohaScans";

vi.mock("../../api/scans", () => ({
  listScans: vi.fn(),
}));

vi.mock("../../api/parcels", () => ({
  triggerScan: vi.fn(),
  getQueueStatus: vi.fn(),
}));

import { listScans } from "../../api/scans";
import { getQueueStatus } from "../../api/parcels";

const mockScan = {
  id: "scan-001",
  state: "WY",
  county: "natrona",
  status: "done" as const,
  records_found: 47,
  records_total: 312,
  started_at: "2026-04-10T10:00:00Z",
  completed_at: "2026-04-10T10:05:00Z",
};

beforeEach(() => {
  vi.mocked(listScans).mockResolvedValue([mockScan]);
  vi.mocked(getQueueStatus).mockResolvedValue({
    pending: 0,
    processing: 0,
    failed: 0,
    complete: 0,
    agents: {},
  });
});

describe("AlohaScans", () => {
  it("renders scan history heading", async () => {
    renderWithProviders(<AlohaScans />);
    expect(screen.getByText("Scan History")).toBeInTheDocument();
  });

  it("shows scan table after loading", async () => {
    renderWithProviders(<AlohaScans />);
    await waitFor(() => {
      expect(screen.getByText("natrona")).toBeInTheDocument();
      expect(screen.getByText("WY")).toBeInTheDocument();
      expect(screen.getByText("done")).toBeInTheDocument();
    });
  });

  it("shows progress column", async () => {
    renderWithProviders(<AlohaScans />);
    await waitFor(() => {
      expect(screen.getByText("47 / 312 parcels")).toBeInTheDocument();
    });
  });

  it("shows empty state when no scans", async () => {
    vi.mocked(listScans).mockResolvedValue([]);
    renderWithProviders(<AlohaScans />);
    await waitFor(() => {
      expect(screen.getByText(/No scans yet/)).toBeInTheDocument();
    });
  });

  it("opens scan form on + New Scan click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlohaScans />);
    await user.click(screen.getByText("+ New Scan"));
    expect(screen.getByText("New Discovery Scan")).toBeInTheDocument();
  });
});
