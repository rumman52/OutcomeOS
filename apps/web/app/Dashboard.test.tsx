import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dashboard } from "./Dashboard";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => ({ value: "demo-user" }) })),
}));

describe("Dashboard", () => {
  it("renders service unavailable instead of fallback finances", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(await Dashboard({ section: "Overview" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Service unavailable");
  });

  it("forwards the authenticated session to the dashboard API", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    vi.stubGlobal("fetch", fetchMock);
    render(await Dashboard({ section: "Overview" }));
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/dashboard",
      expect.objectContaining({ headers: { cookie: "outcomeos_session=demo-user" } }),
    );
  });
});
