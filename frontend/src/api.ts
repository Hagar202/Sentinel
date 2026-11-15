// Every call from the web app to the Sentinel FastAPI backend lives here.

export type Finding = { reason: string; points: number };
export type Action = { action: string; needs_approval: boolean };
export type Step = { tool: string; input: Record<string, unknown>; result: string };
export type Result = {
  agent: string;
  title: string;
  verdict: string;
  score: number;
  findings: Finding[];
  summary: string;
  actions: Action[];
  steps: Step[];          // the agent's thinking: which tools it called and what came back
  decided_by: string;     // "LLM agent", "LLM agent + guardrail" or "rules (offline)"
  extra: Record<string, any>;
  time: string;
};
export type AskAnswer = { agent: string; route_reason: string; result: Result; messages: string[] };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json();
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

export const api = {
  health: () => request<any>("/health"),
  graph: () => request<{ mermaid: string }>("/system/graph"),

  overview: () => request<any>("/overview"),
  ask: (text: string) => post<AskAnswer>("/ask", { text }),
  runAll: () => post<any>("/run-all"),

  emails: () => request<{ demo: string[]; real: string[] }>("/phishing/emails"),
  preview: (source: string, name: string) => request<any>(`/phishing/preview?source=${source}&name=${name}`),
  analyze: (source: string, name: string) => post<Result>("/phishing/analyze", { source, name }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Result>("/phishing/upload", { method: "POST", body: form });
  },
  scan: (count: number) => request<any>(`/phishing/scan?count=${count}`),

  incidentStats: () => request<any>("/incident/stats"),
  incidentRun: () => post<Result>("/incident/run"),

  costStats: (model: string, budget: number) => request<any>(`/costs/stats?model=${model}&budget=${budget}`),
  costRun: (model: string, budget: number) => post<Result>("/costs/run", { model, budget }),

  vocStats: () => request<any>("/voc/stats"),
  vocReviews: (topic: string, sentiment: string) => request<any>(`/voc/reviews?topic=${encodeURIComponent(topic)}&sentiment=${sentiment}`),
  vocRun: () => post<Result>("/voc/run"),

  approvals: () => request<any[]>("/approvals"),
  decide: (agent: string, action: string, decision: "approved" | "rejected") =>
    post("/approvals", { agent, action, decision }),
  decisions: () => request<any[]>("/decisions"),

  evaluation: () => request<any>("/evaluation"),
  compareLlm: (emails_each: number) => post<any[]>("/evaluation/llm", { emails_each }),
  brief: () => request<{ subject: string; html: string }>("/reports/brief"),
  sendBrief: () => post<{ status: string }>("/reports/send"),
  results: () => request<Result[]>("/results"),
  outbox: () => request<{ name: string; html: string }[]>("/outbox"),
};
