import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { Login } from "./Login";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
}));

vi.mock("../stores/authStore", () => ({
  useAuthStore: vi.fn((selector) =>
    selector({ token: null, userId: null, tier: null, setAuth: mockSetAuth, logout: vi.fn() }),
  ),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

import { login, register } from "../api/auth";
const mockSetAuth = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Login", () => {
  it("renders login form by default", () => {
    renderWithProviders(<Login />);
    expect(screen.getByText("Sign in to your account")).toBeTruthy();
    expect(screen.getByPlaceholderText("you@example.com")).toBeTruthy();
    expect(screen.getByPlaceholderText("Min 8 characters")).toBeTruthy();
    expect(screen.getByText("Sign In")).toBeTruthy();
  });

  it("switches to register mode", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Login />);
    await user.click(screen.getByText("Register"));
    expect(screen.getByText("Create a new account")).toBeTruthy();
    expect(screen.getByPlaceholderText("Your name (optional)")).toBeTruthy();
    expect(screen.getByText("Create Account")).toBeTruthy();
  });

  it("calls login API on submit", async () => {
    const user = userEvent.setup();
    (login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "tok123",
      user_id: "u1",
      tier: "free",
    });
    renderWithProviders(<Login />);

    await user.type(screen.getByPlaceholderText("you@example.com"), "a@b.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith("a@b.com", "password123");
      expect(mockSetAuth).toHaveBeenCalledWith("tok123", "u1", "free");
      expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
    });
  });

  it("calls register API when in register mode", async () => {
    const user = userEvent.setup();
    (register as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "tok456",
      user_id: "u2",
      tier: "free",
    });
    renderWithProviders(<Login />);

    await user.click(screen.getByText("Register"));
    await user.type(screen.getByPlaceholderText("Your name (optional)"), "Test User");
    await user.type(screen.getByPlaceholderText("you@example.com"), "new@user.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.click(screen.getByText("Create Account"));

    await waitFor(() => {
      expect(register).toHaveBeenCalledWith("new@user.com", "password123", "Test User");
      expect(mockSetAuth).toHaveBeenCalledWith("tok456", "u2", "free");
    });
  });

  it("shows error on login failure", async () => {
    const user = userEvent.setup();
    (login as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { data: { detail: "Invalid credentials" } },
    });
    renderWithProviders(<Login />);

    await user.type(screen.getByPlaceholderText("you@example.com"), "bad@user.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "wrongpass1");
    await user.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeTruthy();
    });
  });

  it("switches back to login from register", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Login />);
    await user.click(screen.getByText("Register"));
    expect(screen.getByText("Create a new account")).toBeTruthy();
    await user.click(screen.getByText("Sign in"));
    expect(screen.getByText("Sign in to your account")).toBeTruthy();
  });
});
