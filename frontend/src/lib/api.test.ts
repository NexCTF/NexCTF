import { afterEach, expect, it, vi } from "vitest";
import { ApiError, apiErrorMessage, createChallenge } from "@/lib/api";

function mockResponse(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: false, status, statusText: "", json: async () => body }),
  );
}

async function failure(): Promise<unknown> {
  return createChallenge("standard", {}).catch((err: unknown) => err);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

it("lists the field errors of a validation failure", async () => {
  mockResponse(422, {
    message: "Validation Error",
    description: "2 validation error(s) detected",
    error_code: "VAL-422",
    data: {
      errors: [
        { field: "title", message: "Field required", type: "missing" },
        { field: "compose", message: "Value error, no services", type: "value_error" },
      ],
    },
  });

  const err = await failure();

  expect(err).toBeInstanceOf(ApiError);
  expect(apiErrorMessage(err, "fallback")).toBe("title: Field required; compose: no services");
});

it("shows a root error without a field prefix", () => {
  const err = new ApiError(422, "Validation Error", null, "VAL-422", [
    { field: "root", message: "Input should be an object", type: "model_type" },
  ]);

  expect(apiErrorMessage(err, "fallback")).toBe("Input should be an object");
});

it("keeps the description for other errors", async () => {
  mockResponse(409, {
    message: "Conflict",
    description: "Challenge title already taken",
    error_code: "RES-409",
    data: null,
  });

  const err = await failure();

  expect(apiErrorMessage(err, "fallback")).toBe("Challenge title already taken");
  expect((err as ApiError).fieldErrors).toBeNull();
});
