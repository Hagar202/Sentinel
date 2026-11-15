import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Inbox, Mail, ScanSearch, Upload } from "lucide-react";
import { api, Result } from "../api";
import ResultPanel from "../components/ResultPanel";
import { Badge, Button, Card, chart, Kpi, PageHeader, pct, Select, useData, VERDICT_COLOR } from "../components/ui";

export default function Phishing() {
  const [tab, setTab] = useState<"one" | "inbox">("one");
  return (
    <>
      <PageHeader icon={<Mail />} title="Phishing Triage"
                  subtitle="Checks headers, links, attachments, wording and an ML model, then decides." />
      <div className="mb-6 inline-flex rounded-xl border border-line bg-surface p-1">
        {[["one", "Analyse an email", Mail], ["inbox", "Scan real phishing", Inbox]].map(([key, label, Icon]: any) => (
          <button key={key} onClick={() => setTab(key)}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm ${tab === key ? "bg-accent/15 font-medium text-accent" : "text-muted"}`}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>
      {tab === "one" ? <AnalyseOne /> : <ScanInbox />}
    </>
  );
}

function AnalyseOne() {
  const emails = useData(api.emails);
  const [source, setSource] = useState("demo");
  const [name, setName] = useState("ceo_fraud_injection.eml");
  const [preview, setPreview] = useState<any>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);

  const names = emails.data ? (source === "demo" ? emails.data.demo : emails.data.real) : [];
  useEffect(() => { if (names.length && !names.includes(name)) setName(names[0]); }, [source, emails.data]); // eslint-disable-line
  useEffect(() => { if (name) api.preview(source, name).then(setPreview).catch(() => setPreview(null)); setResult(null); }, [source, name]);

  const analyse = async () => { setBusy(true); setResult(await api.analyze(source, name)); setBusy(false); };
  const upload = async (file?: File) => { if (!file) return; setBusy(true); setResult(await api.upload(file)); setBusy(false); };

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Select label="Source" value={source} onChange={setSource} options={["demo", "real"]} />
          <div className="min-w-64 flex-1"><Select label="Email" value={name} onChange={setName} options={names} /></div>
          <Button onClick={analyse} loading={busy} icon={<ScanSearch size={16} />}>Analyze email</Button>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-line bg-surface-2 px-4 py-2 text-sm hover:border-accent/50">
            <Upload size={16} /> Upload .eml
            <input type="file" accept=".eml" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
          </label>
        </div>
        <p className="mt-3 text-xs text-muted">
          <b>demo</b> = 3 hand-made emails · <b>real</b> = 200 real phishing emails from honeypot mailboxes (Phishing Pot)
        </p>
      </Card>

      {preview && (
        <Card title="What the agent reads">
          <div className="grid gap-x-8 gap-y-2 text-sm md:grid-cols-2">
            {[["From", `${preview.from_name} <${preview.from_address}>`], ["Reply-To", preview.reply_to || "–"],
              ["Subject", preview.subject], ["SPF / DKIM / DMARC", `${preview.spf} / ${preview.dkim} / ${preview.dmarc}`],
              ["Attachments", preview.attachments.join(", ") || "–"], ["Links", String(preview.links.length)]].map(([k, v]) => (
              <div key={k} className="flex gap-3 border-b border-line py-2"><span className="w-36 shrink-0 text-muted">{k}</span><span className="truncate">{v}</span></div>
            ))}
          </div>
          {preview.links.length > 0 && (
            <div className="mt-4 space-y-1 text-xs">
              {preview.links.slice(0, 5).map((l: any, i: number) => (
                <div key={i} className="truncate rounded-lg bg-surface-2 px-3 py-2">
                  <span className="text-muted">shows</span> {l.text || "(no text)"} <span className="text-muted">→ goes to</span> <span className="text-warn">{l.url}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {result && <ResultPanel result={result} />}
    </div>
  );
}

function ScanInbox() {
  const [count, setCount] = useState(100);
  const [scan, setScan] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); setScan(await api.scan(count)); setBusy(false); };

  const verdicts = scan ? ["phishing", "suspicious", "safe"].map((v) => ({ name: v, value: scan.rows.filter((r: any) => r.verdict === v).length })) : [];
  const histogram = scan ? Object.entries(scan.rows.reduce((h: any, r: any) => { h[r.score] = (h[r.score] ?? 0) + 1; return h; }, {}))
    .map(([score, n]) => ({ score: Number(score), emails: n })).sort((a, b) => a.score - b.score) : [];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <span className="text-sm text-muted">Emails to scan</span>
          <input type="range" min={20} max={200} step={20} value={count} onChange={(e) => setCount(Number(e.target.value))} className="w-64 accent-[#8b7cff]" />
          <span className="w-10 font-semibold">{count}</span>
          <Button onClick={run} loading={busy} icon={<ScanSearch size={16} />}>Scan inbox</Button>
          <span className="text-xs text-muted">Checks + ML only, no LLM.</span>
        </div>
      </Card>
      {scan && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Kpi label="Scanned" value={scan.rows.length} note="real phishing emails" />
            <Kpi label="Caught" value={pct(scan.caught)} note="phishing or suspicious" color="#22c993" />
            <Kpi label="Missed" value={scan.rows.filter((r: any) => r.verdict === "safe").length} note="marked safe" color="#f25c69" />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Verdicts">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie data={verdicts} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90} paddingAngle={3} stroke="none">
                    {verdicts.map((v) => <Cell key={v.name} fill={VERDICT_COLOR[v.name]} />)}
                  </Pie>
                  <Tooltip {...chart.tooltip} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Score distribution (6+ = phishing)" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={histogram}>
                  <CartesianGrid {...chart.grid} />
                  <XAxis dataKey="score" {...chart.axis} />
                  <YAxis {...chart.axis} allowDecimals={false} />
                  <Tooltip {...chart.tooltip} />
                  <Bar dataKey="emails" radius={[4, 4, 0, 0]}>
                    {histogram.map((h) => <Cell key={h.score} fill={h.score >= 6 ? "#f25c69" : h.score >= 3 ? "#f5a524" : "#22c993"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
          <Card title="Results">
            <div className="max-h-[480px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-solid text-left text-xs uppercase tracking-wider text-muted">
                  <tr><th className="pb-3 pr-3">Email</th><th className="pb-3 pr-3">Verdict</th><th className="pb-3 pr-3">Score</th><th className="pb-3 pr-3">Subject</th><th className="pb-3">Main reason</th></tr>
                </thead>
                <tbody>
                  {scan.rows.map((r: any) => (
                    <tr key={r.email} className="border-t border-line">
                      <td className="py-2.5 pr-3 text-muted">{r.email}</td>
                      <td className="pr-3"><Badge verdict={r.verdict} /></td>
                      <td className="pr-3 font-medium">{r.score}</td>
                      <td className="max-w-xs truncate pr-3">{r.subject}</td>
                      <td className="max-w-sm truncate text-muted">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
