import { useEffect, useState } from "react";
import "./MaintenanceLogs.css";

const API_URL = "http://127.0.0.1:8000";

function MaintenanceLogsPage({ machines = [], onBack, onRegister }) {
  const [activeTab, setActiveTab] = useState("daily");
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [logsError, setLogsError] = useState("");
  const [saving, setSaving] = useState(false);
  const [closingProblemId, setClosingProblemId] = useState(null);

  const [daily, setDaily] = useState({
    machineId: "",
    date: new Date().toISOString().slice(0, 10),
    shift: "Morning",
    status: "Operational",
    observations: "",
  });

  const [problem, setProblem] = useState({
    machineId: "",
    date: new Date().toISOString().slice(0, 10),
    severity: "Medium",
    symptoms: "",
    description: "",
  });

  const [repair, setRepair] = useState({
    machineId: "",
    problemDescription: "",
    actions: "",
    outcome: "",
    verified: false,
  });

  const machineName = (id) =>
    machines.find((machine) => String(machine.id) === String(id))
      ?.name ?? "Unknown machine";

  const updateField = (setter, field, value) => {
    setter((previous) => ({ ...previous, [field]: value }));
  };

  useEffect(() => {
    let active = true;

    async function fetchLogs() {
      try {
        const response = await fetch(`${API_URL}/maintenance-logs`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Could not load maintenance logs.");
        }
        if (active) setLogs(Array.isArray(data) ? data : []);
      } catch (err) {
        if (active) {
          setLogsError(err.message || "Could not connect to the backend.");
        }
      } finally {
        if (active) setLogsLoading(false);
      }
    }

    fetchLogs();
    return () => {
      active = false;
    };
  }, []);

  async function saveLog(logData) {
    setSaving(true);
    setLogsError("");

    try {
      const response = await fetch(`${API_URL}/maintenance-logs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(logData),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not save this maintenance log.");
      }
      setLogs((previous) => [data, ...previous]);
      return true;
    } catch (err) {
      setLogsError(err.message || "Could not connect to the backend.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function saveDailyLog(event) {
    event.preventDefault();

    const saved = await saveLog({
      machine_id: Number(daily.machineId),
      record_type: "daily",
      recorded_on: daily.date,
      shift: daily.shift,
      machine_status: daily.status,
      description: daily.observations,
    });
    if (!saved) return;

    setDaily((previous) => ({
      ...previous,
      date: new Date().toISOString().slice(0, 10),
      shift: "Morning",
      status: "Operational",
      observations: "",
    }));
  }

  async function saveProblem(event) {
    event.preventDefault();

    const saved = await saveLog({
      machine_id: Number(problem.machineId),
      record_type: "problem",
      recorded_on: problem.date,
      severity: problem.severity,
      symptoms: problem.symptoms,
      description: problem.description,
    });
    if (!saved) return;

    setProblem({
      machineId: "",
      date: new Date().toISOString().slice(0, 10),
      severity: "Medium",
      symptoms: "",
      description: "",
    });

  }

  async function saveRepair(event) {
    event.preventDefault();

    const saved = await saveLog({
      machine_id: Number(repair.machineId),
      record_type: "repair",
      recorded_on: new Date().toISOString().slice(0, 10),
      problem_description: repair.problemDescription,
      actions: repair.actions,
      outcome: repair.outcome,
      verified: repair.verified,
    });
    if (!saved) return;

    setRepair({
      machineId: "",
      problemDescription: "",
      actions: "",
      outcome: "",
      verified: false,
    });

  }

  async function closeProblem(logId) {
    setClosingProblemId(logId);
    setLogsError("");

    try {
      const response = await fetch(
        `${API_URL}/maintenance-logs/${logId}/close`,
        { method: "PATCH" }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not close this problem report.");
      }
      setLogs((previous) =>
        previous.map((log) => (log.id === logId ? data : log))
      );
    } catch (err) {
      setLogsError(err.message || "Could not connect to the backend.");
    } finally {
      setClosingProblemId(null);
    }
  }

  const tabs = [
    { id: "daily", label: "Daily Logs", icon: "▤" },
    { id: "problems", label: "Report Problem", icon: "⚠" },
    { id: "repairs", label: "Record Repair", icon: "🔧" },
  ];
  const dailyLogs = logs.filter((log) => log.record_type === "daily");
  const problems = logs.filter((log) => log.record_type === "problem");
  const repairs = logs.filter((log) => log.record_type === "repair");
  const activeRecordType = {
    daily: "daily",
    problems: "problem",
    repairs: "repair",
  }[activeTab];
  const activeLogs = logs.filter(
    (log) => log.record_type === activeRecordType
  );

  return (
    <div className="page-content maintenance-page">
      <button className="page-back-button" onClick={onBack}>
        <span aria-hidden="true">←</span>
        Back to Dashboard
      </button>

      <div className="maintenance-page-heading">
        <div>
          <p className="eyebrow">SERVICE RECORDS</p>
          <h1>Maintenance Logs</h1>
          <p>
            Record daily inspections, report equipment issues, and document
            completed repairs.
          </p>
        </div>
        <button
          type="button"
          className="maintenance-register-button"
          onClick={onRegister}
        >
          + Register a Machine
        </button>
      </div>

      <section className="maintenance-summary">
        <button
          type="button"
          className={`maintenance-summary-card ${activeTab === "daily" ? "active" : ""}`}
          aria-pressed={activeTab === "daily"}
          onClick={() => setActiveTab("daily")}
        >
          <span>DAILY LOGS</span>
          <strong>{logsLoading ? "…" : dailyLogs.length}</strong>
          <p>Machine activity records</p>
        </button>
        <button
          type="button"
          className={`maintenance-summary-card ${activeTab === "problems" ? "active" : ""}`}
          aria-pressed={activeTab === "problems"}
          onClick={() => setActiveTab("problems")}
        >
          <span>REPORTED PROBLEMS</span>
          <strong>{logsLoading ? "…" : problems.length}</strong>
          <p>Recorded machine faults</p>
        </button>
        <button
          type="button"
          className={`maintenance-summary-card ${activeTab === "repairs" ? "active" : ""}`}
          aria-pressed={activeTab === "repairs"}
          onClick={() => setActiveTab("repairs")}
        >
          <span>REPAIR RECORDS</span>
          <strong>{logsLoading ? "…" : repairs.length}</strong>
          <p>Documented repairs</p>
        </button>
      </section>

      <nav className="maintenance-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={
              activeTab === tab.id ? "maintenance-tab active" : "maintenance-tab"
            }
            onClick={() => setActiveTab(tab.id)}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      <section className="maintenance-card maintenance-records">
        <div className="maintenance-section-heading">
          <div>
            <h2>
              {activeTab === "daily"
                ? "Recent Daily Logs"
                : activeTab === "problems"
                  ? "Reported Problems"
                  : "Repair History"}
            </h2>
            <p>Maintenance records saved for this category.</p>
          </div>
        </div>

        {logsError && (
          <p className="error-message" role="alert">
            {logsError}
          </p>
        )}

        {logsLoading ? (
          <p className="maintenance-empty">
            Loading saved maintenance records...
          </p>
        ) : activeLogs.length === 0 ? (
          <p className="maintenance-empty">
            No records in this category yet. Submit the form below to add one.
          </p>
        ) : (
          activeLogs.map((log) => (
            <article className="maintenance-record" key={log.id}>
              <div>
                <strong>{machineName(log.machine_id)}</strong>
                <p>
                  {log.recorded_on}
                  {log.shift ? ` · ${log.shift} shift` : ""}
                  {log.machine_status ? ` · ${log.machine_status}` : ""}
                  {log.severity ? ` · ${log.severity} priority` : ""}
                </p>
                {log.symptoms && <p>Symptoms: {log.symptoms}</p>}
                {log.problem_description && (
                  <p>Problem: {log.problem_description}</p>
                )}
                {log.description && <p>{log.description}</p>}
                {log.actions && <p>Repair: {log.actions}</p>}
                {log.outcome && <p>Outcome: {log.outcome}</p>}
              </div>
              <div className="maintenance-record-actions">
                {log.record_type === "problem" && (
                  <>
                    <span
                      className={`problem-status ${log.status === "closed" ? "closed" : "open"}`}
                    >
                      {log.status === "closed" ? "Closed" : "Open"}
                    </span>
                    {log.status !== "closed" && (
                      <button
                        type="button"
                        className="maintenance-close-button"
                        disabled={closingProblemId === log.id}
                        onClick={() => closeProblem(log.id)}
                      >
                        {closingProblemId === log.id
                          ? "Closing..."
                          : "Close problem"}
                      </button>
                    )}
                  </>
                )}
                {log.record_type === "repair" && (
                  <span
                    className={
                      log.verified
                        ? "verification verified"
                        : "verification unverified"
                    }
                  >
                    {log.verified ? "Verified" : "Unverified"}
                  </span>
                )}
              </div>
            </article>
          ))
        )}
      </section>

      {activeTab === "daily" && (
        <section className="maintenance-card">
          <div className="maintenance-section-heading">
            <div>
              <h2>Daily Machine Log</h2>
              <p>Record inspections, activities, and machine conditions.</p>
            </div>
          </div>

          <form onSubmit={saveDailyLog}>
            <div className="maintenance-form-grid">
              <label>
                Machine *
                <select
                  required
                  value={daily.machineId}
                  onChange={(e) =>
                    updateField(setDaily, "machineId", e.target.value)
                  }
                >
                  <option value="">Select a machine</option>
                  {machines.map((machine) => (
                    <option key={machine.id} value={machine.id}>
                      {machine.name} — {machine.machine_type}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Date *
                <input
                  type="date"
                  required
                  value={daily.date}
                  onChange={(e) =>
                    updateField(setDaily, "date", e.target.value)
                  }
                />
              </label>

              <label>
                Shift
                <select
                  value={daily.shift}
                  onChange={(e) =>
                    updateField(setDaily, "shift", e.target.value)
                  }
                >
                  <option>Morning</option>
                  <option>Afternoon</option>
                  <option>Night</option>
                </select>
              </label>

              <label>
                Machine status
                <select
                  value={daily.status}
                  onChange={(e) =>
                    updateField(setDaily, "status", e.target.value)
                  }
                >
                  <option>Operational</option>
                  <option>Under maintenance</option>
                  <option>Stopped</option>
                </select>
              </label>
            </div>

            <label className="maintenance-full-field">
              Observations and activities *
              <textarea
                required
                rows="5"
                placeholder="Describe inspections, machine performance, unusual noises, temperature changes, or other observations..."
                value={daily.observations}
                onChange={(e) =>
                  updateField(setDaily, "observations", e.target.value)
                }
              />
            </label>

            <button
              className="maintenance-submit"
              type="submit"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Daily Log"}
            </button>
          </form>
        </section>
      )}

      {activeTab === "problems" && (
        <section className="maintenance-card">
          <div className="maintenance-section-heading">
            <div>
              <h2>Report a Machine Problem</h2>
              <p>Record a fault so its diagnosis and repair can be tracked.</p>
            </div>
          </div>

          <form onSubmit={saveProblem}>
            <div className="maintenance-form-grid">
              <label>
                Machine *
                <select
                  required
                  value={problem.machineId}
                  onChange={(e) =>
                    updateField(setProblem, "machineId", e.target.value)
                  }
                >
                  <option value="">Select a machine</option>
                  {machines.map((machine) => (
                    <option key={machine.id} value={machine.id}>
                      {machine.name} — {machine.machine_type}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Date observed *
                <input
                  type="date"
                  required
                  value={problem.date}
                  onChange={(e) =>
                    updateField(setProblem, "date", e.target.value)
                  }
                />
              </label>

              <label>
                Severity
                <select
                  value={problem.severity}
                  onChange={(e) =>
                    updateField(setProblem, "severity", e.target.value)
                  }
                >
                  <option>Low</option>
                  <option>Medium</option>
                  <option>High</option>
                  <option>Critical</option>
                </select>
              </label>
            </div>

            <label className="maintenance-full-field">
              Symptoms *
              <input
                required
                placeholder="e.g. Unusual vibration and rising temperature"
                value={problem.symptoms}
                onChange={(e) =>
                  updateField(setProblem, "symptoms", e.target.value)
                }
              />
            </label>

            <label className="maintenance-full-field">
              Problem description *
              <textarea
                required
                rows="4"
                placeholder="Describe what happened, when it started, and any relevant observations..."
                value={problem.description}
                onChange={(e) =>
                  updateField(setProblem, "description", e.target.value)
                }
              />
            </label>

            <button
              className="maintenance-submit"
              type="submit"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Problem Report"}
            </button>
          </form>
        </section>
      )}

      {activeTab === "repairs" && (
        <section className="maintenance-card">
          <div className="maintenance-section-heading">
            <div>
              <h2>Record a Repair</h2>
              <p>Document what was done and whether the repair worked.</p>
            </div>
          </div>

          <form onSubmit={saveRepair}>
            <div className="maintenance-form-grid">
              <label>
                Machine *
                <select
                  required
                  value={repair.machineId}
                  onChange={(e) =>
                    updateField(setRepair, "machineId", e.target.value)
                  }
                >
                  <option value="">Select a machine</option>
                  {machines.map((machine) => (
                    <option key={machine.id} value={machine.id}>
                      {machine.name} — {machine.machine_type}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Related problem *
                <input
                  required
                  placeholder="Describe or identify the fault"
                  value={repair.problemDescription}
                  onChange={(e) =>
                    updateField(
                      setRepair,
                      "problemDescription",
                      e.target.value
                    )
                  }
                />
              </label>
            </div>

            <label className="maintenance-full-field">
              Repair actions *
              <textarea
                required
                rows="4"
                placeholder="Describe the diagnosis, repair steps, and any parts replaced..."
                value={repair.actions}
                onChange={(e) =>
                  updateField(setRepair, "actions", e.target.value)
                }
              />
            </label>

            <label className="maintenance-full-field">
              Repair outcome *
              <textarea
                required
                rows="3"
                placeholder="Did the machine return to normal operation? What was tested?"
                value={repair.outcome}
                onChange={(e) =>
                  updateField(setRepair, "outcome", e.target.value)
                }
              />
            </label>

            <label className="maintenance-checkbox">
              <input
                type="checkbox"
                checked={repair.verified}
                onChange={(e) =>
                  updateField(setRepair, "verified", e.target.checked)
                }
              />
              <span>
                <strong>Solution verified</strong>
                <small>
                  Check only if an authorized person has confirmed the repair.
                </small>
              </span>
            </label>

            <button
              className="maintenance-submit"
              type="submit"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Repair Record"}
            </button>
          </form>
        </section>
      )}

      <p className="maintenance-note">
        Maintenance records are saved to the server and remain available after
        refresh. Supporting file attachments are not stored yet.
      </p>
    </div>
  );
}

export default MaintenanceLogsPage;