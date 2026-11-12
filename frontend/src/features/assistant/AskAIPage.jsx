import { useState } from "react";
import "./AskAIPage.css";

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

export default function AskAIPage({
  onBack,
  question,
  setQuestion,
  answer,
  streaming,
  sources,
  loading,
  error,
  onAsk,
  machines,
  facilities,
  systems,
  locations,
  machinesLoading,
  scopeType,
  setScopeType,
  scopeId,
  setScopeId,
}) {
  const [activeTab, setActiveTab] = useState("location");
  const [selectedFunctionalSystemId, setSelectedFunctionalSystemId] =
    useState("");
  const [physicalLocationId, setPhysicalLocationId] = useState("");
  const [selectedMachineId, setSelectedMachineId] = useState("");

  const selectableItems =
    scopeType === "machine"
      ? machines.map((item) => ({
          id: item.id,
          name: item.machine_name ?? item.name,
          detail: item.machine_code ?? item.machine_type,
        }))
      : scopeType === "functional_system"
        ? systems.map((item) => ({
            id: item.id,
            name: item.name,
            detail: "Functional system",
          }))
        : scopeType === "physical_location"
          ? locations.map((item) => ({
              id: item.id,
              name: item.name,
              detail: item.location_type,
            }))
          : facilities.map((item) => ({
              id: item.id,
              name: item.name,
              detail: "Facility",
            }));

  const scopeLabel = {
    machine: "machine name",
    functional_system: "functional system",
    physical_location: "physical location",
    facility: "facility",
  }[scopeType];
  const scopePlural = {
    machine: "machine names",
    functional_system: "functional systems",
    physical_location: "physical locations",
    facility: "facilities",
  }[scopeType];
  const selectedSystem = systems.find(
    (system) => String(system.id) === String(scopeId)
  );
  const usesLocationAndMachineSteps =
    (scopeType === "functional_system" || scopeType === "facility") &&
    Boolean(scopeId);
  const selectedFacilityId =
    scopeType === "functional_system" ? selectedSystem?.facility_id : scopeId;
  const facilitySystems = systems.filter(
    (system) => String(system.facility_id) === String(selectedFacilityId)
  );
  const activeSystemId =
    scopeType === "functional_system"
      ? selectedSystem?.id
      : selectedFunctionalSystemId;
  const activeSystem = systems.find(
    (system) => String(system.id) === String(activeSystemId)
  );
  const functionalSystemIds = activeSystem
    ? getDescendantIds(systems, activeSystem.id)
    : new Set();
  const systemLocations = locations.filter(
    (location) =>
      selectedFacilityId &&
      String(location.facility_id) === String(selectedFacilityId)
  );
  const locationIds = physicalLocationId
    ? getDescendantIds(systemLocations, physicalLocationId)
    : new Set();
  const machinesInSelectedScope = usesLocationAndMachineSteps
    ? machines.filter(
        (machine) =>
          String(machine.facility_id) === String(selectedFacilityId) &&
          functionalSystemIds.has(String(machine.functional_system_id)) &&
          locationIds.has(String(machine.physical_location_id))
      )
    : [];

  return (
    <div className="page-content ask-ai-page">
      <button className="page-back-button" onClick={onBack}>
        <span aria-hidden="true">←</span>
        Back to Dashboard
      </button>

      <div className="page-heading">
        <p className="eyebrow">AI MAINTENANCE ASSISTANT</p>
        <h1>Ask AI</h1>
        <p className="page-description">
          Get machine-specific answers from maintenance history and technical
          manuals.
        </p>
      </div>

      <section className="ask-page-card">
        <div className="section-heading">
          <div>
            <h2>What problem are you experiencing?</h2>
            <p>
              Select a machine, functional system, physical location, or
              facility to search its maintenance history and technical
              documentation.
            </p>
          </div>
          <span className="ai-badge">AI ASSISTED</span>
        </div>

        <div className="machine-selection">
          <label htmlFor="scope-type">Question scope</label>
          <select
            id="scope-type"
            className="dropdown"
            value={scopeType}
            onChange={(event) => {
              setScopeType(event.target.value);
              setScopeId("");
              setPhysicalLocationId("");
              setSelectedMachineId("");
              setActiveTab("location");
            }}
          >
            <option value="machine">Individual machine</option>
            <option value="functional_system">Functional system</option>
            <option value="physical_location">Physical location</option>
            <option value="facility">Facility</option>
          </select>

          <label htmlFor="scope-item">
            {scopeType === "machine"
              ? "Select machine name"
              : `Select ${scopeLabel}`}
          </label>
          <select
            id="scope-item"
            className="dropdown"
            value={scopeId}
            onChange={(event) => {
              setScopeId(event.target.value);
              setSelectedFunctionalSystemId("");
              setPhysicalLocationId("");
              setSelectedMachineId("");
              setActiveTab(
                scopeType === "facility" ? "system" : "location"
              );
            }}
            disabled={machinesLoading}
          >
            <option value="">
              {machinesLoading
                ? "Loading..."
                : selectableItems.length
                  ? `Choose a ${scopeLabel}`
                  : `No ${scopePlural} available`}
            </option>
            {selectableItems.map((item) => (
              <option key={item.id} value={String(item.id)}>
                {item.name}
                {item.detail ? ` — ${item.detail}` : ""}
              </option>
            ))}
          </select>
        </div>

        {usesLocationAndMachineSteps && (
          <>
            <div
              className="ask-ai-tabs"
              role="tablist"
              aria-label="Select a functional system, physical location, and machine"
            >
              {scopeType === "facility" && (
                <button
                  id="ask-ai-tab-system"
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "system"}
                  aria-controls="ask-ai-panel-system"
                  className={activeTab === "system" ? "active" : ""}
                  onClick={() => setActiveTab("system")}
                >
                  1. Functional system
                </button>
              )}
              <button
                id="ask-ai-tab-location"
                type="button"
                role="tab"
                aria-selected={activeTab === "location"}
                aria-controls="ask-ai-panel-location"
                className={activeTab === "location" ? "active" : ""}
                disabled={
                  scopeType === "facility" && !selectedFunctionalSystemId
                }
                onClick={() => setActiveTab("location")}
              >
                {scopeType === "facility"
                  ? "2. Physical location"
                  : "1. Physical location"}
              </button>
              <button
                id="ask-ai-tab-machine"
                type="button"
                role="tab"
                aria-selected={activeTab === "machine"}
                aria-controls="ask-ai-panel-machine"
                className={activeTab === "machine" ? "active" : ""}
                disabled={!physicalLocationId}
                onClick={() => setActiveTab("machine")}
              >
                {scopeType === "facility"
                  ? "3. Select machine & ask AI"
                  : "2. Select machine & ask AI"}
              </button>
            </div>

            {scopeType === "facility" && activeTab === "system" ? (
              <section
                id="ask-ai-panel-system"
                role="tabpanel"
                aria-labelledby="ask-ai-tab-system"
                className="ask-ai-step-panel"
              >
                <h3>Select a functional system</h3>
                <label htmlFor="facility-functional-system">
                  Functional system
                </label>
                <select
                  id="facility-functional-system"
                  className="dropdown"
                  value={selectedFunctionalSystemId}
                  onChange={(event) => {
                    setSelectedFunctionalSystemId(event.target.value);
                    setPhysicalLocationId("");
                    setSelectedMachineId("");
                  }}
                  disabled={machinesLoading}
                >
                  <option value="">
                    {machinesLoading
                      ? "Loading functional systems..."
                      : facilitySystems.length
                        ? "Choose a functional system"
                        : "No functional systems in this facility"}
                  </option>
                  {facilitySystems.map((system) => (
                    <option key={system.id} value={String(system.id)}>
                      {system.name}
                    </option>
                  ))}
                </select>
                <button
                  className="ask-button ask-ai-next-button"
                  type="button"
                  disabled={!selectedFunctionalSystemId}
                  onClick={() => setActiveTab("location")}
                >
                  Continue to physical location
                </button>
              </section>
            ) : activeTab === "location" ? (
              <section
                id="ask-ai-panel-location"
                role="tabpanel"
                aria-labelledby="ask-ai-tab-location"
                className="ask-ai-step-panel"
              >
                <h3>Select a physical location</h3>
                <p>
                  Choose the location where the machine is installed. Machines
                  in this location and its sublocations will be available next.
                </p>
                <label htmlFor="functional-system-location">
                  Physical location
                </label>
                <select
                  id="functional-system-location"
                  className="dropdown"
                  value={physicalLocationId}
                  onChange={(event) => {
                    setPhysicalLocationId(event.target.value);
                    setSelectedMachineId("");
                  }}
                  disabled={machinesLoading}
                >
                  <option value="">
                    {machinesLoading
                      ? "Loading locations..."
                      : systemLocations.length
                        ? "Choose a physical location"
                        : "No physical locations in this facility"}
                  </option>
                  {systemLocations.map((location) => (
                    <option key={location.id} value={String(location.id)}>
                      {location.name} — {location.location_type}
                    </option>
                  ))}
                </select>
                <button
                  className="ask-button ask-ai-next-button"
                  type="button"
                  disabled={!physicalLocationId}
                  onClick={() => setActiveTab("machine")}
                >
                  Continue to machine selection
                </button>
              </section>
            ) : (
              <section
                id="ask-ai-panel-machine"
                role="tabpanel"
                aria-labelledby="ask-ai-tab-machine"
                className="ask-ai-step-panel"
              >
                <h3>Select a machine</h3>
                <label htmlFor="functional-system-machine">
                  Machine name
                </label>
                <select
                  id="functional-system-machine"
                  className="dropdown"
                  value={selectedMachineId}
                  onChange={(event) =>
                    setSelectedMachineId(event.target.value)
                  }
                  disabled={machinesLoading}
                >
                  <option value="">
                    {machinesLoading
                      ? "Loading machines..."
                      : machinesInSelectedScope.length
                        ? "Choose a machine"
                        : "No machines match this system and location"}
                  </option>
                  {machinesInSelectedScope.map((machine) => (
                    <option key={machine.id} value={String(machine.id)}>
                      {machine.machine_name ?? machine.name}
                      {machine.machine_code
                        ? ` — ${machine.machine_code}`
                        : ""}
                    </option>
                  ))}
                </select>
                {selectedMachineId && (
                  <form
                    className="ask-ai-machine-question"
                    onSubmit={(event) =>
                      onAsk(event, {
                        scopeType: "machine",
                        scopeId: selectedMachineId,
                      })
                    }
                  >
                    <label className="ask-question-label" htmlFor="question">
                      Describe the problem
                    </label>
                    <textarea
                      id="question"
                      value={question}
                      onChange={(event) => setQuestion(event.target.value)}
                      placeholder="Example: The conveyor motor is overheating. What should I check in the manual?"
                    />
                    <button
                      className="ask-button"
                      type="submit"
                      disabled={loading}
                    >
                      {loading
                        ? "Searching maintenance logs and manuals..."
                        : "Ask Maintenance AI →"}
                    </button>
                  </form>
                )}
              </section>
            )}
          </>
        )}

        {!usesLocationAndMachineSteps && (
          <form onSubmit={onAsk}>
            <label className="ask-question-label" htmlFor="question">
              Describe the problem
            </label>
            <textarea
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Example: The conveyor motor is overheating. What should I check in the manual?"
            />
            <button className="ask-button" type="submit" disabled={loading}>
              {loading
                ? "Searching maintenance logs and manuals..."
                : "Ask Maintenance AI →"}
            </button>
          </form>
        )}

        {error && <p className="error-message">{error}</p>}

        {(loading || answer) && (
          <section className="answer-panel">
            {answer ? (
              <>
                <h3>Maintenance assistant response</h3>
                <p
                  className={`answer-text${streaming ? " answer-streaming" : ""}`}
                  aria-live="polite"
                  aria-busy={streaming}
                >
                  {answer}
                </p>
              </>
            ) : (
              <p className="thinking-status" role="status" aria-live="polite">
                <span className="thinking-indicator" aria-hidden="true" />
                Thinking...
              </p>
            )}

            {answer && sources.length > 0 && (
              <div>
                <h4>Sources</h4>
                <ul>
                  {sources.map((source, index) => (
                    <li
                      key={
                        source.source_type === "maintenance_log"
                          ? `log-${source.log_id}`
                          : `manual-${source.filename}-${source.page_number}-${index}`
                      }
                    >
                      {source.source_type === "maintenance_log"
                        ? `Maintenance Log #${source.log_id} — ${source.record_type} · ${source.recorded_on}`
                        : `${source.filename} — Page ${source.page_number}`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        <p className="disclaimer">
          AI-generated guidance is not a verified repair instruction. Follow
          approved safety procedures and consult a qualified technician.
        </p>
      </section>
    </div>
  );
}
