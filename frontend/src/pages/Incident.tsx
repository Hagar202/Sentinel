import { useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { KeyRound, Radar, Server, ShieldAlert, UserX } from "lucide-react";
import { api, Result } from "../api";
import ResultPanel from "../components/ResultPanel";
import { Button, Card, chart, Kpi, Loading, PageHeader, pct, SERIES, useData } from "../components/ui";

export default function Incident() {
  const { data } = useData(api.incidentStats);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); setResult(await api.incidentRun()); setBusy(false); };

  return (
    <>
      <PageHeader icon={<Server />} title="Incident Commander"
                  subtitle="Reads real server logs (Loghub), finds attacks and error storms, tells the on-call engineer what to do.">
        <Button onClick={run} loading={busy} icon={<Radar size={16} />}>Investigate incident</Button>
      </PageHeader>
      {!data ? <Loading /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Failed SSH logins" value={data.failed_logins} note="2,000 real log lines" icon={<KeyRound size={16} />} color="#f25c69" />
            <Kpi label="Attacking IPs" value={data.attacking_ips} note="20+ failed logins each" icon={<ShieldAlert size={16} />} color="#f5a524" />
            <Kpi label="Usernames guessed" value={data.usernames_guessed} note="users that don't exist" icon={<UserX size={16} />} />
            <Kpi label="Web error rate" value={pct(data.web_error_rate)} note="Apache log" icon={<Server size={16} />} color="#f5a524" />
          </div>

          {result && <ResultPanel result={result} />}

          <div className="grid gap-4 lg:grid-cols-5">
            <Card title="SSH events per minute" className="lg:col-span-3">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.per_minute}>
                  <CartesianGrid {...chart.grid} />
                  <XAxis dataKey="minute" {...chart.axis} minTickGap={40} tickFormatter={(m) => m.slice(7)} />
                  <YAxis {...chart.axis} />
                  <Tooltip {...chart.tooltip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {data.events.map((e: string, i: number) => <Bar key={e} dataKey={e} stackId="a" fill={SERIES[i]} />)}
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Top attacking IPs" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.top_ips} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid {...chart.grid} horizontal={false} vertical />
                  <XAxis type="number" {...chart.axis} />
                  <YAxis type="category" dataKey="ip" {...chart.axis} width={110} />
                  <Tooltip {...chart.tooltip} />
                  <Bar dataKey="count" name="failed logins" fill="#f25c69" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title="Web server errors per minute">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={data.web_errors}>
                <defs>
                  <linearGradient id="err" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f5a524" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#f5a524" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid {...chart.grid} />
                <XAxis dataKey="minute" {...chart.axis} minTickGap={60} />
                <YAxis {...chart.axis} />
                <Tooltip {...chart.tooltip} />
                <Area type="monotone" dataKey="errors" stroke="#f5a524" fill="url(#err)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </Card>

          <Card title="Latest login events">
            <div className="max-h-72 overflow-y-auto font-mono text-xs">
              {data.recent.map((r: any, i: number) => (
                <div key={i} className="flex gap-4 border-t border-line py-2">
                  <span className="text-muted">{r.time}</span>
                  <span className={r.event === "successful login" ? "text-ok" : "text-danger"}>{r.event}</span>
                  <span>{r.user}</span>
                  <span className="text-muted">{r.ip}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
