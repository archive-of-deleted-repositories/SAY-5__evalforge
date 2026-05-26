import { useQuery } from "@tanstack/react-query";
import { fetchRecent, wsUrl } from "../api/client";
import { AxisBadge } from "../components/AxisBadge";
import { OutputWithHighlights } from "../components/OutputWithHighlights";
import { useLiveFeed } from "../lib/ws";

export function LiveFeed() {
  const initial = useQuery({ queryKey: ["recent"], queryFn: () => fetchRecent(50) });
  const { events } = useLiveFeed({ url: wsUrl() });

  const items = events.length > 0 ? events : initial.data ?? [];
  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-900">Live Feed</h2>
        <span className="text-xs text-slate-500" data-testid="live-count">
          {items.length} recent checks
        </span>
      </header>
      <ul className="space-y-3" data-testid="live-list">
        {items.map((c) => (
          <li
            key={c.id}
            data-testid="check-row"
            className={`rounded-lg border bg-white p-4 shadow-sm ${
              c.flagged ? "border-rose-300" : "border-slate-200"
            }`}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-mono">{c.id.slice(0, 8)}</span>
              <span>prompt {c.prompt_version}</span>
              <span>{new Date(c.created_at).toLocaleTimeString()}</span>
            </div>
            {"axes" in c && Array.isArray(c.axes) ? (
              <div className="mb-2 flex flex-wrap gap-2">
                {c.axes.map((ax) => (
                  <AxisBadge key={ax.axis} axis={ax} />
                ))}
              </div>
            ) : null}
            <OutputWithHighlights text={c.output_text} axes={"axes" in c ? c.axes : []} />
          </li>
        ))}
      </ul>
    </main>
  );
}
