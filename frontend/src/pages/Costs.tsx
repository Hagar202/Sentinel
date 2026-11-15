import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Calculator, Coins, PiggyBank, TrendingUp, Wallet } from "lucide-react";
import { api, Result } from "../api";
import ResultPanel from "../components/ResultPanel";
import { Button, Card, chart, Kpi, Loading, money, PageHeader, pct, Select, SERIES, useData } from "../components/ui";

export default function Costs() {
  const [model, setModel] = useState("gpt-4o");
  const [budget, setBudget] = useState(60000);
  const { data } = useData(() => api.costStats(model, budget), [model, budget]);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); setResult(await api.costRun(model, budget)); setBusy(false); };

  return (
    <>
      <PageHeader icon={<Wallet />} title="Cost Watchdog"
                  subtitle="One hour of real LLM traffic from Azure production, priced with today's model prices.">
        <Button onClick={run} loading={busy} icon={<Calculator size={16} />}>Check AI costs</Button>
      </PageHeader>

      <Card className="mb-6">
        <div className="flex flex-wrap items-end gap-6">
          <Select label="Model the company uses today" value={model} onChange={setModel} options={data?.models ?? [model]} />
          <label className="flex flex-col gap-1 text-xs text-muted">
            Monthly AI budget ($)
            <input type="number" step={5000} value={budget} onChange={(e) => setBudget(Number(e.target.value) || 1)}
                   className="w-40 rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus:border-accent" />
          </label>
          {data && <span className="text-xs text-muted">Prices: {data.price_source} · Monthly = this hour × 720</span>}
        </div>
      </Card>

      {!data ? <Loading /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Real requests" value={data.requests.toLocaleString()} note="1 hour, chat + code" icon={<TrendingUp size={16} />} />
            <Kpi label="Monthly cost" value={money(data.monthly_cost)} note={`on ${model}`} icon={<Coins size={16} />} />
            <Kpi label="Budget used" value={pct(data.budget_used)} note={`of ${money(budget)}`}
                 color={data.budget_used > 1 ? "#f25c69" : data.budget_used > 0.8 ? "#f5a524" : "#22c993"} />
            <Kpi label="Cheapest option" value={money(data.cheapest.monthly_cost)} note={`on ${data.cheapest.model}`}
                 icon={<PiggyBank size={16} />} color="#22c993" />
          </div>

          {result && <ResultPanel result={result} />}

          <Card title="Same traffic, different models: $ per month">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={data.comparison} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid {...chart.grid} horizontal={false} vertical />
                <XAxis type="number" {...chart.axis} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} />
                <YAxis type="category" dataKey="model" {...chart.axis} width={130} />
                <Tooltip {...chart.tooltip} formatter={(v: any) => money(v)} />
                <Bar dataKey="monthly_cost" name="monthly cost" radius={[0, 6, 6, 0]}>
                  {data.comparison.map((c: any) => <Cell key={c.model} fill={c.model === model ? "#8b7cff" : "#3b4466"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Requests per minute" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data.per_minute}>
                  <CartesianGrid {...chart.grid} />
                  <XAxis dataKey="time" {...chart.axis} minTickGap={30} />
                  <YAxis {...chart.axis} />
                  <Tooltip {...chart.tooltip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line dataKey="chatbot" stroke={SERIES[0]} strokeWidth={2} dot={false} />
                  <Line dataKey="code_assistant" stroke={SERIES[1]} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Where the money goes">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={data.by_feature} dataKey="cost" nameKey="feature" innerRadius={60} outerRadius={90} paddingAngle={3} stroke="none">
                    {data.by_feature.map((_: any, i: number) => <Cell key={i} fill={SERIES[i]} />)}
                  </Pie>
                  <Tooltip {...chart.tooltip} formatter={(v: any) => `$${Number(v).toFixed(2)} / hour`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title="Prompt size: requests by input tokens">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.prompt_sizes}>
                <CartesianGrid {...chart.grid} />
                <XAxis dataKey="range" {...chart.axis} />
                <YAxis {...chart.axis} />
                <Tooltip {...chart.tooltip} />
                <Bar dataKey="requests" fill="#38bdf8" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}
    </>
  );
}
