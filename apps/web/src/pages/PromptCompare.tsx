import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/client";

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export function PromptCompare() {
  const { data, isLoading } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <h2 className="mb-4 text-xl font-semibold text-slate-900">Prompt Compare</h2>
      {isLoading && <p className="text-sm text-slate-500">loading...</p>}
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-slate-700">version</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-slate-700">total</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-slate-700">quality</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-slate-700">safety</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-slate-700">
                moderation
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100" data-testid="stats-rows">
            {(data ?? []).map((s) => (
              <tr key={s.prompt_version} data-testid="stats-row">
                <td className="px-4 py-2 font-mono text-sm">{s.prompt_version}</td>
                <td className="px-4 py-2 text-right text-sm">{s.total}</td>
                <td className="px-4 py-2 text-right text-sm">{pct(s.quality_pass_rate)}</td>
                <td className="px-4 py-2 text-right text-sm">{pct(s.safety_pass_rate)}</td>
                <td className="px-4 py-2 text-right text-sm">{pct(s.moderation_pass_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
