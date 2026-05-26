import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchQueue, reviewCheck } from "../api/client";
import { AxisBadge } from "../components/AxisBadge";
import { OutputWithHighlights } from "../components/OutputWithHighlights";
import type { ReviewLabel } from "../lib/types";

export function ReviewQueue() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["queue"], queryFn: fetchQueue });

  const review = useMutation({
    mutationFn: async ({ id, label }: { id: string; label: ReviewLabel }) =>
      reviewCheck(id, label),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["queue"] });
      qc.invalidateQueries({ queryKey: ["recent"] });
    },
  });

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-900">Review Queue</h2>
        <span className="text-xs text-slate-500" data-testid="queue-count">
          {data?.length ?? 0} pending
        </span>
      </header>
      {isLoading && <p className="text-sm text-slate-500">loading...</p>}
      <ul className="space-y-3" data-testid="queue-list">
        {(data ?? []).map((c) => (
          <li
            key={c.id}
            data-testid="queue-item"
            data-id={c.id}
            className="rounded-lg border border-rose-300 bg-white p-4 shadow-sm"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-mono">{c.id.slice(0, 8)}</span>
              <span>prompt {c.prompt_version}</span>
            </div>
            <div className="mb-2 flex flex-wrap gap-2">
              {c.axes.map((ax) => (
                <AxisBadge key={ax.axis} axis={ax} />
              ))}
            </div>
            <OutputWithHighlights text={c.output_text} axes={c.axes} />
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                data-testid="btn-correct"
                onClick={() => review.mutate({ id: c.id, label: "correct" })}
                className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
              >
                Correct
              </button>
              <button
                data-testid="btn-false-positive"
                onClick={() => review.mutate({ id: c.id, label: "false_positive" })}
                className="rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600"
              >
                False positive
              </button>
              <button
                data-testid="btn-false-negative"
                onClick={() => review.mutate({ id: c.id, label: "false_negative" })}
                className="rounded-md bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
              >
                False negative
              </button>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
