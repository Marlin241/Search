import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApplicationCard } from "./ApplicationCard";
import * as api from "@/lib/api";
import type { Application } from "@/lib/types";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    generateCv: vi.fn(),
    generateLetter: vi.fn(),
    downloadCv: vi.fn(),
    downloadLetter: vi.fn(),
    getPrefilledForm: vi.fn(),
    confirmApplication: vi.fn(),
    markApplicationSentManually: vi.fn(),
    ApiError: actual.ApiError,
  };
});

const diagnostic = {
  id: 1,
  created_at: "2026-08-06T00:00:00Z",
  overall_score: 70,
  structural_score: 80,
  structural_issues: [],
  semantic_score: 60,
  missing_keywords: ["Docker"],
  recommendations: ["Add Docker"],
};

function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    id: 1,
    diagnostic_id: 1,
    offer_url: "https://example.com/job/1",
    source: "manual",
    company_name: "Acme",
    job_title: "Développeur Python",
    ats_type: null,
    status: "en_cours",
    error_message: null,
    submitted_at: null,
    created_at: "2026-08-06T00:00:00Z",
    updated_at: "2026-08-06T00:00:00Z",
    diagnostic,
    ...overrides,
  };
}

const NEEDS_REVIEW_DETAIL =
  "Ce CV contient des éléments à vérifier avant l'envoi automatique — relisez-le ou régénérez-le depuis le diagnostic.";
const MISSING_FIELDS_DETAIL = "Les champs du formulaire pré-rempli sont requis pour la soumission automatique.";

beforeEach(() => {
  vi.mocked(api.generateCv).mockReset();
  vi.mocked(api.getPrefilledForm).mockReset();
  vi.mocked(api.confirmApplication).mockReset();
  vi.mocked(api.markApplicationSentManually).mockReset();
});

describe("ApplicationCard", () => {
  it("renders the offer title, company, and diagnostic report", () => {
    render(<ApplicationCard application={makeApplication()} token="tok" onUpdated={vi.fn()} />);
    expect(screen.getByText("Développeur Python")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Docker")).toBeInTheDocument();
  });

  it("confirms directly (no review step) for a non-ATS offer", async () => {
    const onUpdated = vi.fn();
    vi.mocked(api.confirmApplication).mockResolvedValue(
      makeApplication({ status: "a_soumettre_manuellement" })
    );
    render(<ApplicationCard application={makeApplication()} token="tok" onUpdated={onUpdated} />);

    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));

    await waitFor(() => expect(api.confirmApplication).toHaveBeenCalledWith("tok", 1, undefined, false));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "a_soumettre_manuellement" }));
  });

  it("fetches and shows the prefilled form review for an ATS-eligible offer", async () => {
    vi.mocked(api.getPrefilledForm).mockResolvedValue({
      fields: [
        { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
      ],
    });
    render(
      <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={vi.fn()} />
    );

    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));

    expect(await screen.findByLabelText(/first name/i)).toHaveValue("Jane");
    expect(api.getPrefilledForm).toHaveBeenCalledWith("tok", 1);
  });

  it("submits the edited fields from the review step", async () => {
    vi.mocked(api.getPrefilledForm).mockResolvedValue({
      fields: [
        { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
      ],
    });
    vi.mocked(api.confirmApplication).mockResolvedValue(makeApplication({ ats_type: "greenhouse", status: "soumise_auto" }));
    const onUpdated = vi.fn();
    render(
      <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={onUpdated} />
    );
    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));
    await screen.findByLabelText(/first name/i);

    fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));

    await waitFor(() =>
      expect(api.confirmApplication).toHaveBeenCalledWith(
        "tok",
        1,
        expect.arrayContaining([expect.objectContaining({ name: "first_name", value: "Jane" })]),
        false
      )
    );
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "soumise_auto" }));
  });

  it("shows the offer link and a mark-sent button in assisted mode", async () => {
    const onUpdated = vi.fn();
    vi.mocked(api.markApplicationSentManually).mockResolvedValue(
      makeApplication({ status: "soumise_manuelle_confirmee" })
    );
    render(
      <ApplicationCard application={makeApplication({ status: "a_soumettre_manuellement" })} token="tok" onUpdated={onUpdated} />
    );

    expect(screen.getByRole("link", { name: /ouvrir la page de candidature/i })).toHaveAttribute(
      "href",
      "https://example.com/job/1"
    );

    fireEvent.click(screen.getByRole("button", { name: /marquer comme envoyée/i }));

    await waitFor(() => expect(api.markApplicationSentManually).toHaveBeenCalledWith("tok", 1));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "soumise_manuelle_confirmee" }));
  });

  it("shows the error message for a failed submission", () => {
    render(
      <ApplicationCard
        application={makeApplication({ status: "echec_soumission", error_message: "Le serveur a refusé la soumission." })}
        token="tok"
        onUpdated={vi.fn()}
      />
    );
    expect(screen.getByText("Le serveur a refusé la soumission.")).toBeInTheDocument();
  });

  it("allows retrying from a failed submission (echec_soumission) via a re-enabled confirm button", async () => {
    const onUpdated = vi.fn();
    vi.mocked(api.confirmApplication).mockResolvedValue(
      makeApplication({ status: "soumise_auto" })
    );
    render(
      <ApplicationCard
        application={makeApplication({ status: "echec_soumission", error_message: "Le serveur a refusé la soumission." })}
        token="tok"
        onUpdated={onUpdated}
      />
    );

    const retryButton = screen.getByRole("button", { name: /réessayer l'envoi/i });
    expect(retryButton).toBeEnabled();
    // The manual-submission block (offer link + mark-sent button) must not
    // also render for echec_soumission - it's gated on a_soumettre_manuellement.
    expect(screen.queryByRole("link", { name: /ouvrir la page de candidature/i })).not.toBeInTheDocument();

    fireEvent.click(retryButton);

    await waitFor(() => expect(api.confirmApplication).toHaveBeenCalledWith("tok", 1, undefined, false));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "soumise_auto" }));
  });

  it("shows 'Préparation du formulaire...' while retrying an ATS-eligible failed submission", async () => {
    vi.mocked(api.getPrefilledForm).mockResolvedValue({
      fields: [
        { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
      ],
    });
    render(
      <ApplicationCard
        application={makeApplication({ status: "echec_soumission", ats_type: "greenhouse", error_message: "Panne." })}
        token="tok"
        onUpdated={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /réessayer l'envoi/i }));

    expect(await screen.findByLabelText(/first name/i)).toHaveValue("Jane");
    expect(api.getPrefilledForm).toHaveBeenCalledWith("tok", 1);
  });

  // --- Deviation 1: 429 rate limit on getPrefilledForm (regression lock) ---
  it("shows a warning banner when the prefilled-form fetch is rate-limited (429)", async () => {
    vi.mocked(api.getPrefilledForm).mockRejectedValue(
      new api.ApiError(429, "Limite de 10 prévisualisations de formulaire par heure atteinte. Réessaie plus tard.")
    );
    render(
      <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={vi.fn()} />
    );

    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));

    expect(
      await screen.findByText(/Limite de 10 prévisualisations de formulaire par heure atteinte\. Réessaie plus tard\./i)
    ).toBeInTheDocument();
  });

  // --- Deviation 2: 422 needs_review block on confirmApplication ---
  describe("needs_review block on confirm", () => {
    it("shows the warning block with checkbox and message (not the generic banner) on a needs_review 422 from the review-confirm path", async () => {
      vi.mocked(api.getPrefilledForm).mockResolvedValue({
        fields: [
          { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
        ],
      });
      vi.mocked(api.confirmApplication).mockRejectedValueOnce(new api.ApiError(422, NEEDS_REVIEW_DETAIL));
      render(
        <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={vi.fn()} />
      );
      fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));
      await screen.findByLabelText(/first name/i);

      fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));

      expect(await screen.findByText(NEEDS_REVIEW_DETAIL)).toBeInTheDocument();
      expect(screen.getByRole("checkbox")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("disables 'Envoyer quand même' until the checkbox is checked", async () => {
      vi.mocked(api.confirmApplication).mockRejectedValueOnce(new api.ApiError(422, NEEDS_REVIEW_DETAIL));
      render(<ApplicationCard application={makeApplication()} token="tok" onUpdated={vi.fn()} />);

      fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));
      await screen.findByText(NEEDS_REVIEW_DETAIL);

      const sendAnywayButton = screen.getByRole("button", { name: /envoyer quand même/i });
      expect(sendAnywayButton).toBeDisabled();

      fireEvent.click(screen.getByRole("checkbox"));
      expect(sendAnywayButton).toBeEnabled();
    });

    it("resends with overrideNeedsReview=true and the same fields on 'Envoyer quand même', then calls onUpdated", async () => {
      vi.mocked(api.getPrefilledForm).mockResolvedValue({
        fields: [
          { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
        ],
      });
      vi.mocked(api.confirmApplication)
        .mockRejectedValueOnce(new api.ApiError(422, NEEDS_REVIEW_DETAIL))
        .mockResolvedValueOnce(makeApplication({ ats_type: "greenhouse", status: "soumise_auto" }));
      const onUpdated = vi.fn();
      render(
        <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={onUpdated} />
      );
      fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));
      await screen.findByLabelText(/first name/i);
      fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));
      await screen.findByText(NEEDS_REVIEW_DETAIL);

      fireEvent.click(screen.getByRole("checkbox"));
      fireEvent.click(screen.getByRole("button", { name: /envoyer quand même/i }));

      await waitFor(() => expect(api.confirmApplication).toHaveBeenCalledTimes(2));
      expect(api.confirmApplication).toHaveBeenNthCalledWith(
        2,
        "tok",
        1,
        expect.arrayContaining([expect.objectContaining({ name: "first_name", value: "Jane" })]),
        true
      );
      expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "soumise_auto" }));
    });

    it("falls through to the generic ErrorBanner for a 422 with a different detail (missing fields), not the needs_review UI", async () => {
      vi.mocked(api.confirmApplication).mockRejectedValueOnce(new api.ApiError(422, MISSING_FIELDS_DETAIL));
      render(<ApplicationCard application={makeApplication()} token="tok" onUpdated={vi.fn()} />);

      fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));

      expect(await screen.findByText(MISSING_FIELDS_DETAIL)).toBeInTheDocument();
      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
      expect(screen.queryByText(/envoyer quand même/i)).not.toBeInTheDocument();
    });
  });
});
