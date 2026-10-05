import {
  AlertTriangle,
  Database,
  Download,
  FileUp,
  GitBranch,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Transaction = {
  transaction_id: string;
  source_account: string;
  destination_account: string;
  amount_minor: number;
  currency: string;
  timestamp_utc: string;
  transaction_type: string;
  channel: string;
};

type CaseGraph = {
  case_id: string;
  seed: string;
  nodes: { id: string; type: string; label: string; risk: number }[];
  edges: {
    id: string;
    source: string;
    target: string;
    type: string;
    amount_minor: number;
    timestamp_utc: string;
  }[];
  patterns: {
    pattern_type: string;
    entities: string[];
    transactions: string[];
    score: number;
    evidence_ids: string[];
  }[];
  evidence: { evidence_id: string; type: string; description: string }[];
  risk: {
    risk_score: number;
    components: { signal: string; contribution: number; evidence_ids: string[] }[];
  };
  excluded_count: number;
  expansion_reasoning: string[];
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function App() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [seed, setSeed] = useState("acc_A");
  const [caseGraph, setCaseGraph] = useState<CaseGraph | null>(null);
  const [status, setStatus] = useState("Waiting for data");

  const accounts = useMemo(
    () => Array.from(
      new Set(transactions.flatMap((tx) => [tx.source_account, tx.destination_account])),
    ).sort(),
    [transactions],
  );

  async function loadTransactions(nextSeed = seed) {
    const response = await fetch(`${apiBaseUrl}/api/v1/transactions`);
    if (!response.ok) {
      setStatus("API unavailable");
      return;
    }
    const data = (await response.json()) as Transaction[];
    setTransactions(data);
    const selected = data.some(
      (tx) => tx.source_account === nextSeed || tx.destination_account === nextSeed,
    )
      ? nextSeed
      : data[0]?.source_account ?? nextSeed;
    setSeed(selected);
    setStatus(data.length ? `${data.length} transactions loaded` : "No transactions loaded");
    if (data.length) await loadCase(selected);
  }

  async function loadCase(nextSeed = seed) {
    const response = await fetch(`${apiBaseUrl}/api/v1/cases/${nextSeed}/graph`);
    if (!response.ok) {
      setCaseGraph(null);
      return;
    }
    setCaseGraph((await response.json()) as CaseGraph);
  }

  async function uploadCsv(file: File) {
    const form = new FormData();
    form.append("file", file);
    setStatus("Importing CSV");
    const response = await fetch(`${apiBaseUrl}/api/v1/transactions/import`, {
      method: "POST",
      body: form,
    });
    const result = await response.json();
    setStatus(`Imported ${result.imported}; skipped ${result.skipped_duplicates}`);
    await loadTransactions();
  }

  useEffect(() => {
    void loadTransactions();
  }, []);

  const risk = caseGraph?.risk.risk_score ?? 0;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">FinTrace</p>
          <h1>Investigation Workspace</h1>
        </div>
        <div className="risk">
          <span>Investigation priority</span>
          <strong>{caseGraph ? risk : "Pending"}</strong>
        </div>
      </header>

      <section className="toolbar" aria-label="Case controls">
        <label>
          Seed account
          <select
            value={seed}
            onChange={(event) => {
              setSeed(event.target.value);
              void loadCase(event.target.value);
            }}
          >
            {accounts.map((account) => (
              <option key={account} value={account}>{account}</option>
            ))}
          </select>
        </label>
        <button onClick={() => void loadTransactions()} aria-label="Refresh case">
          <RefreshCw size={18} />
        </button>
        <a
          className="iconButton"
          href={`${apiBaseUrl}/api/v1/cases/${seed}/export`}
          aria-label="Export case"
        >
          <Download size={18} />
        </a>
        <label className="iconButton" aria-label="Upload CSV">
          <FileUp size={18} />
          <input
            type="file"
            accept=".csv"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void uploadCsv(file);
            }}
          />
        </label>
      </section>

      <section className="workspace">
        <section className="graphPanel" aria-label="Investigation graph">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Case graph</p>
              <h2>{caseGraph?.case_id ?? "No case loaded"}</h2>
            </div>
            <div className="statusPill">{status}</div>
          </div>
          <div className="graphStage">
            {caseGraph?.edges.map((edge, index) => (
              <div className="flowLine" key={edge.id} style={{ top: `${26 + index * 12}%` }}>
                <span>{edge.source}</span>
                <i />
                <strong>{edge.target}</strong>
              </div>
            ))}
            {caseGraph?.nodes.map((node, index) => (
              <div
                className={`node ${node.id === seed ? "source" : ""}`}
                key={node.id}
                style={{
                  left: `${12 + (index % 4) * 22}%`,
                  top: `${18 + Math.floor(index / 4) * 28}%`,
                }}
              >
                <span>{node.label}</span>
                <small>{node.type}</small>
              </div>
            ))}
          </div>
        </section>

        <aside className="casePanel">
          <div className="importBox">
            <Database size={18} />
            <div>
              <strong>{status}</strong>
              <span>CSV import and case graph</span>
            </div>
          </div>

          <section>
            <h2>Risk signals</h2>
            {caseGraph?.risk.components.length ? caseGraph.risk.components.map((component) => (
              <div className="signal" key={`${component.signal}-${component.contribution}`}>
                <AlertTriangle size={16} />
                <span>{component.signal.replace(/_/g, " ")}</span>
                <strong>+{component.contribution}</strong>
              </div>
            )) : (
              <div className="signal">
                <ShieldCheck size={16} />
                No structural signal in this case graph
              </div>
            )}
          </section>

          <section>
            <h2>Detected patterns</h2>
            <div className="table">
              {caseGraph?.patterns.map((pattern) => (
                <div className="row" key={`${pattern.pattern_type}-${pattern.transactions.join("-")}`}>
                  <span>{pattern.pattern_type.replace(/_/g, " ")}</span>
                  <span>{pattern.transactions.join(", ")}</span>
                  <strong>{Math.round(pattern.score * 100)}%</strong>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2>Evidence</h2>
            <div className="evidenceList">
              {caseGraph?.evidence.map((item) => (
                <article key={item.evidence_id}>
                  <strong>{item.evidence_id}</strong>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
          </section>
        </aside>
      </section>

      <section className="timeline" aria-label="Transaction timeline">
        <GitBranch size={18} />
        <div className="rail">
          <span style={{ width: caseGraph?.edges.length ? "64%" : "8%" }} />
        </div>
        <span className="timeLabel">
          {caseGraph?.edges.length ?? 0} visible transactions, {caseGraph?.excluded_count ?? 0} outside this case
        </span>
      </section>
    </main>
  );
}
