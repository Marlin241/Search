import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Input, Textarea, Select } from "./Field";

describe("Input", () => {
  it("renders with its value and reports changes", () => {
    const onChange = vi.fn();
    render(<Input aria-label="Email" value="jane@example.com" onChange={onChange} />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveValue("jane@example.com");
    fireEvent.change(input, { target: { value: "new@example.com" } });
    expect(onChange).toHaveBeenCalled();
  });
});

describe("Textarea", () => {
  it("renders with its value and reports changes", () => {
    const onChange = vi.fn();
    render(<Textarea aria-label="Description" value="texte" onChange={onChange} />);
    const textarea = screen.getByLabelText("Description");
    expect(textarea).toHaveValue("texte");
    fireEvent.change(textarea, { target: { value: "nouveau texte" } });
    expect(onChange).toHaveBeenCalled();
  });
});

describe("Select", () => {
  it("renders its options and reports changes", () => {
    const onChange = vi.fn();
    render(
      <Select aria-label="Type" value="a" onChange={onChange}>
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>
    );
    const select = screen.getByLabelText("Type");
    expect(select).toHaveValue("a");
    fireEvent.change(select, { target: { value: "b" } });
    expect(onChange).toHaveBeenCalled();
  });
});
