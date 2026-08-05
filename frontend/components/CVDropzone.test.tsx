import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CVDropzone } from "./CVDropzone";

function makeFile(name: string, type: string): File {
  return new File(["content"], name, { type });
}

describe("CVDropzone", () => {
  it("calls onFileSelected with a valid file", () => {
    const onFileSelected = vi.fn();
    render(<CVDropzone file={null} onFileSelected={onFileSelected} />);

    const input = screen.getByLabelText("Sélectionner un CV");
    const file = makeFile("cv.pdf", "application/pdf");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledWith(file);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an error and calls onFileSelected(null) for an invalid file", () => {
    const onFileSelected = vi.fn();
    render(<CVDropzone file={null} onFileSelected={onFileSelected} />);

    const input = screen.getByLabelText("Sélectionner un CV");
    const file = makeFile("cv.txt", "text/plain");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledWith(null);
    expect(screen.getByRole("alert")).toHaveTextContent("PDF ou un DOCX");
  });

  it("shows the selected file's name", () => {
    const file = makeFile("mon-cv.pdf", "application/pdf");
    render(<CVDropzone file={file} onFileSelected={vi.fn()} />);
    expect(screen.getByText("mon-cv.pdf")).toBeInTheDocument();
  });
});
