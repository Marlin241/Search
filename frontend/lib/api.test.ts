import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError, register, login, fetchMe, createDiagnostic, listDiagnostics, deleteAllDiagnostics } from "./api";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("register", () => {
  it("posts JSON to /auth/register", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: 1, email: "jane@example.com" }, 201));
    const user = await register("jane@example.com", "s3cret!");
    expect(user.email).toBe("jane@example.com");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/auth/register");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ email: "jane@example.com", password: "s3cret!" });
  });
});

describe("login", () => {
  it("posts form-encoded credentials to /auth/login", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: "tok", token_type: "bearer" }));
    const result = await login("jane@example.com", "s3cret!");
    expect(result.access_token).toBe("tok");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/auth/login");
    expect(init?.body).toBe("username=jane%40example.com&password=s3cret%21");
  });
});

describe("fetchMe", () => {
  it("sends the bearer token", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: 1, email: "jane@example.com" }));
    await fetchMe("tok123");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });
});

describe("createDiagnostic", () => {
  it("builds multipart form data with only the active offer field", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        id: 1,
        created_at: "2026-08-05T00:00:00Z",
        overall_score: 80,
        structural_score: 90,
        structural_issues: [],
        semantic_score: 70,
        missing_keywords: [],
        recommendations: [],
      })
    );
    const file = new File(["content"], "cv.pdf", { type: "application/pdf" });
    await createDiagnostic("tok123", file, { text: "Offer text" });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const body = init?.body as FormData;
    expect(body.get("cv_file")).toBe(file);
    expect(body.get("offer_text")).toBe("Offer text");
    expect(body.get("offer_url")).toBeNull();
  });
});

describe("listDiagnostics / deleteAllDiagnostics", () => {
  it("lists diagnostics", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([]));
    const result = await listDiagnostics("tok123");
    expect(result).toEqual([]);
  });

  it("deletes without parsing a body on 204", async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, status: 204, json: async () => { throw new Error("no body"); } } as Response);
    await expect(deleteAllDiagnostics("tok123")).resolves.toBeUndefined();
  });
});

describe("error handling", () => {
  it("throws an ApiError with the backend's detail message on a non-2xx response", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "Cet email est déjà utilisé." }, 409));
    await expect(register("dup@example.com", "pw")).rejects.toMatchObject({
      status: 409,
      message: "Cet email est déjà utilisé.",
    });
  });

  it("throws a status-0 ApiError when fetch itself fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network down"));
    await expect(login("jane@example.com", "pw")).rejects.toMatchObject({
      status: 0,
      message: "Impossible de contacter le serveur.",
    });
  });
});

it("ApiError is an instance of Error", () => {
  const error = new ApiError(422, "Invalid input");
  expect(error).toBeInstanceOf(Error);
  expect(error.status).toBe(422);
});
