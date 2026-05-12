import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { AlohaSettings } from "../AlohaSettings";

vi.mock("../../api/settings", () => ({
  getPreferences: vi.fn(),
  updatePreferences: vi.fn(),
}));

import { getPreferences, updatePreferences } from "../../api/settings";

const mockPreferences = {
  scoring_weights: {
    lien_to_value: 30,
    redemption_urgency: 25,
    owner_motivation: 25,
    contact_reachability: 20,
  },
  api_keys: { google_maps: "AIza-test-key" },
  include_screenshots: true,
};

beforeEach(() => {
  vi.mocked(getPreferences).mockResolvedValue(mockPreferences);
  vi.mocked(updatePreferences).mockResolvedValue(mockPreferences);
});

describe("AlohaSettings", () => {
  it("shows loading state while fetching preferences", () => {
    // Make query stay in loading state
    vi.mocked(getPreferences).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<AlohaSettings />);
    expect(screen.getByText("Loading preferences...")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    vi.mocked(getPreferences).mockRejectedValue(new Error("Server error"));
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load preferences/)).toBeInTheDocument();
      expect(screen.getByText(/Server error/)).toBeInTheDocument();
    });
  });

  it("renders heading after data loads", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("Aloha Settings")).toBeInTheDocument();
    });
  });

  it("renders scoring weight labels", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("Lien-to-Value Ratio")).toBeInTheDocument();
      expect(screen.getByText("Redemption Urgency")).toBeInTheDocument();
      expect(screen.getByText("Owner Motivation")).toBeInTheDocument();
      expect(screen.getByText("Contact Reachability")).toBeInTheDocument();
    });
  });

  it("renders scoring weight inputs with loaded values", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      const inputs = screen.getAllByRole("spinbutton");
      // 4 weight inputs
      expect(inputs).toHaveLength(4);
      expect(inputs[0]).toHaveValue(30);
      expect(inputs[1]).toHaveValue(25);
      expect(inputs[2]).toHaveValue(25);
      expect(inputs[3]).toHaveValue(20);
    });
  });

  it("shows total weight percentage", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("Total: 100%")).toBeInTheDocument();
    });
  });

  it("updates weight when input changes", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlohaSettings />);

    await waitFor(() => {
      expect(screen.getByText("Lien-to-Value Ratio")).toBeInTheDocument();
    });

    const inputs = screen.getAllByRole("spinbutton");
    // Clear and type a new value for the first weight (lien_to_value)
    await user.clear(inputs[0]);
    await user.type(inputs[0], "40");

    expect(inputs[0]).toHaveValue(40);
    // Total should now be 40+25+25+20 = 110
    expect(screen.getByText(/Total: 110%/)).toBeInTheDocument();
    expect(screen.getByText(/should be 100%/)).toBeInTheDocument();
  });

  it("renders Google Maps API Key section", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("Google Maps API Key")).toBeInTheDocument();
    });
  });

  it("renders screenshots checkbox", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("Include screenshots in reports")).toBeInTheDocument();
      expect(screen.getByRole("checkbox")).toBeChecked();
    });
  });

  it("renders Save Settings button", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });
  });

  it("calls updatePreferences on save", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlohaSettings />);

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Save Settings"));

    await waitFor(() => {
      expect(updatePreferences).toHaveBeenCalledWith({
        scoring_weights: {
          lien_to_value: 30,
          redemption_urgency: 25,
          owner_motivation: 25,
          contact_reachability: 20,
        },
        api_keys: { google_maps: "AIza-test-key" },
        include_screenshots: true,
      });
    });
  });

  it("shows success feedback after save", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlohaSettings />);

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Save Settings"));

    await waitFor(() => {
      expect(screen.getByText("Settings saved")).toBeInTheDocument();
    });
  });

  it("shows error feedback when save fails", async () => {
    vi.mocked(updatePreferences).mockRejectedValue(new Error("Save failed"));

    const user = userEvent.setup();
    renderWithProviders(<AlohaSettings />);

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Save Settings"));

    await waitFor(() => {
      expect(screen.getByText(/Failed to save/)).toBeInTheDocument();
      expect(screen.getByText(/Save failed/)).toBeInTheDocument();
    });
  });

  it("toggles screenshots checkbox", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlohaSettings />);

    await waitFor(() => {
      expect(screen.getByRole("checkbox")).toBeChecked();
    });

    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("renders PDF Export section heading", async () => {
    renderWithProviders(<AlohaSettings />);
    await waitFor(() => {
      expect(screen.getByText("PDF Export Defaults")).toBeInTheDocument();
    });
  });
});
