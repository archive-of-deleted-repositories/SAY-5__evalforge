import type { AxisScore } from "../lib/types";

interface Props {
  text: string;
  axes: AxisScore[];
}

interface Span {
  start: number;
  end: number;
  axis: string;
  feature: string;
}

function buildSpans(axes: AxisScore[]): Span[] {
  const spans: Span[] = [];
  for (const a of axes) {
    for (const c of a.contributions) {
      if (!a.flagged) continue;
      spans.push({
        start: c.offset,
        end: c.offset + c.length,
        axis: a.axis,
        feature: c.feature,
      });
    }
  }
  spans.sort((x, y) => x.start - y.start);
  // remove overlaps, keep first
  const out: Span[] = [];
  let last = -1;
  for (const s of spans) {
    if (s.start >= last) {
      out.push(s);
      last = s.end;
    }
  }
  return out;
}

const axisColor: Record<string, string> = {
  quality: "bg-blue-200",
  safety: "bg-amber-200",
  moderation: "bg-rose-200",
};

export function OutputWithHighlights({ text, axes }: Props) {
  const spans = buildSpans(axes);
  if (spans.length === 0) {
    return <p className="whitespace-pre-wrap break-words text-sm text-slate-700">{text}</p>;
  }
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  spans.forEach((s, i) => {
    if (s.start > cursor) {
      parts.push(<span key={`t${i}`}>{text.slice(cursor, s.start)}</span>);
    }
    parts.push(
      <mark
        key={`m${i}`}
        title={s.feature}
        data-testid={`highlight-${s.axis}`}
        className={`rounded px-0.5 ${axisColor[s.axis] ?? "bg-slate-200"}`}
      >
        {text.slice(s.start, s.end)}
      </mark>,
    );
    cursor = s.end;
  });
  if (cursor < text.length) {
    parts.push(<span key="tail">{text.slice(cursor)}</span>);
  }
  return <p className="whitespace-pre-wrap break-words text-sm text-slate-700">{parts}</p>;
}
