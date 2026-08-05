import { describe, it, expect } from "vitest";
import { validateCvFile, MAX_CV_SIZE_BYTES } from "./validation";

function makeFile(name: string, size: number, type = "application/octet-stream"): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("validateCvFile", () => {
  it("accepts a valid PDF", () => {
    expect(validateCvFile(makeFile("cv.pdf", 1024))).toBeNull();
  });

  it("accepts a valid DOCX", () => {
    expect(validateCvFile(makeFile("cv.docx", 1024))).toBeNull();
  });

  it("rejects an unsupported extension", () => {
    expect(validateCvFile(makeFile("cv.txt", 1024))).toContain("PDF ou un DOCX");
  });

  it("rejects a file over the size limit", () => {
    expect(validateCvFile(makeFile("cv.pdf", MAX_CV_SIZE_BYTES + 1))).toContain("5 Mo");
  });
});
