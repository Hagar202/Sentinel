import { useState } from "react";
import { Download, FileText, Send } from "lucide-react";
import { api } from "../api";
import { Button, Card, Loading, PageHeader, useData } from "../components/ui";

function download(name: string, content: string, type: string) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = name;
  link.click();
}

export default function Reports() {
  const brief = useData(api.brief);
  const outbox = useData(api.outbox);
  const [status, setStatus] = useState("");

  const send = async () => { setStatus((await api.sendBrief()).status); outbox.reload(); };
  const exportCsv = async () => {
    const results = await api.results();
    const rows = results.map((r) => [r.time, r.agent, r.verdict, r.score, `"${r.title.replace(/"/g, "'")}"`].join(","));
    download("sentinel_results.csv", ["time,agent,verdict,score,title", ...rows].join("\n"), "text/csv");
  };

  return (
    <>
      <PageHeader icon={<FileText />} title="Reports" subtitle="The daily brief for management, exports, and every email Sentinel sent.">
        <Button variant="ghost" onClick={exportCsv} icon={<Download size={16} />}>Export CSV</Button>
        <Button variant="ghost" onClick={() => brief.data && download("sentinel_daily_brief.html", brief.data.html, "text/html")}
                icon={<Download size={16} />}>Brief (HTML)</Button>
        <Button onClick={send} icon={<Send size={16} />}>Send brief now</Button>
      </PageHeader>
      {status && <div className="mb-4 rounded-xl bg-ok/10 px-4 py-3 text-sm text-ok">{status}</div>}

      <div className="grid gap-6 lg:grid-cols-5">
        <Card title="Daily brief" className="lg:col-span-3">
          {!brief.data ? <Loading /> : (
            <>
              <div className="mb-3 text-xs text-muted">{brief.data.subject}</div>
              <div className="rounded-xl bg-white p-5 text-sm text-slate-800" dangerouslySetInnerHTML={{ __html: brief.data.html }} />
            </>
          )}
        </Card>
        <Card title="Outbox" className="lg:col-span-2" action={<span className="text-xs text-muted">dry run: saved, not sent</span>}>
          <div className="max-h-[600px] space-y-2 overflow-y-auto">
            {outbox.data?.length === 0 && <p className="text-sm text-muted">Empty.</p>}
            {outbox.data?.map((mail) => (
              <details key={mail.name} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
                <summary className="cursor-pointer truncate">{mail.html.match(/Subject: (.*?)</)?.[1] ?? mail.name}</summary>
                <div className="mt-3 rounded-lg bg-white p-3 text-xs text-slate-800" dangerouslySetInnerHTML={{ __html: mail.html }} />
              </details>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
