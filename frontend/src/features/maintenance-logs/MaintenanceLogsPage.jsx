import { useEffect, useState } from "react";
import "./MaintenanceLogs.css";
import { apiFetch } from "../../shared/api";

const INITIAL_DATE = new Date().toISOString().slice(0, 10);

function getDescendantIds(items, rootId) {
  const descendants = new Set([String(rootId)]);
  const pending = [String(rootId)];

  while (pending.length) {
    const parentId = pending.pop();
    for (const item of items) {
      if (
        String(item.parent_id) === parentId &&
        !descendants.has(String(item.id))
      ) {
        descendants.add(String(item.id));
        pending.push(String(item.id));
      }
    }
  }

  return descendants;
}

function MachineHierarchySelector({
  idPrefix,
  facilities,
  systems,
  locations,
  machines,
  machinesLoading,
  machineId,
  onMachineChange,
}) {
  const [selectionMode, setSelectionMode] = useState("hierarchy");
  const selectedMachine = machines.find(
    (machine) => String(machine.id) === String(machineId)
  );
  const [facilityId, setFacilityId] = useState(
    selectedMachine ? String(selectedMachine.facility_id) : ""
  );
  const [systemId, setSystemId] = useState(
    selectedMachine?.functional_system_id
      ? String(selectedMachine.functional_system_id)
      : ""
  );
  const [locationId, setLocationId] = useState(
    selectedMachine?.physical_location_id
      ? String(selectedMachine.physical_location_id)
      : ""
  );

  const facilitySystems = systems.filter(
    (system) => String(system.facility_id) === facilityId
  );
  const facilityLocations = locations.filter(
    (location) => String(location.facility_id) === facilityId
  );
  const systemIds = systemId
    ? getDescendantIds(facilitySystems, systemId)
    : new Set();
  const locationIds = locationId
    ? getDescendantIds(facilityLocations, locationId)
    : new Set();
  const filteredMachines = machines.filter(
    (machine) =>
      String(machine.facility_id) === facilityId &&
      systemIds.has(String(machine.functional_system_id)) &&
      locationIds.has(String(machine.physical_location_id))
  );

  if (selectionMode === "single") {
    return (
      <>
        <label>
          Machine selection *
          <select
            value={selectionMode}
            onChange={(event) => {
              setSelectionMode(event.target.value);
              onMachineChange("");
            }}
          >
            <option value="hierarchy">Select by facility hierarchy</option>
            <option value="single">Select one machine directly</option>
          </select>
        </label>
        <label>
          Machine name *
          <select
            id={`${idPrefix}-machine`}
            required
            value={machineId}
            disabled={machinesLoading}
            onChange={(event) => onMachineChange(event.target.value)}
          >
            <option value="">Select a machine</option>
            {machines.map((machine) => (
              <option key={machine.id} value={String(machine.id)}>
                {machine.machine_name ?? machine.name}
                {machine.machine_code ?? machine.machine_type
                  ? ` — ${machine.machine_code ?? machine.machine_type}`
                  : ""}
              </option>
            ))}
          </select>
        </label>
      </>
    );
  }

  return (
    <>
      <label>
        Machine selection *
        <select
          value={selectionMode}
          onChange={(event) => {
            setSelectionMode(event.target.value);
            onMachineChange("");
          }}
        >
          <option value="hierarchy">Select by facility hierarchy</option>
          <option value="single">Select one machine directly</option>
        </select>
      </label>

      <label>
        Facility *
        <select
          required
          value={facilityId}
          disabled={machinesLoading}
          onChange={(event) => {
            setFacilityId(event.target.value);
            setSystemId("");
            setLocationId("");
            onMachineChange("");
          }}
        >
          <option value="">Select a facility</option>
          {facilities.map((facility) => (
            <option key={facility.id} value={String(facility.id)}>
              {facility.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Functional system *
        <select
          required
          value={systemId}
          disabled={!facilityId || machinesLoading}
          onChange={(event) => {
            setSystemId(event.target.value);
            setLocationId("");
            onMachineChange("");
          }}
        >
          <option value="">Select a functional system</option>
          {facilitySystems.map((system) => (
            <option key={system.id} value={String(system.id)}>
              {system.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Physical location *
        <select
          required
          value={locationId}
          disabled={!systemId || machinesLoading}
          onChange={(event) => {
            setLocationId(event.target.value);
            onMachineChange("");
          }}
        >
          <option value="">Select a physical location</option>
          {facilityLocations.map((location) => (
            <option key={location.id} value={String(location.id)}>
              {location.name} — {location.location_type}
            </option>
          ))}
        </select>
      </label>

      <label>
        Machine name *
        <select
          id={`${idPrefix}-machine`}
          required
          value={machineId}
          disabled={!locationId || machinesLoading}
          onChange={(event) => onMachineChange(event.target.value)}
        >
          <option value="">
            {locationId && filteredMachines.length === 0
              ? "No machines in this system and location"
              : "Select a machine"}
          </option>
          {filteredMachines.map((machine) => (
            <option key={machine.id} value={String(machine.id)}>
              {machine.machine_name ?? machine.name}
              {machine.machine_code ?? machine.machine_type
                ? ` — ${machine.machine_code ?? machine.machine_type}`
                : ""}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}

function MaintenanceLogsPage({
  machines = [],
  facilities = [],
  systems = [],
  locations = [],
  machinesLoading = false,
  isAdmin = false,
  onBack,
  onRegister,
}) {
  const [activeTab, setActiveTab] = useState("daily");
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [logsError, setLogsError] = useState("");
  const [saving, setSaving] = useState(false);
  const [closingProblemId, setClosingProblemId] = useState(null);
  const [editingLog, setEditingLog] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  const [daily, setDaily] = useState({
    machineId: "",
    date: INITIAL_DATE,
    observations: "",
  });

  const [problem, setProblem] = useState({
    machineId: "",
    date: INITIAL_DATE,
    symptoms: "",
    description: "",
  });

  const [repair, setRepair] = useState({
    machineId: "",
    problemDescription: "",
    actions: "",
    outcome: "",
  });

  const machineName = (id) => {
    const machine = machines.find(
      (item) => String(item.id) === String(id)
    );
    return machine?.machine_name ?? machine?.name ?? "Unknown machine";
  };

  const updateField = (setter, field, value) => {
    setter((previous) => ({ ...previous, [field]: value }));
  };

  useEffect(() => {
    let active = true;

    async function fetchLogs() {
      try {
        const response = await apiFetch("/maintenance-logs");
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
      const response = await apiFetch("/maintenance-logs", {
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
      description: daily.observations,
    });
    if (!saved) return;

    setDaily((previous) => ({
      ...previous,
      date: new Date().toISOString().slice(0, 10),
      observations: "",
    }));
  }

  async function saveProblem(event) {
    event.preventDefault();

    const saved = await saveLog({
      machine_id: Number(problem.machineId),
      record_type: "problem",
      recorded_on: problem.date,
      symptoms: problem.symptoms,
      description: problem.description,
    });
    if (!saved) return;

    setProblem({
      machineId: "",
      date: new Date().toISOString().slice(0, 10),
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
      description: repair.problemDescription,
      repair_actions: repair.actions,
      outcome: repair.outcome,
    });
    if (!saved) return;

    setRepair({
      machineId: "",
      problemDescription: "",
      actions: "",
      outcome: "",
    });

  }

  async function closeProblem(logId) {
    setClosingProblemId(logId);
    setLogsError("");

    try {
      const response = await apiFetch(`/maintenance-logs/${logId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "CLOSED" }),
      });
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

  async function saveLogEdit(event) {
    event.preventDefault();
    if (!editingLog) return;
    setSavingEdit(true);
    setLogsError("");
    try {
      const response = await apiFetch(`/maintenance-logs/${editingLog.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description: editingLog.description,
          symptoms: editingLog.symptoms || null,
          repair_actions: editingLog.repair_actions || null,
          outcome: editingLog.outcome || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not update this maintenance record.");
      }
      setLogs((previous) =>
        previous.map((log) => (log.id === data.id ? data : log))
      );
      setEditingLog(null);
    } catch (err) {
      setLogsError(err.message || "Could not connect to the backend.");
    } finally {
      setSavingEdit(false);
    }
  }

  async function deleteLog(log) {
    if (!window.confirm("Archive this maintenance record? It will be removed from AI search.")) {
      return;
    }
    setLogsError("");
    try {
      const response = await apiFetch(`/maintenance-logs/${log.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("Could not delete this maintenance record.");
      }
      setLogs((previous) => previous.filter((item) => item.id !== log.id));
      if (editingLog?.id === log.id) setEditingLog(null);
    } catch (err) {
      setLogsError(err.message || "Could not connect to the backend.");
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
        {onRegister && (
          <button
            type="button"
            className="maintenance-register-button"
            onClick={onRegister}
          >
            + Register a Machine
          </button>
        )}
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
              {editingLog?.id === log.id ? (
                <form className="maintenance-edit-form" onSubmit={saveLogEdit}>
                  <strong>{machineName(log.machine_id)} · {log.recorded_on}</strong>
                  {log.record_type === "problem" && (
                    <label>
                      Symptoms
                      <textarea
                        required
                        value={editingLog.symptoms ?? ""}
                        onChange={(event) =>
                          setEditingLog((current) => ({
                            ...current,
                            symptoms: event.target.value,
                          }))
                        }
                      />
                    </label>
                  )}
                  <label>
                    Description
                    <textarea
                      required
                      value={editingLog.description ?? ""}
                      onChange={(event) =>
                        setEditingLog((current) => ({
                          ...current,
                          description: event.target.value,
                        }))
                      }
                    />
                  </label>
                  {log.record_type === "repair" && (
                    <>
                      <label>
                        Repair actions
                        <textarea
                          required
                          value={editingLog.repair_actions ?? ""}
                          onChange={(event) =>
                            setEditingLog((current) => ({
                              ...current,
                              repair_actions: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label>
                        Outcome
                        <textarea
                          required
                          value={editingLog.outcome ?? ""}
                          onChange={(event) =>
                            setEditingLog((current) => ({
                              ...current,
                              outcome: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </>
                  )}
                  <div className="maintenance-record-actions">
                    <button type="submit" disabled={savingEdit}>
                      {savingEdit ? "Saving..." : "Save changes"}
                    </button>
                    <button type="button" onClick={() => setEditingLog(null)}>
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <div>
                    <strong>{machineName(log.machine_id)}</strong>
                    <p>{log.recorded_on}</p>
                    {log.symptoms && <p>Symptoms: {log.symptoms}</p>}
                    {log.description && <p>{log.description}</p>}
                    {log.repair_actions && <p>Repair: {log.repair_actions}</p>}
                    {log.outcome && <p>Outcome: {log.outcome}</p>}
                  </div>
                  <div className="maintenance-record-actions">
                    {log.record_type === "problem" && (
                      <>
                        <span
                          className={`problem-status ${log.status === "CLOSED" ? "closed" : "open"}`}
                        >
                          {log.status === "CLOSED" ? "Closed" : "Open"}
                        </span>
                        {log.status !== "CLOSED" && (
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
                    <button type="button" onClick={() => setEditingLog({ ...log })}>
                      Edit
                    </button>
                    {isAdmin && (
                      <button type="button" onClick={() => deleteLog(log)}>
                        Delete
                      </button>
                    )}
                  </div>
                </>
              )}
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
              <MachineHierarchySelector
                idPrefix="daily-log"
                facilities={facilities}
                systems={systems}
                locations={locations}
                machines={machines}
                machinesLoading={machinesLoading}
                machineId={daily.machineId}
                onMachineChange={(value) =>
                  updateField(setDaily, "machineId", value)
                }
              />

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
              <MachineHierarchySelector
                idPrefix="problem-log"
                facilities={facilities}
                systems={systems}
                locations={locations}
                machines={machines}
                machinesLoading={machinesLoading}
                machineId={problem.machineId}
                onMachineChange={(value) =>
                  updateField(setProblem, "machineId", value)
                }
              />

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
              <MachineHierarchySelector
                idPrefix="repair-log"
                facilities={facilities}
                systems={systems}
                locations={locations}
                machines={machines}
                machinesLoading={machinesLoading}
                machineId={repair.machineId}
                onMachineChange={(value) =>
                  updateField(setRepair, "machineId", value)
                }
              />

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
        refresh. Upload technical PDFs from the Manuals page.
      </p>
    </div>
  );
}

export default MaintenanceLogsPage;