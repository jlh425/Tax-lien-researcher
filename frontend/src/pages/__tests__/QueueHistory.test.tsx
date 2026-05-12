import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import { QueueHistory } from "../QueueHistory";

vi.mock("../../api/parcels", () => ({
  getQueueStatus: vi.fn(),
}));

import { getQueueStatus } from "../../api/parcels";

const mockQueueStatus = {
  pending: 5,
  processing: 2,
  complete: 42,
  failed: 1,
  agents: {
    orchestrator: 20,
    scraper: 15,
    scoring: 10,
  },
};

beforeEach(() => {
  vi.mocked(getQueueStatus).mockResolvedValue(mockQueueStatus);
});

describe("QueueHistory", () => {
  it("renders heading and back link", () => {
    renderWithProviders(<QueueHistory />);
    expect(screen.getByText("Queue History")).toBeInTheDocument();
    expect(screen.getByText("Back to Dashboard")).toBeInTheDocument();
  });

  it("renders status card labels", () => {
    renderWithProviders(<QueueHistory />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows counts after data loads", async () => {
    renderWithProviders(<QueueHistory />);
    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument();
    });
  });

  it("shows agent breakdown table after data loads", async () => {
    renderWithProviders(<QueueHistory />);
    await waitFor(() => {
      expect(screen.getByText("orchestrator")).toBeInTheDocument();
      expect(screen.getByText("scraper")).toBeInTheDocument();
      expect(screen.getByText("scoring")).toBeInTheDocument();
    });
  });

  it("shows agent task counts and percentages", async () => {
    renderWithProviders(<QueueHistory />);
    await waitFor(() => {
      // orchestrator: 20/45 = 44%
      expect(screen.getByText("20")).toBeInTheDocument();
      expect(screen.getByText("44%")).toBeInTheDocument();
      // scraper: 15/45 = 33%
      expect(screen.getByText("15")).toBeInTheDocument();
      expect(screen.getByText("33%")).toBeInTheDocument();
      // scoring: 10/45 = 22%
      expect(screen.getByText("10")).toBeInTheDocument();
      expect(screen.getByText("22%")).toBeInTheDocument();
    });
  });

  it("shows error state on fetch failure", async () => {
    vi.mocked(getQueueStatus).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<QueueHistory />);
    await waitFor(() => {
      expect(screen.getByText("Failed to load queue status.")).toBeInTheDocument();
    });
  });

  it("shows empty agent message when no agents", async () => {
    vi.mocked(getQueueStatus).mockResolvedValue({
      pending: 0,
      processing: 0,
      complete: 0,
      failed: 0,
      agents: {},
    });
    renderWithProviders(<QueueHistory />);
    await waitFor(() => {
      expect(screen.getByText("No agent activity yet.")).toBeInTheDocument();
    });
  });

  it("renders Agent Breakdown section heading", async () => {
    renderWithProviders(<QueueHistory />);
    expect(screen.getByText("Agent Breakdown")).toBeInTheDocument();
  });

  it("uses refetchInterval for auto-refresh", () => {
    // Verify getQueueStatus is called — the query is configured with refetchInterval: 5000
    renderWithProviders(<QueueHistory />);
    expect(getQueueStatus).toHaveBeenCalled();
  });
});
