import assert from "node:assert/strict";
import test from "node:test";

test("production demo flags are documented as disabled", () => {
  assert.equal(process.env.DEMO_AUTH_ENABLED ?? "false", "false");
  assert.equal(process.env.MOCK_INTEGRATIONS_ENABLED ?? "false", "false");
});
