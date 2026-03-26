import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test/utils";
import { QueueStatusBar } from "./QueueStatusBar";

vi.mock("../api/parcels", () => ({
  getQueueStatus: vi.fn(),
}));

import { getQueueStatus } from "../api/parcels";

describe("QueueStatusBar", () => {
  it("renders nothing when no active queue items", async () => {
    vi.mocked(getQueueStatus).mockResolvedValue({
      pending: 0,
      processing: 0,
      failed: 0,
      complete: 10,
      agents: {},
    });
    const { container } = renderWithProviders(<QueueStatusBar />);
    // Wait for query to resolve, then check nothing is rendered
    await waitFor(() => {
      expect(container.textContent).toBe("");
    });
  });

  it("shows processing count", async () => {
    vi.mocked(getQueueStatus).mockResolvedValue({
      pending: 0,
      processing: 3,
      failed: 0,
      complete: 10,
      agents: {},
    });
    renderWithProviders(<QueueStatusBar />);
    await waitFor(() => {
      expect(screen.getByText(/3 processing/)).toBeInTheDocument();
    });
  });

  it("shows queued count", async () => {
    vi.mocked(getQueueStatus).mockResolvedValue({
      pending: 5,
      processing: 0,
      failed: 0,
      complete: 10,
      agents: {},
    });
    renderWithProviders(<QueueStatusBar />);
    await waitFor(() => {
      expect(screen.getByText(/5 queued/)).toBeInTheDocument();
    });
  });

  it("shows failed count in red", async () => {
    vi.mocked(getQueueStatus).mockResolvedValue({
      pending: 0,
      processing: 0,
      failed: 2,
      complete: 10,
      agents: {},
    });
    renderWithProviders(<QueueStatusBar />);
    await waitFor(() => {
      expect(screen.getByText(/2 failed/)).toBeInTheDocument();
    });
  });
});
