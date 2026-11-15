// "Tell Sentinel what happened": any message in plain words -> the LLM router picks the agent -> the agent investigates.
import { useState } from "react";
import { GitBranch, Send } from "lucide-react";
import { api, AskAnswer } from "../api";
import ResultPanel from "./ResultPanel";
import { Button, Card } from "./ui";

const EXAMPLES = [
  "Our website is very slow and some people can't log in to the server",
  "The OpenAI bill this month is much higher than our budget",
  "العملاء بيشتكوا إن الخامة وحشة والمنتج بيبوظ بسرعة",
  "I got an email from 'IT support' asking me to confirm my password today",
];

export default function AskSentinel({ onDone }: { onDone?: () => void }) {
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const send = async () => {
    setBusy(true); setError("");
    try { setAnswer(await api.ask(text)); onDone?.(); }
    catch (e: any) { setError(String(e.message ?? e)); }
    setBusy(false);
  };

  return (
    <div className="space-y-4">
      <Card title="Tell Sentinel what happened" action={<span className="text-xs text-muted">the LLM router picks the agent</span>}>
        <textarea value={text} onChange={(e) => setText(e.target.value)} dir="auto" rows={3}
                  placeholder="Write anything: a problem, a complaint, or paste a suspicious email..."
                  className="w-full resize-y rounded-xl border border-line bg-surface-2 p-3 text-sm outline-none focus:border-accent" />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {EXAMPLES.map((example) => (
            <button key={example} onClick={() => setText(example)} dir="auto"
                    className="max-w-xs truncate rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-accent hover:text-fg">
              {example}
            </button>
          ))}
          <div className="ml-auto"><Button onClick={send} loading={busy} disabled={!text.trim()} icon={<Send size={16} />}>Send to the Orchestrator</Button></div>
        </div>
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      </Card>
      {answer && (
        <>
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm">
            <GitBranch size={16} className="text-accent" />
            <span className="font-medium">Router → {answer.result.agent}</span>
            <span className="text-muted">· {answer.route_reason}</span>
          </div>
          <ResultPanel result={answer.result} />
        </>
      )}
    </div>
  );
}
