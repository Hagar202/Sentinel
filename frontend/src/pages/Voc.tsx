import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Frown, MessageSquareWarning, MessagesSquare, Sparkles, ThumbsDown } from "lucide-react";
import { api, Result } from "../api";
import ResultPanel from "../components/ResultPanel";
import { Button, Card, chart, Kpi, Loading, PageHeader, pct, Select, useData } from "../components/ui";

const MOOD_COLOR: Record<string, string> = { positive: "#22c993", neutral: "#8b93ad", negative: "#f25c69" };

export default function Voc() {
  const { data } = useData(api.vocStats);
  const [topic, setTopic] = useState("All");
  const [mood, setMood] = useState("negative");
  const list = useData(() => api.vocReviews(topic, mood), [topic, mood]);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); setResult(await api.vocRun()); setBusy(false); };

  return (
    <>
      <PageHeader icon={<MessagesSquare />} title="Arabic Voice of the Customer"
                  subtitle="4,272 real Arabic product reviews from souq.com: what do customers complain about?">
        <Button onClick={run} loading={busy} icon={<Sparkles size={16} />}>Analyze reviews</Button>
      </PageHeader>
      {!data ? <Loading /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Reviews" value={data.reviews.toLocaleString()} note="souq.com, Arabic" icon={<MessagesSquare size={16} />} />
            <Kpi label="Negative" value={pct(data.negative_share)} note="from the star rating" icon={<Frown size={16} />} color="#f25c69" />
            <Kpi label="Top complaint" value={data.top_topic} note={`${data.top_topic_count} unhappy customers`} icon={<MessageSquareWarning size={16} />} color="#f5a524" />
            <Kpi label="Say “don't buy”" value={data.dont_recommend} note="e.g. لا انصح" icon={<ThumbsDown size={16} />} color="#f5a524" />
          </div>

          {result && <ResultPanel result={result} />}

          <div className="grid gap-4 lg:grid-cols-5">
            <Card title="Sentiment" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={data.sentiment} dataKey="count" nameKey="sentiment" innerRadius={65} outerRadius={95} paddingAngle={3} stroke="none">
                    {data.sentiment.map((s: any) => <Cell key={s.sentiment} fill={MOOD_COLOR[s.sentiment]} />)}
                  </Pie>
                  <Tooltip {...chart.tooltip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
            <Card title="What unhappy customers talk about" className="lg:col-span-3">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.topics} layout="vertical" margin={{ left: 30 }}>
                  <CartesianGrid {...chart.grid} horizontal={false} vertical />
                  <XAxis type="number" {...chart.axis} />
                  <YAxis type="category" dataKey="topic" {...chart.axis} width={140} />
                  <Tooltip {...chart.tooltip} />
                  <Bar dataKey="count" name="unhappy customers" fill="#f25c69" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title="Read the reviews" action={<span className="text-xs text-muted">{list.data?.total ?? 0} matching</span>}>
            <div className="mb-4 flex flex-wrap gap-4">
              <Select label="Topic" value={topic} onChange={setTopic} options={["All", ...data.topic_names]} />
              <Select label="Sentiment" value={mood} onChange={setMood} options={["negative", "neutral", "positive", "All"]} />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {list.data?.rows.map((r: any, i: number) => (
                <div key={i} dir="rtl" className="rounded-xl border border-line bg-surface-2 p-4 text-right font-[family-name:var(--font-arabic)] leading-relaxed">
                  {r.text}
                  <div dir="ltr" className="mt-3 flex flex-wrap gap-2 text-left">
                    <span className="rounded-full px-2 py-0.5 text-[11px]" style={{ color: MOOD_COLOR[r.sentiment], background: `${MOOD_COLOR[r.sentiment]}1f` }}>{r.sentiment}</span>
                    {r.topics.map((t: string) => <span key={t} className="rounded-full bg-accent/15 px-2 py-0.5 text-[11px] text-accent">{t}</span>)}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-muted">Labels come from the original star ratings, so a few reviews are labelled wrongly.</p>
          </Card>
        </div>
      )}
    </>
  );
}
