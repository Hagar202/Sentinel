// The layout: a floating glass bar on top (no sidebar), the page below, and a Ctrl+K command palette.
import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { BarChart3, CheckCircle2, Command, FileText, Gauge, LayoutDashboard, Mail, MessagesSquare, Moon, Search, Server, Settings, Sun, Wallet } from "lucide-react";
import { api } from "./api";
import Overview from "./pages/Overview";
import Approvals from "./pages/Approvals";
import Phishing from "./pages/Phishing";
import Incident from "./pages/Incident";
import Costs from "./pages/Costs";
import Voc from "./pages/Voc";
import Evaluation from "./pages/Evaluation";
import Reports from "./pages/Reports";
import System from "./pages/System";

const PAGES = [
  { to: "/", label: "Overview", icon: LayoutDashboard, hint: "KPIs, run all agents" },
  { to: "/approvals", label: "Approvals", icon: CheckCircle2, hint: "Human in the loop" },
  { to: "/phishing", label: "Phishing", icon: Mail, hint: "Phishing Triage agent" },
  { to: "/incident", label: "Incidents", icon: Server, hint: "Incident Commander agent" },
  { to: "/costs", label: "Costs", icon: Wallet, hint: "Cost Watchdog agent" },
  { to: "/voc", label: "Arabic VoC", icon: MessagesSquare, hint: "Arabic Voice of Customer agent" },
  { to: "/evaluation", label: "Evaluation", icon: BarChart3, hint: "Accuracy on real data" },
  { to: "/reports", label: "Reports", icon: FileText, hint: "Daily brief, outbox" },
  { to: "/system", label: "System", icon: Settings, hint: "Architecture, datasets" },
];

// Ctrl+K: type to jump to any page
function Palette({ open, close }: { open: boolean; close: () => void }) {
  const [query, setQuery] = useState("");
  const go = useNavigate();
  const found = PAGES.filter((p) => (p.label + p.hint).toLowerCase().includes(query.toLowerCase()));
  if (!open) return null;
  const pick = (to: string) => { go(to); setQuery(""); close(); };

  return (
    <div className="fixed inset-0 z-50 grid place-items-start bg-black/50 pt-[15vh] backdrop-blur-sm" onClick={close}>
      <div className="mx-auto w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface-solid shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search size={16} className="text-muted" />
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Jump to..."
                 onKeyDown={(e) => { if (e.key === "Enter" && found[0]) pick(found[0].to); if (e.key === "Escape") close(); }}
                 className="w-full bg-transparent py-4 text-sm outline-none" />
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {found.map(({ to, label, hint, icon: Icon }) => (
            <button key={to} onClick={() => pick(to)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-accent/15">
              <Icon size={16} className="text-accent" /> <span className="font-medium">{label}</span>
              <span className="ml-auto text-xs text-muted">{hint}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [dark, setDark] = useState(true);
  const [health, setHealth] = useState<any>(null);
  const [palette, setPalette] = useState(false);

  useEffect(() => { document.documentElement.classList.toggle("dark", dark); }, [dark]);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); setPalette((p) => !p); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="relative min-h-full">
      {/* Moving colour blobs behind everything */}
      <div className="aurora" aria-hidden><span /><span /><span /></div>

      <header className="sticky top-0 z-40 px-4 pt-4">
        <div className="mx-auto flex max-w-7xl items-center gap-3 rounded-2xl border border-line bg-surface px-3 py-2 shadow-lg backdrop-blur-xl">
          <div className="flex shrink-0 items-center gap-2 pl-1 pr-2">
            <img src="/logo.svg" className="h-7 w-6" alt="" />
            <span className="hidden font-semibold sm:inline">Senti<span className="text-accent">nel</span></span>
          </div>

          <nav className="no-scrollbar flex flex-1 gap-1 overflow-x-auto">
            {PAGES.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end title={label}
                       className={({ isActive }) => `flex shrink-0 items-center gap-2 rounded-xl px-2.5 py-2 text-[13px] transition ${
                         isActive ? "bg-accent text-white shadow-[0_0_20px_-4px_var(--accent)]" : "text-muted hover:bg-surface-2 hover:text-fg"}`}>
                <Icon size={15} /> <span className="hidden xl:inline">{label}</span>
              </NavLink>
            ))}
          </nav>

          <button onClick={() => setPalette(true)}
                  className="hidden shrink-0 items-center gap-2 rounded-xl border border-line px-2.5 py-2 text-xs text-muted hover:text-fg md:flex">
            <Search size={14} /> <kbd className="flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-[10px]"><Command size={10} />K</kbd>
          </button>
          <div className="flex shrink-0 items-center gap-2 rounded-xl px-2 text-xs text-muted"
               title={health ? `LLM: ${health.llm_connected ? health.llm_provider : "offline (rules + ML)"} · ${health.dry_run ? "dry run" : "live email"}` : "API offline"}>
            <span className={`relative flex h-2.5 w-2.5 ${health ? "text-ok" : "text-danger"}`}>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-current" />
            </span>
            <span className="hidden 2xl:inline">{health ? "Live" : "Offline"}</span>
          </div>
          <button onClick={() => setDark(!dark)} className="shrink-0 rounded-xl p-2 text-muted hover:bg-surface-2 hover:text-fg" title="Theme">
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 pb-16 pt-10 sm:px-6">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/phishing" element={<Phishing />} />
          <Route path="/incident" element={<Incident />} />
          <Route path="/costs" element={<Costs />} />
          <Route path="/voc" element={<Voc />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/system" element={<System />} />
          <Route path="*" element={<div className="flex items-center gap-2 text-muted"><Gauge /> Page not found</div>} />
        </Routes>
      </main>
      <Palette open={palette} close={() => setPalette(false)} />
    </div>
  );
}
