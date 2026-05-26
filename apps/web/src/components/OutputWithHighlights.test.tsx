import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AxisScore } from "../lib/types";
import { OutputWithHighlights } from "./OutputWithHighlights";

describe("OutputWithHighlights", () => {
  it("renders raw text when no contributions", () => {
    const axes: AxisScore[] = [
      { axis: "quality", score: 0.9, label: "on_rubric", flagged: false, reasons: [], contributions: [] },
    ];
    render(<OutputWithHighlights text="hello world" axes={axes} />);
    expect(screen.getByText("hello world")).toBeTruthy();
  });

  it("renders a <mark> for each flagged contribution span", () => {
    const text = "this is crap";
    const axes: AxisScore[] = [
      {
        axis: "moderation",
        score: 0.3,
        label: "profanity",
        flagged: true,
        reasons: [],
        contributions: [
          { feature: "moderation:profanity", weight: 0.4, snippet: "crap", offset: 8, length: 4 },
        ],
      },
    ];
    render(<OutputWithHighlights text={text} axes={axes} />);
    const marks = screen.getAllByTestId("highlight-moderation");
    expect(marks.length).toBe(1);
    expect(marks[0].textContent).toBe("crap");
  });
});
