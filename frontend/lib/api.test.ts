import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  ApiError,
  register,
  login,
  fetchMe,
  createDiagnostic,
  listDiagnostics,
  deleteAllDiagnostics,
  downloadCv,
  downloadLetter,
  generateCv,
  generateLetter,
  getCandidateProfile,
  updateCandidateProfile,
  uploadReferenceCv,
  searchJobs,
} from "./api";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function blobResponse(content: string, status = 200, contentType = "application/pdf") {
  return {
    ok: status >= 200 && status < 300,
    status,
    blob: async () => new Blob([content], { type: contentType }),
    json: async () => ({ detail: "Erreur" }),
  } as unknown as Response;
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

describe("generateCv", () => {
  it("posts to /diagnostics/:id/cv with the bearer token", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ kind: "cv", needs_review: false, created_at: "2026-08-06T00:00:00Z", updated_at: "2026-08-06T00:00:00Z" }, 201)
    );
    const document = await generateCv("tok123", 42);
    expect(document.kind).toBe("cv");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/cv");
    expect(init?.method).toBe("POST");
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });
});

describe("generateLetter", () => {
  it("posts to /diagnostics/:id/lettre", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ kind: "lettre", needs_review: false, created_at: "2026-08-06T00:00:00Z", updated_at: "2026-08-06T00:00:00Z" }, 201)
    );
    const document = await generateLetter("tok123", 42);
    expect(document.kind).toBe("lettre");

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/lettre");
  });
});

describe("downloadCv", () => {
  it("returns a Blob from /diagnostics/:id/cv", async () => {
    vi.mocked(fetch).mockResolvedValue(blobResponse("%PDF-1.4 fake"));
    const blob = await downloadCv("tok123", 42);
    expect(blob).toBeInstanceOf(Blob);

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/cv");
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });

  it("throws ApiError with the parsed detail on failure", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Aucun CV optimisé n'a encore été généré pour ce diagnostic." }),
    } as Response);

    await expect(downloadCv("tok123", 42)).rejects.toMatchObject({
      status: 404,
      message: "Aucun CV optimisé n'a encore été généré pour ce diagnostic.",
    });
  });
});

describe("downloadLetter", () => {
  it("returns a Blob from /diagnostics/:id/lettre", async () => {
    vi.mocked(fetch).mockResolvedValue(blobResponse("%PDF-1.4 fake"));
    const blob = await downloadLetter("tok123", 42);
    expect(blob).toBeInstanceOf(Blob);

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/lettre");
  });
});

describe("getCandidateProfile", () => {
  it("gets /profile with the auth header", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        full_name: "Jane Doe",
        phone: "0612345678",
        address: null,
        linkedin_url: null,
        portfolio_url: null,
        work_authorization: "FR/UE",
        salary_expectation: null,
        cv_filename: null,
        has_cv: false,
        updated_at: "2026-08-06T00:00:00Z",
      })
    );
    const profile = await getCandidateProfile("tok");
    expect(profile.full_name).toBe("Jane Doe");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/profile");
    expect((init?.headers as Headers).get("Authorization")).toBe("Bearer tok");
  });
});

describe("updateCandidateProfile", () => {
  it("puts JSON to /profile", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        full_name: "Jane Doe",
        phone: "0612345678",
        address: null,
        linkedin_url: null,
        portfolio_url: null,
        work_authorization: "FR/UE",
        salary_expectation: null,
        cv_filename: null,
        has_cv: false,
        updated_at: "2026-08-06T00:00:00Z",
      })
    );
    await updateCandidateProfile("tok", {
      full_name: "Jane Doe",
      phone: "0612345678",
      address: null,
      linkedin_url: null,
      portfolio_url: null,
      work_authorization: "FR/UE",
      salary_expectation: null,
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/profile");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string).full_name).toBe("Jane Doe");
  });
});

describe("uploadReferenceCv", () => {
  it("posts the file as multipart form data to /profile/cv", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        full_name: "",
        phone: "",
        address: null,
        linkedin_url: null,
        portfolio_url: null,
        work_authorization: "",
        salary_expectation: null,
        cv_filename: "cv.pdf",
        has_cv: true,
        updated_at: "2026-08-06T00:00:00Z",
      })
    );
    const file = new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" });

    const profile = await uploadReferenceCv("tok", file);

    expect(profile.has_cv).toBe(true);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/profile/cv");
    expect(init?.body).toBeInstanceOf(FormData);
  });
});

describe("searchJobs", () => {
  it("posts criteria to /job-search/search and returns listings", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        listings: [
          {
            title: "Développeur Python",
            company: "Acme",
            location: "Paris",
            snippet: "...",
            url: "https://example.com/1",
            source: "adzuna",
            ats_type: null,
          },
        ],
        unavailable_sources: ["france_travail"],
      })
    );

    const result = await searchJobs("tok", {
      keywords: "python",
      exclude_keywords: [],
      followed_companies: [],
    });

    expect(result.listings).toHaveLength(1);
    expect(result.unavailable_sources).toEqual(["france_travail"]);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/job-search/search");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string).keywords).toBe("python");
  });
});
