import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Dt } from "./Dt";

describe("Dt", () => {
  it("renders label and value", () => {
    render(<Dt label="Status" value="Active" />);
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("returns null when value is null", () => {
    const { container } = render(<Dt label="Status" value={null} />);
    expect(container.innerHTML).toBe("");
  });
});
