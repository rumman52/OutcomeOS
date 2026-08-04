import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dashboard } from "./Dashboard";

describe("Dashboard", () => {
  it("renders service unavailable instead of fallback finances", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(await Dashboard({ section: "Overview" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Service unavailable");
  });
});
