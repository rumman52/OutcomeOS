import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sandbox } from "./Sandbox";

describe("Sandbox", () => {
  it("creates an isolated sandbox order", () => {
    render(<Sandbox />);
    fireEvent.change(screen.getByLabelText("Order reference"), { target: { value: "demo-42" } });
    fireEvent.click(screen.getByRole("button", { name: "Create sandbox order" }));
    expect(screen.getByRole("status")).toHaveTextContent("demo-42 created · pending");
  });
});
