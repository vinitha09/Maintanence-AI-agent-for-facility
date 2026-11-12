
import { useEffect, useState } from "react";
import "./App.css";
import AuthPage from "./AuthPage";
import AdminUsersPage from "./AdminUsersPage";
import RegisterMachine from "../features/machines/RegisterMachine";
import MachinesPage from "../features/machines/MachinesPage";
import ManualsPage from "../features/manuals/ManualsPage";
import MaintenanceLogs from "../features/maintenance-logs/MaintenanceLogsPage";
import AskAIPage from "../features/assistant/AskAIPage";
import HierarchyPage from "../features/hierarchy/HierarchyPage";
import { apiFetch, responseError } from "../shared/api";

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
        machine.machine_name ??
        machine.name ??
        machine.machineName ??
        machine.asset_name ??
        "Unnamed machine",
      machine_type:
        machine.machine_code ??
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
  const [organizations, setOrganizations] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [systems, setSystems] = useState([]);
  const [locations, setLocations] = useState([]);
  const [machinesLoading, setMachinesLoading] = useState(true);
  const [scopeType, setScopeType] = useState("machine");
  const [scopeId, setScopeId] = useState("");
  const [workspaceVersion, setWorkspaceVersion] = useState(0);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function loadSession() {
      try {
        const response = await apiFetch("/auth/me");
        if (response.ok) {
          const currentUser = await response.json();
          if (active) setUser(currentUser);
        }
      } catch (requestError) {
        if (active) {
          setError(`Could not connect to the authentication service: ${requestError.message}`);
        }
      } finally {
        if (active) setAuthLoading(false);
      }
    }
    loadSession();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadWorkspace() {
      if (!user) {
        setMachinesLoading(false);
        return;
      }
      setMachinesLoading(true);
      try {
        const paths = [
          "/machines",
          "/organizations",
          "/facilities",
          "/hierarchy/functional-systems",
          "/hierarchy/physical-locations",
        ];
        const responses = await Promise.all(paths.map((path) => apiFetch(path)));
        for (const response of responses) {
          if (!response.ok) {
            throw await responseError(response, "Could not load workspace data.");
          }
        }
        const [machineData, organizationData, facilityData, systemData, locationData] =
          await Promise.all(responses.map((response) => response.json()));
        if (!active) return;
        setMachines(extractMachines(machineData));
        setOrganizations(organizationData);
        setFacilities(facilityData);
        setSystems(systemData);
        setLocations(locationData);
      } catch (err) {
        if (active) setError(err.message || "Could not connect to the backend.");
      } finally {
        if (active) setMachinesLoading(false);
      }
    }
    loadWorkspace();
    return () => {
      active = false;
    };
  }, [workspaceVersion, user]);

  async function handleLogout() {
    try {
      const response = await apiFetch("/auth/logout", { method: "POST" });
      if (!response.ok) {
        throw await responseError(response, "Could not end the session.");
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setUser(null);
      setPage("dashboard");
      setMachines([]);
    }
  }

  async function handleAsk(
    event,
    requestedScope = { scopeType, scopeId }
  ) {
    event.preventDefault();

    if (!question.trim()) {
      setError("Please enter a maintenance question.");
      return;
    }

    if (!requestedScope.scopeId) {
      setError("Please select a machine or hierarchy scope first.");
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");
    setSources([]);

    try {
      const response = await apiFetch("/manuals/search/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          scope_type: requestedScope.scopeType,
          scope_id: Number(requestedScope.scopeId),
          question: question.trim(),
          top_k: 3,
        }),
      });

      if (!response.ok) {
        throw await responseError(response, "Failed to get an answer.");
      }

      if (!response.body) {
        throw new Error(
          "This browser does not support streaming AI responses."
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamedAnswer = "";
      let streamFinished = false;

      async function handleEvent(block) {
        let eventName = "message";
        const dataLines = [];
        for (const line of block.split(/\r?\n/)) {
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }
        if (dataLines.length === 0) return;

        const data = JSON.parse(dataLines.join("\n"));
        if (eventName === "sources") {
          setSources(data.sources ?? []);
        } else if (eventName === "token") {
          streamedAnswer += data.text;
          setAnswer(streamedAnswer);
          await new Promise((resolve) => setTimeout(resolve, 0));
        } else if (eventName === "error") {
          throw new Error(data.detail || "The AI response stream failed.");
        } else if (eventName === "done") {
          streamFinished = true;
        }
      }

      try {
        while (!streamFinished) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let boundary = buffer.match(/\r?\n\r?\n/);
          while (boundary) {
            const block = buffer.slice(0, boundary.index);
            buffer = buffer.slice(boundary.index + boundary[0].length);
            await handleEvent(block);
            if (streamFinished) break;
            boundary = buffer.match(/\r?\n\r?\n/);
          }
        }

        buffer += decoder.decode();
        if (buffer.trim()) await handleEvent(buffer);
      } finally {
        reader.releaseLock();
      }

      if (!streamFinished) {
        throw new Error("The AI response stream ended unexpectedly.");
      }

      if (!streamedAnswer.trim() || streamedAnswer.trim().toLowerCase() === "null") {
        throw new Error("The AI returned an empty response. Please try again.");
      }
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

    const normalizedMachine = extractMachines([machine])[0];
    setMachines((previous) => {
      const exists = previous.some(
        (item) => String(item.id) === String(normalizedMachine.id)
      );

      if (exists) {
        return previous.map((item) =>
          String(item.id) === String(normalizedMachine.id)
            ? normalizedMachine
            : item
        );
      }

      return [...previous, normalizedMachine];
    });

    setScopeType("machine");
    setScopeId(String(normalizedMachine.id));
    setError("");
    setPage("dashboard");
  }

  function handleMachineChanged(machine) {
    setMachines((previous) => {
      if (machine.deleted) {
        return previous.filter((item) => item.id !== machine.id);
      }
      const normalizedMachine = extractMachines([machine])[0];
      return previous.some((item) => item.id === normalizedMachine.id)
        ? previous.map((item) =>
            item.id === normalizedMachine.id ? normalizedMachine : item
          )
        : [...previous, normalizedMachine];
    });
  }

  if (authLoading) {
    return <main className="auth-page">Checking your session…</main>;
  }
  if (!user) {
    return (
      <AuthPage
        notice={error}
        onAuthenticated={(authenticatedUser) => {
          setError("");
          setUser(authenticatedUser);
        }}
      />
    );
  }

  const technicianNavigation = [
    { id: "dashboard", icon: "▦", label: "Dashboard" },
    { id: "machines", icon: "⚙", label: "Machines" },
    { id: "ask", icon: "✧", label: "Ask AI" },
    { id: "manuals", icon: "▤", label: "Manuals" },
    { id: "maintenance", icon: "▣", label: "Maintenance Logs" },
    { id: "register", icon: "+", label: "Register Machine" },
  ].filter(
    (item) =>
      user.role === "ADMIN" ||
      user.is_approved ||
      user.is_invited ||
      !["ask", "register"].includes(item.id)
  );
  const canUseAiAndRegister =
    user.role === "ADMIN" || user.is_approved || user.is_invited;

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
          {technicianNavigation.map((item) => (
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
          <button
            className={`nav-item ${page === "hierarchy" ? "active" : ""}`}
            onClick={() => setPage("hierarchy")}
          >
            <span className="nav-icon">⌂</span>
            Organization &amp; Hierarchy
          </button>
          {user.role === "ADMIN" && (
            <button
              className={`nav-item ${page === "users" ? "active" : ""}`}
              onClick={() => setPage("users")}
            >
              <span className="nav-icon">♙</span>
              User Management
            </button>
          )}
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" />
          {user.name}
          <button type="button" onClick={handleLogout}>Sign out</button>
        </div>
      </aside>

      <main className="main">
        {!canUseAiAndRegister && (
          <div className="approval-notice" role="status">
            Your account is awaiting administrator approval. You can view and
            edit existing records; AI assistance and machine registration will
            be available after approval.
          </div>
        )}
        <header className="topbar">
          <div>
            <p className="eyebrow">INDUSTRIAL MAINTENANCE PLATFORM</p>
            {page === "dashboard" && <h1>Dashboard</h1>}
          </div>
        </header>
        {page === "ask" && canUseAiAndRegister && (
          <AskAIPage
            onBack={() => setPage("dashboard")}
            question={question}
            setQuestion={setQuestion}
            answer={answer}
            streaming={loading && Boolean(answer)}
            sources={sources}
            loading={loading}
            error={error}
            onAsk={handleAsk}
            machines={machines}
            facilities={facilities}
            systems={systems}
            locations={locations}
            machinesLoading={machinesLoading}
            scopeType={scopeType}
            setScopeType={setScopeType}
            scopeId={scopeId}
            setScopeId={setScopeId}
          />
        )}
        {page === "machines" && (
          <MachinesPage
            machines={machines}
            facilities={facilities}
            systems={systems}
            locations={locations}
            isAdmin={user.role === "ADMIN"}
            canRegister={canUseAiAndRegister}
            onRegister={() => setPage("register")}
            onChanged={handleMachineChanged}
          />
        )}
        {page === "manuals" && (
          <ManualsPage
            onBack={() => setPage("dashboard")}
            machines={machines}
            loadingMachines={machinesLoading}
            isAdmin={user.role === "ADMIN"}
          />
        )}
        {page === "maintenance" && (
          <MaintenanceLogs
            machines={machines}
            facilities={facilities}
            systems={systems}
            locations={locations}
            machinesLoading={machinesLoading}
            isAdmin={user.role === "ADMIN"}
            onBack={() => setPage("dashboard")}
            onRegister={
              canUseAiAndRegister ? () => setPage("register") : undefined
            }
          />
        )}
        {page === "register" && canUseAiAndRegister && (
          <RegisterMachine
            onCancel={() => setPage("dashboard")}
            onRegistered={handleRegistered}
            facilities={facilities}
            systems={systems}
            locations={locations}
          />
        )}
        {page === "hierarchy" && (
          <HierarchyPage
            organizations={organizations}
            facilities={facilities}
            machines={machines}
            systems={systems}
            locations={locations}
            isAdmin={user.role === "ADMIN"}
            onBack={() => setPage("dashboard")}
            onChanged={() => setWorkspaceVersion((version) => version + 1)}
          />
        )}
        {page === "users" && user.role === "ADMIN" && (
          <AdminUsersPage currentUser={user} />
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
