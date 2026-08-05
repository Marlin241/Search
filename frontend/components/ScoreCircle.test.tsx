import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ScoreCircle } from "./ScoreCircle";

describe("ScoreCircle", () => {
  it("renders the score", () => {
    render(<ScoreCircle score={62} />);
    expect(screen.getByText("62")).toBeInTheDocument();
  });

  it("clamps scores above 100 down to 100", () => {
    render(<ScoreCircle score={140} />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("clamps negative scores up to 0", () => {
    render(<ScoreCircle score={-10} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("renders an optional label", () => {
    render(<ScoreCircle score={80} label="Structure" />);
    expect(screen.getByText("Structure")).toBeInTheDocument();
  });
});
