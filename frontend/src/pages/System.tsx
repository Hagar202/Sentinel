import { ArrowRight, Bot, Cpu, Database, ExternalLink, Mail, Settings } from "lucide-react";
import { api } from "../api";
import { Card, Kpi, money, PageHeader, useData } from "../components/ui";

const DATASETS = [
  ["Phishing Triage", "200 real phishing emails", "Phishing Pot", "https://github.com/rf-peixoto/phishing_pot", "CC BY-NC 4.0"],
  ["Phishing evaluation", "500 real normal emails", "Enron-Spam", "https://github.com/MWiechmann/enron_spam_data", "Research"],
  ["Incident Commander", "2,000 SSH + 2,000 Apache log lines", "Loghub", "https://github.com/logpai/loghub", "Research"],
  ["Cost Watchdog", "28,000 real LLM requests", "Azure LLM Inference Trace", "https://github.com/Azure/AzurePublicDataset", "CC BY 4.0"],
  ["Cost Watchdog", "Live model prices", "LiteLLM", "https://github.com/BerriAI/litellm", "MIT"],
  ["Arabic VoC", "4,272 Arabic product reviews", "Elsahar & El-Beltagy 2015", "https://github.com/hadyelsahar/large-arabic-sentiment-analysis-resouces", "Research"],
];
const AGENTS = ["Phishing Triage", "Incident Commander", "Cost Watchdog", "Arabic VoC"];
const KNOWLEDGE = [["security_policy.md", "Phishing Triage"], ["incident_runbook.md", "Incident Commander"], ["ai_cost_policy.md", "Cost Watchdog"]];

function Box({ children, accent = false }: { children: React.ReactNode; accent?: boolean }) {
  return <div className={`rounded-xl border px-4 py-3 text-center text-sm font-medium ${accent ? "border-accent bg-accent/15 text-accent" : "border-line bg-surface-2"}`}>{children}</div>;
}

export default function System() {
  const { data: health } = useData(api.health);

  return (
    <>
      <PageHeader icon={<Settings />} title="System & data" subtitle="Configuration, architecture and where every dataset comes from." />
      {health && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="LLM" value={health.llm_provider} note={health.agents_mode}
               icon={<Bot size={16} />} color={health.llm_connected ? "#22c993" : "#f5a524"} />
          <Kpi label="Emails" value={health.dry_run ? "Dry run" : "Live"} note={health.dry_run ? "saved to outbox" : "sent by SMTP"} icon={<Mail size={16} />} />
          <Kpi label="Cost model" value={health.current_model} note={`budget ${money(health.monthly_budget)}/month`} icon={<Cpu size={16} />} />
          <Kpi label="API docs" value={<a href="/docs" target="_blank" className="text-accent hover:underline">/docs</a>} note="try every endpoint" icon={<Database size={16} />} />
        </div>
      )}

      <Card title="Architecture" className="mb-6">
        <div className="grid items-center gap-4 lg:grid-cols-[1fr_auto_1fr_auto_1.4fr_auto_1fr]">
          <Box>React web app<div className="text-xs font-normal text-muted">this page</div></Box>
          <ArrowRight className="mx-auto text-muted" />
          <Box>FastAPI<div className="text-xs font-normal text-muted">api/main.py</div></Box>
          <ArrowRight className="mx-auto text-muted" />
          <div className="space-y-2">
            <Box accent>Orchestrator · LangGraph<div className="text-xs font-normal">LLM router</div></Box>
            <div className="grid grid-cols-2 gap-2">{AGENTS.map((a) => <Box key={a}>{a}</Box>)}</div>
          </div>
          <ArrowRight className="mx-auto text-muted" />
          <div className="space-y-2"><Box>Tools + guardrails</Box><Box>RAG · Gemini embeddings + FAISS</Box><Box>Memory · SQLite</Box><Box>LLM · Gemini / Groq / OpenAI</Box><Box>Alert step → email</Box></div>
        </div>
      </Card>

      <Card title="Company knowledge (RAG: chunks → Gemini embeddings → FAISS)" className="mb-6">
        <div className="grid gap-3 sm:grid-cols-3">
          {KNOWLEDGE.map(([doc, agent]) => (
            <div key={doc} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
              <div className="font-medium">knowledge/{doc}</div><div className="text-xs text-muted">searched by {agent}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Data sources (all real, all public)">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-muted">
            <tr><th className="pb-3">Used by</th><th>What</th><th>Source</th><th>License</th></tr>
          </thead>
          <tbody>
            {DATASETS.map(([agent, what, source, link, license]) => (
              <tr key={what} className="border-t border-line">
                <td className="py-3 pr-4">{agent}</td>
                <td className="pr-4 text-fg/80">{what}</td>
                <td className="pr-4"><a href={link} target="_blank" className="inline-flex items-center gap-1 text-accent hover:underline">{source} <ExternalLink size={12} /></a></td>
                <td className="text-muted">{license}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
