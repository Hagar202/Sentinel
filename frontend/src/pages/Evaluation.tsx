import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import { BarChart3, Brain, Gauge, ShieldCheck, Target, Timer } from "lucide-react";
import { api } from "../api";
import { Button, Card, chart, Kpi, Loading, PageHeader, pct, SERIES, useData, VERDICT_COLOR } from "../components/ui";

function LlmComparison({ rows, onRun }: { rows: any[] | null; onRun: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async () => { setBusy(true); setError(""); try { await onRun(); } catch (e: any) { setError(String(e.message ?? e)); } setBusy(false); };
  const metrics = [["detection_rate", "Detection"], ["false_alarm_rate", "False alarms"], ["precision", "Precision"], ["accuracy", "Accuracy"]];
  const chartRows = metrics.map(([key, label]) => ({ metric: label, ...Object.fromEntries((rows ?? []).map((r) => [r.method, r[key]])) }));

  return (
    <Card title="Rules vs LLM agent vs LLM agent + guardrail (same real emails)"
          action={<Button variant="ghost" onClick={run} loading={busy} icon={<Brain size={16} />}>Run on 5 + 5 emails (~3 min)</Button>}>
      {error && <p className="mb-3 text-sm text-danger">{error}</p>}
      {!rows ? (
        <p className="text-sm text-muted">Not run yet. Run it in the notebook (section 11) or with the button. It needs an LLM key, and it is
          slow on purpose: it pauses between emails to stay under the free LLM's rate limit.</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartRows}>
                <CartesianGrid {...chart.grid} />
                <XAxis dataKey="metric" {...chart.axis} />
                <YAxis {...chart.axis} domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <Tooltip {...chart.tooltip} formatter={(v: any) => pct(v, 1)} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {rows.map((r, i) => <Bar key={r.method} dataKey={r.method} fill={SERIES[i]} radius={[4, 4, 0, 0]} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="text-sm lg:col-span-2">
            <thead className="text-left text-xs uppercase text-muted"><tr><th className="pb-2">Method</th><th>Detect</th><th>False</th><th>Acc.</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.method} className="border-t border-line">
                  <td className="py-2 pr-3">{r.method}</td><td>{pct(r.detection_rate)}</td><td>{pct(r.false_alarm_rate)}</td><td>{pct(r.accuracy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-muted lg:col-span-5">{rows[0].phishing_emails} real phishing + {rows[0].normal_emails} real normal emails (a random sample).
            About {Math.round(rows[rows.length - 1].avg_seconds)} s per email with the LLM, about {Math.round(rows[0].avg_seconds * 1000)} ms with the rules.</p>
        </div>
      )}
    </Card>
  );
}

export default function Evaluation() {
  const { data, reload } = useData(api.evaluation);

  return (
    <>
      <PageHeader icon={<BarChart3 />} title="Evaluation" subtitle="Measured on real, labelled data, not on our demo emails." />
      {!data ? <Loading text="Running the agents on 700 real emails and 4,272 reviews..." /> : (
        <div className="space-y-6">
          <h2 className="text-sm font-semibold text-muted">The key experiment: does the LLM agent beat the rules?</h2>
          <LlmComparison rows={data.llm_comparison} onRun={async () => { await api.compareLlm(5); await reload(); }} />

          <h2 className="pt-4 text-sm font-semibold text-muted">Rules + ML alone (the guardrail) · all 200 real phishing + 500 real normal emails</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Kpi label="Detection rate" value={pct(data.phishing.detection_rate)} note="attacks flagged" icon={<Target size={16} />} color="#22c993" />
            <Kpi label="False alarms" value={pct(data.phishing.false_alarm_rate, 1)} note="normal emails flagged" icon={<ShieldCheck size={16} />} color="#22c993" />
            <Kpi label="Precision" value={pct(data.phishing.precision, 1)} note="flagged that were attacks" />
            <Kpi label="Accuracy" value={pct(data.phishing.accuracy, 1)} note="all 700 emails" icon={<Gauge size={16} />} />
            <Kpi label="Speed" value={`${data.phishing.ms_per_email.toFixed(0)} ms`} note="per email, no LLM" icon={<Timer size={16} />} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Verdict by true label">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.by_label}>
                  <CartesianGrid {...chart.grid} />
                  <XAxis dataKey="truth" {...chart.axis} />
                  <YAxis {...chart.axis} />
                  <Tooltip {...chart.tooltip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {["safe", "suspicious", "phishing"].map((v) => <Bar key={v} dataKey={v} fill={VERDICT_COLOR[v]} radius={[4, 4, 0, 0]} />)}
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Scores: normal emails stay low, attacks go high">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.scores}>
                  <CartesianGrid {...chart.grid} />
                  <XAxis dataKey="score" {...chart.axis} />
                  <YAxis {...chart.axis} scale="sqrt" />
                  <Tooltip {...chart.tooltip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="normal" fill="#22c993" />
                  <Bar dataKey="phishing" fill="#f25c69" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
          <p className="text-xs text-muted">Flagged = phishing or suspicious. Normal emails are Enron business emails without headers, so header checks
            can't help them, and the ML model may have seen similar emails in training.</p>

          <h2 className="pt-4 text-sm font-semibold text-muted">Arabic sentiment · word list vs the real star-rating label</h2>
          <div className="grid gap-4 lg:grid-cols-3">
            <Kpi label="Accuracy" value={pct(data.sentiment.accuracy)} note={`${data.sentiment.reviews.toLocaleString()} reviews, 3 classes`} />
            <Card title="Confusion matrix (rows = truth, columns = guess)" className="lg:col-span-2">
              <table className="w-full text-center text-sm">
                <thead><tr><th />{data.confusion.labels.map((l: string) => <th key={l} className="pb-2 text-xs uppercase text-muted">{l}</th>)}</tr></thead>
                <tbody>
                  {data.confusion.rows.map((row: any) => {
                    const total = data.confusion.labels.reduce((s: number, l: string) => s + row[l], 0);
                    return (
                      <tr key={row.truth}>
                        <td className="py-1 pr-3 text-right text-xs uppercase text-muted">{row.truth}</td>
                        {data.confusion.labels.map((l: string) => (
                          <td key={l} className="p-1">
                            <div className="rounded-lg py-3 font-medium" style={{ background: `rgba(139,124,255,${(row[l] / total) * 0.85 + 0.05})` }}>{row[l]}</div>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
          </div>
          <p className="text-xs text-muted">A simple word list is a baseline. With an LLM key, the VoC agent also reads the reviews itself.</p>
        </div>
      )}
    </>
  );
}
