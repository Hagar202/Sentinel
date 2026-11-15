import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Bot, Clock, LayoutDashboard, Mail, MessagesSquare, Play, Server, Wallet, Zap } from "lucide-react";
import { api } from "../api";
import AskSentinel from "../components/AskSentinel";
import { Badge, Button, Card, chart, Empty, Kpi, Loading, PageHeader, useData, VERDICT_COLOR } from "../components/ui";

const AGENTS = [
  { name: "Phishing Triage", icon: Mail, data: "Real phishing emails" },
  { name: "Incident Commander", icon: Server, data: "Real SSH + web logs" },
  { name: "Cost Watchdog", icon: Wallet, data: "Real Azure LLM traffic" },
  { name: "Arabic VoC", icon: MessagesSquare, data: "Real Arabic reviews" },
];
const VERDICTS = ["phishing", "critical", "suspicious", "warning", "safe", "ok"];

export default function Overview() {
  const { data, setData, reload } = useData(api.overview);
  const [running, setRunning] = useState(false);

  const runAll = async () => {
    setRunning(true);
    setData(await api.runAll());
    setRunning(false);
  };

  // Turn [{agent, verdict, events}] into one row per agent for the stacked bar chart
  const byAgent = AGENTS.map((a) => {
    const row: Record<string, any> = { agent: a.name.split(" ")[0] };
    data?.counts.filter((c: any) => c.agent === a.name).forEach((c: any) => (row[c.verdict] = c.events));
    return row;
  });
  const totals = VERDICTS.map((v) => ({
    name: v, value: (data?.counts ?? []).filter((c: any) => c.verdict === v).reduce((s: number, c: any) => s + c.events, 0),
  })).filter((t) => t.value > 0);

  return (
    <>
      <PageHeader icon={<LayoutDashboard />} title="Command center"
                  subtitle="Every event goes through the LangGraph Orchestrator to a specialist LLM agent that investigates with tools.">
        <Button onClick={runAll} loading={running} icon={<Play size={16} />}>Run all agents on real data</Button>
      </PageHeader>

      {!data ? <Loading /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Events analysed" value={data.total} note="saved in memory" icon={<Bot size={16} />} />
            <Kpi label="Urgent" value={data.urgent} note="phishing or critical" icon={<AlertTriangle size={16} />} color="#f25c69" />
            <Kpi label="Waiting for you" value={data.waiting} note="actions to approve" icon={<Clock size={16} />} color="#f5a524" />
            <Kpi label="Agents online" value={`${data.agents_online} / 4`} note="orchestrated by LangGraph" icon={<Zap size={16} />} color="#22c993" />
          </div>

          <AskSentinel onDone={reload} />

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {AGENTS.map((agent, i) => {
              const latest = data.latest[i];
              const Icon = agent.icon;
              return (
                <Card key={agent.name} className="flex flex-col">
                  <div className="flex items-center gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent/15 text-accent"><Icon size={18} /></div>
                    <div>
                      <div className="text-sm font-semibold">{agent.name}</div>
                      <div className="text-xs text-muted">{agent.data}</div>
                    </div>
                  </div>
                  {latest ? (
                    <div className="mt-4 space-y-2">
                      <Badge verdict={latest.verdict} />
                      <p className="line-clamp-2 text-sm text-fg/80">{latest.title}</p>
                      <p className="text-xs text-muted">{latest.decided_by ?? "rules"} · {latest.time.slice(11, 16)}</p>
                    </div>
                  ) : <p className="mt-4 text-sm text-muted">Not run yet</p>}
                </Card>
              );
            })}
          </div>

          {data.total === 0 ? <Empty text="No events yet. Click “Run all agents on real data” to start." /> : (
            <>
              <div className="grid gap-4 lg:grid-cols-3">
                <Card title="Events by agent" className="lg:col-span-2">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={byAgent}>
                      <CartesianGrid {...chart.grid} />
                      <XAxis dataKey="agent" {...chart.axis} />
                      <YAxis {...chart.axis} allowDecimals={false} />
                      <Tooltip {...chart.tooltip} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {VERDICTS.map((v) => <Bar key={v} dataKey={v} stackId="a" fill={VERDICT_COLOR[v]} radius={[4, 4, 0, 0]} />)}
                    </BarChart>
                  </ResponsiveContainer>
                </Card>
                <Card title="All verdicts">
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie data={totals} dataKey="value" nameKey="name" innerRadius={65} outerRadius={95} paddingAngle={3} stroke="none">
                        {totals.map((t) => <Cell key={t.name} fill={VERDICT_COLOR[t.name]} />)}
                      </Pie>
                      <Tooltip {...chart.tooltip} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </Card>
              </div>

              <Card title="Activity feed">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-xs uppercase tracking-wider text-muted">
                      <tr><th className="pb-3">Time</th><th>Agent</th><th>Verdict</th><th>Score</th><th>Title</th></tr>
                    </thead>
                    <tbody>
                      {data.feed.map((r: any, i: number) => (
                        <tr key={i} className="border-t border-line">
                          <td className="py-3 pr-4 whitespace-nowrap text-muted">{r.time.slice(11, 19)}</td>
                          <td className="pr-4 whitespace-nowrap">{r.agent}</td>
                          <td className="pr-4"><Badge verdict={r.verdict} /></td>
                          <td className="pr-4 font-medium">{r.score}</td>
                          <td className="max-w-md truncate text-fg/80">{r.title}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      )}
    </>
  );
}
