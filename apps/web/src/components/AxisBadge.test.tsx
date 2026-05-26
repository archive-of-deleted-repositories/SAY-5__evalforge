import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AxisScore } from "../lib/types";
import { AxisBadge } from "./AxisBadge";

const axis: AxisScore = {
  axis: "moderation",
  score: 0.42,
  label: "profanity",
  flagged: true,
  reasons: [],
  contributions: [],
};

describe("AxisBadge", () => {
  it("shows the axis label and score", () => {
    render(<AxisBadge axis={axis} />);
    expect(screen.getByTestId("axis-moderation")).toBeTruthy();
    expect(screen.getByText("0.42")).toBeTruthy();
  });

  it("renders FLAG when flagged", () => {
    render(<AxisBadge axis={axis} />);
    expect(screen.getByText("FLAG")).toBeTruthy();
  });

  it("renders OK when not flagged", () => {
    render(<AxisBadge axis={{ ...axis, flagged: false }} />);
    expect(screen.getByText("OK")).toBeTruthy();
  });
});
