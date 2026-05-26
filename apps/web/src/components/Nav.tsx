import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/", label: "Live Feed" },
  { to: "/queue", label: "Review Queue" },
  { to: "/compare", label: "Prompt Compare" },
];

export function Nav() {
  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-lg font-semibold text-slate-900">EvalForge</h1>
        <div className="flex gap-2">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.to === "/"}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-700 hover:bg-slate-100"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
