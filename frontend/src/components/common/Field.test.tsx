import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Field } from "./Field";

describe("Field", () => {
  it("renders label and input", () => {
    render(<Field label="Name" value="" onChange={() => {}} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("shows placeholder text", () => {
    render(<Field label="State" value="" onChange={() => {}} placeholder="FL" />);
    expect(screen.getByPlaceholderText("FL")).toBeInTheDocument();
  });

  it("calls onChange when typing", async () => {
    const onChange = vi.fn();
    render(<Field label="Name" value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole("textbox"), "test");
    expect(onChange).toHaveBeenCalled();
  });

  it("respects maxLength", () => {
    render(<Field label="State" value="" onChange={() => {}} maxLength={2} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("maxLength", "2");
  });

  it("applies custom className", () => {
    render(<Field label="Name" value="" onChange={() => {}} className="w-16" />);
    expect(screen.getByRole("textbox").className).toContain("w-16");
  });
});
