
import { useEffect, useState } from "react";
import "./App.css";
import RegisterMachine from "./RegisterMachine";
import ManualsPage from "./ManualsPage";
import MaintenanceLogs from "./MaintenanceLogsPage";
import AskAIPage from "./AskAIPage";

const API_URL = "http://127.0.0.1:8000";

function extractMachines(data) {
  const list = Array.isArray(data)
    ? data
    : data?.machines ??
      data?.data?.machines ??
      data?.data ??
      data?.items ??
      data?.results ??
      data?.records ??
      data?.assets ??
      [];

  if (!Array.isArray(list)) return [];

  return list
    .filter((machine) => machine && typeof machine === "object")
    .map((machine) => ({
      ...machine,
      id: machine.id,
      name:
        machine.name ??
        machine.machine_name ??
        machine.machineName ??
        machine.asset_name ??
        "Unnamed machine",
      machine_type:
        machine.machine_type ??
        machine.type ??
        machine.machineType ??
        "",
    }))
    .filter((machine) => machine.id != null);
}

function App() {
  const [page, setPage] = useState("dashboard");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [machines, setMachines] = useState([]);
  const [machinesLoading, setMachinesLoading] = useState(true);
  const [machineId, setMachineId] = useState("");
  const test = "debugging works"; // Set breakpoint here

  console.log(test);
  async function loadMachines() {
    try {
      const response = await fetch(`${API_URL}/machines`);

      if (!response.ok) {
        throw new Error("Could not load machines.");
      }

      const data = await response.json();
      setMachines(extractMachines(data));
    } catch (err) {
      setError(err.message || "Could not connect to the backend.");
    } finally {
      setMachinesLoading(false);
    }
  }

  useEffect(() => {
    loadMachines();
  }, []);

  async function handleAsk(event) {
    event.preventDefault();

    if (!question.trim()) {
      setError("Please enter a maintenance question.");
      return;
    }

    if (!machineId) {
      setError("Please select a machine first.");
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");
    setSources([]);

    try {
      const response = await fetch(`${API_URL}/manuals/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          machine_id: Number(machineId),
          question: question.trim(),
          top_k: 3,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to get an answer.");
      }

      if (
        typeof data.answer !== "string" ||
        !data.answer.trim() ||
        data.answer.trim().toLowerCase() === "null"
      ) {
        throw new Error(
          "The AI returned an empty response. Please try again."
        );
      }

      setAnswer(data.answer.trim());
      setSources(data.sources ?? []);
    } catch (err) {
      setError(err.message || "Could not connect to the backend.");
    } finally {
      setLoading(false);
    }
  }

  function handleRegistered(machine) {
    if (!machine?.id) {
      setError(
        "Machine registered, but the server did not return its ID."
      );
      return;
    }

    setMachines((previous) => {
      const exists = previous.some(
        (item) => String(item.id) === String(machine.id)
      );

      if (exists) {
        return previous.map((item) =>
          String(item.id) === String(machine.id) ? machine : item
        );
      }

      return [...previous, machine];
    });

    setMachineId(String(machine.id));
    setError("");
    setPage("dashboard");
  }

  const navigation = [
    { id: "dashboard", icon: "▦", label: "Dashboard" },
    { id: "ask", icon: "✧", label: "Ask AI" },
    { id: "manuals", icon: "▤", label: "Manuals" },
    { id: "maintenance", icon: "▣", label: "Maintenance Logs" },
    { id: "register", icon: "+", label: "Register Machine" },
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">⚙</span>
          <div>
            <h2>Maintenance AI</h2>
            <p>Industrial Intelligence</p>
          </div>
        </div>

        <p className="sidebar-section-label">WORKSPACE</p>

        <nav className="sidebar-nav">
          {navigation.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${
                page === item.id ? "active" : ""
              }`}
              onClick={() => {
                setError("");
                setPage(item.id);
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" />
          Maintenance workspace
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">INDUSTRIAL MAINTENANCE PLATFORM</p>
            {page === "dashboard" && <h1>Dashboard</h1>}
          </div>
        </header>
        {page === "ask" && (
          <AskAIPage
            onBack={() => setPage("dashboard")}
            question={question}
            setQuestion={setQuestion}
            answer={answer}
            sources={sources}
            loading={loading}
            error={error}
            onAsk={handleAsk}
            machines={machines}
            machinesLoading={machinesLoading}
            machineId={machineId}
            setMachineId={setMachineId}
          />
        )}
      {page === "manuals" && (
  <ManualsPage
    onBack={() => setPage("dashboard")}
    machines={machines}
    loadingMachines={machinesLoading}
  />
)}
{page === "maintenance" && (
  <MaintenanceLogs
    machines={machines}
    onBack={() => setPage("dashboard")}
    onRegister={() => setPage("register")}
  />
)}
{page === "register" && (
  <RegisterMachine
    onCancel={() => setPage("dashboard")}
    onRegistered={handleRegistered}
  />
)}
        {page === "dashboard" && (
          <>
            <section className="dashboard-welcome">
              <div>
                <p className="eyebrow">MAINTENANCE OVERVIEW</p>
                <h2>Keep your machines running.</h2>
                <p>
                  Monitor equipment, track maintenance activity, and
                  use AI to investigate machine problems.
                </p>
              </div>
              <div className="welcome-symbol">⚙</div>
            </section>

            <section className="dashboard-stats">
              <article className="dashboard-stat">
                <div className="stat-icon machines-icon">▦</div>
                <p>Total Machines</p>
                <h2>{machinesLoading ? "…" : machines.length}</h2>
                <span>Registered equipment</span>
              </article>

              <article className="dashboard-stat">
                <div className="stat-icon tickets-icon">!</div>
                <p>Open Tickets</p>
                <h2>—</h2>
                <span>Connect incident records</span>
              </article>

              <article className="dashboard-stat">
                <div className="stat-icon repair-icon">⚒</div>
                <p>Under Maintenance</p>
                <h2>—</h2>
                <span>Connect maintenance records</span>
              </article>

              <article className="dashboard-stat">
                <div className="stat-icon resolved-icon">✓</div>
                <p>Resolved Tickets</p>
                <h2>—</h2>
                <span>Connect repair history</span>
              </article>
            </section>

            <section className="dashboard-content-grid">
              <article className="dashboard-panel activity-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Recent Maintenance Activity</h2>
                    <p>Your maintenance records will appear here.</p>
                  </div>
                  <span className="panel-heading-icon">◷</span>
                </div>

                <div className="activity-empty">
                  <span className="empty-icon">▤</span>
                  <h3>No activity to display yet</h3>
                  <p>
                    Daily logs, reported problems, and repairs will
                    appear here once records are connected.
                  </p>
                  <button
                    className="secondary-button"
                    onClick={() => setPage("maintenance")}
                  >
                    Open Maintenance Logs
                  </button>
                </div>
              </article>

             
            </section>

            {error && <p className="error-message">{error}</p>}
          </>
        )}

        <footer className="app-footer">
          Maintenance AI · Industrial Maintenance Intelligence · Prototype
        </footer>
      </main>
    </div>
  );
}

export default App;
