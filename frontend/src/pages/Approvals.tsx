import { Check, CheckCircle2, Lock, X } from "lucide-react";
import { api } from "../api";
import { Badge, Card, Empty, Kpi, Loading, PageHeader, useData } from "../components/ui";

export default function Approvals() {
  const waiting = useData(api.approvals);
  const log = useData(api.decisions);

  const decide = async (agent: string, action: string, decision: "approved" | "rejected") => {
    await api.decide(agent, action, decision);
    waiting.reload();
    log.reload();
  };

  const approved = log.data?.filter((d) => d.decision === "approved").length ?? 0;
  const rejected = log.data?.filter((d) => d.decision === "rejected").length ?? 0;

  return (
    <>
      <PageHeader icon={<CheckCircle2 />} title="Approvals"
                  subtitle="Human in the loop: agents never block, delete or roll back anything on their own." />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Kpi label="Waiting" value={waiting.data?.length ?? "–"} note="need a decision" color="#f5a524" />
        <Kpi label="Approved" value={approved} color="#22c993" />
        <Kpi label="Rejected" value={rejected} color="#f25c69" />
      </div>

      {!waiting.data ? <Loading /> : waiting.data.length === 0 ? <Empty text="Nothing is waiting for approval." /> : (
        <div className="space-y-3">
          {waiting.data.map((item, i) => (
            <Card key={i}>
              <div className="flex flex-wrap items-center gap-4">
                <Badge verdict={item.verdict} />
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-muted">{item.agent} · {item.title}</div>
                  <div className="mt-1 flex items-center gap-2 font-medium"><Lock size={15} className="text-warn" />{item.action}</div>
                </div>
                <button onClick={() => decide(item.agent, item.action, "approved")}
                        className="inline-flex items-center gap-1 rounded-xl bg-ok/15 px-4 py-2 text-sm font-medium text-ok hover:bg-ok/25">
                  <Check size={16} /> Approve
                </button>
                <button onClick={() => decide(item.agent, item.action, "rejected")}
                        className="inline-flex items-center gap-1 rounded-xl bg-danger/10 px-4 py-2 text-sm font-medium text-danger hover:bg-danger/20">
                  <X size={16} /> Reject
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card title="Decision log (audit trail)" className="mt-6">
        {!log.data?.length ? <p className="text-sm text-muted">No decisions yet.</p> : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wider text-muted">
              <tr><th className="pb-3">Time</th><th>Agent</th><th>Action</th><th>Decision</th></tr>
            </thead>
            <tbody>
              {log.data.map((d, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="py-3 pr-4 text-muted">{d.time}</td>
                  <td className="pr-4">{d.agent}</td>
                  <td className="pr-4">{d.action}</td>
                  <td className={d.decision === "approved" ? "text-ok" : "text-danger"}>{d.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
