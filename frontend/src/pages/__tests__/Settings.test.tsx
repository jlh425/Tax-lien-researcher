import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { Settings } from "../Settings";

vi.mock("../../api/settings", () => ({
  getLlmStatus: vi.fn(),
  getConfiguredLlms: vi.fn(),
  testLlmConnection: vi.fn(),
  addConfiguredLlm: vi.fn(),
  setActiveLlm: vi.fn(),
  deleteConfiguredLlm: vi.fn(),
}));

import {
  getLlmStatus,
  getConfiguredLlms,
  testLlmConnection,
  addConfiguredLlm,
  setActiveLlm,
  deleteConfiguredLlm,
} from "../../api/settings";

const mockLlm = {
  id: "llm-001",
  provider: "anthropic",
  model: "claude-sonnet-4-20250514",
  base_url: null,
  masked_key: "sk-ant...xyz",
  is_active: true,
  added_at: "2026-05-01T10:00:00Z",
};

beforeEach(() => {
  vi.mocked(getLlmStatus).mockResolvedValue({
    has_user_key: true,
    has_server_llm: true,
    server_provider: "anthropic",
  });
  vi.mocked(getConfiguredLlms).mockResolvedValue({
    llms: [mockLlm],
  });
  vi.mocked(testLlmConnection).mockResolvedValue({
    success: true,
    message: "Connection successful",
    response_text: "Hello!",
  });
  vi.mocked(addConfiguredLlm).mockResolvedValue({
    message: "LLM added",
    llm: mockLlm,
  });
  vi.mocked(setActiveLlm).mockResolvedValue({ message: "Activated" });
  vi.mocked(deleteConfiguredLlm).mockResolvedValue({ message: "Deleted" });
});

describe("Settings", () => {
  it("renders heading and back link", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Back to Dashboard")).toBeInTheDocument();
  });

  it("renders provider dropdown with all providers", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Groq")).toBeInTheDocument();
    expect(screen.getByText("Ollama (local)")).toBeInTheDocument();
  });

  it("renders model input and API key input", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByPlaceholderText("claude-sonnet-4-20250514")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Leave blank to use stored key")).toBeInTheDocument();
  });

  it("renders Test & Add button", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Test & Add")).toBeInTheDocument();
  });

  it("disables Test & Add button when model is empty", () => {
    renderWithProviders(<Settings />);
    const btn = screen.getByText("Test & Add");
    expect(btn).toBeDisabled();
  });

  it("enables Test & Add button when model is filled", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Settings />);
    const modelInput = screen.getByPlaceholderText("claude-sonnet-4-20250514");
    await user.type(modelInput, "my-model");
    const btn = screen.getByText("Test & Add");
    expect(btn).toBeEnabled();
  });

  it("shows success message after successful test and add", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Settings />);

    const modelInput = screen.getByPlaceholderText("claude-sonnet-4-20250514");
    await user.type(modelInput, "claude-sonnet-4-20250514");

    const apiKeyInput = screen.getByPlaceholderText("Leave blank to use stored key");
    await user.type(apiKeyInput, "sk-test-key");

    await user.click(screen.getByText("Test & Add"));

    await waitFor(() => {
      expect(screen.getByText(/added successfully/)).toBeInTheDocument();
    });
  });

  it("shows error message after failed connection test", async () => {
    vi.mocked(testLlmConnection).mockResolvedValue({
      success: false,
      message: "Invalid API key",
      response_text: null,
    });

    const user = userEvent.setup();
    renderWithProviders(<Settings />);

    const modelInput = screen.getByPlaceholderText("claude-sonnet-4-20250514");
    await user.type(modelInput, "claude-sonnet-4-20250514");

    await user.click(screen.getByText("Test & Add"));

    await waitFor(() => {
      expect(screen.getByText("Invalid API key")).toBeInTheDocument();
    });
  });

  it("shows configured LLMs list", async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("claude-sonnet-4-20250514")).toBeInTheDocument();
      expect(screen.getByText("anthropic")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
    });
  });

  it("shows masked API key for configured LLM", async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("sk-ant...xyz")).toBeInTheDocument();
    });
  });

  it("shows empty state when no LLMs configured", async () => {
    vi.mocked(getConfiguredLlms).mockResolvedValue({ llms: [] });
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(
        screen.getByText("No LLMs configured yet. Add one above to get started."),
      ).toBeInTheDocument();
    });
  });

  it("shows setup required banner when no LLM configured", async () => {
    vi.mocked(getLlmStatus).mockResolvedValue({
      has_user_key: false,
      has_server_llm: false,
      server_provider: null,
    });
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("LLM Configuration Required")).toBeInTheDocument();
    });
  });

  it("shows Delete button for configured LLM", async () => {
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Delete")).toBeInTheDocument();
    });
  });

  it("shows Set Active button for inactive LLM", async () => {
    vi.mocked(getConfiguredLlms).mockResolvedValue({
      llms: [{ ...mockLlm, is_active: false }],
    });
    renderWithProviders(<Settings />);
    await waitFor(() => {
      expect(screen.getByText("Set Active")).toBeInTheDocument();
    });
  });

  it("hides API key field when Ollama is selected", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Settings />);

    const select = screen.getByDisplayValue("Anthropic");
    await user.selectOptions(select, "ollama");

    expect(screen.queryByPlaceholderText("Leave blank to use stored key")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("http://localhost:11434")).toBeInTheDocument();
  });

  it("calls deleteConfiguredLlm when Delete is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));

    await waitFor(() => {
      expect(deleteConfiguredLlm).toHaveBeenCalledWith("llm-001");
    });
  });

  it("calls setActiveLlm when Set Active is clicked", async () => {
    vi.mocked(getConfiguredLlms).mockResolvedValue({
      llms: [{ ...mockLlm, is_active: false }],
    });

    const user = userEvent.setup();
    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("Set Active")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Set Active"));

    await waitFor(() => {
      expect(setActiveLlm).toHaveBeenCalledWith("llm-001");
    });
  });
});
