import type { AxisScore } from "../lib/types";

const colors: Record<string, string> = {
  quality: "bg-blue-100 text-blue-800 border-blue-300",
  safety: "bg-amber-100 text-amber-800 border-amber-300",
  moderation: "bg-rose-100 text-rose-800 border-rose-300",
};

interface Props {
  axis: AxisScore;
}

export function AxisBadge({ axis }: Props) {
  const color = colors[axis.axis] ?? "bg-slate-100 text-slate-800";
  return (
    <span
      data-testid={`axis-${axis.axis}`}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${color}`}
    >
      <span className="capitalize">{axis.axis}</span>
      <span className="font-mono">{axis.score.toFixed(2)}</span>
      {axis.flagged ? (
        <span className="rounded-full bg-rose-600 px-2 py-0.5 text-[10px] text-white">FLAG</span>
      ) : (
        <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] text-white">OK</span>
      )}
    </span>
  );
}
