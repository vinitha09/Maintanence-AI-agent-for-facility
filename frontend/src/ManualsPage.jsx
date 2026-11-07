import { useState } from "react";
import "./ManualsPage.css";

const API_URL = "http://127.0.0.1:8000";

export default function ManualsPage({
  onBack,
  machines = [],
  loadingMachines,
}) {
  const [machineId, setMachineId] = useState("");
  const [manuals, setManuals] = useState([]);
  const [loadingManuals, setLoadingManuals] = useState(false);
  const [error, setError] = useState("");
 

  async function loadManuals(id) {
    setMachineId(id);
    setManuals([]);
    setError("");

    if (!id) return;

    setLoadingManuals(true);

    try {
      const response = await fetch(`${API_URL}/machines/${id}/manuals`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load manuals.");
      }

      setManuals(
        Array.isArray(data) ? data : data?.manuals ?? []
      );
    } catch (err) {
      setError(err.message || "Could not load manuals.");
    } finally {
      setLoadingManuals(false);
    }
  }

  return (
    <div className="page-content manuals-page">
      <button className="page-back-button" onClick={onBack}>
        <span aria-hidden="true">←</span>
        Back to Dashboard
      </button>

      <div className="page-heading">
        <div>
          <p className="eyebrow">DOCUMENT LIBRARY</p>
          <h1>Machine Manuals</h1>
          <p className="page-description">
            Browse technical documentation linked to your registered machines.
          </p>
        </div>
      </div>

      <section className="content-card manuals-selector">
        <label htmlFor="manual-machine">Select a machine</label>

        <select
          id="manual-machine"
          value={machineId}
          onChange={(event) => loadManuals(event.target.value)}
          disabled={loadingMachines}
        >
          <option value="">
            {loadingMachines
              ? "Loading machines..."
              : machines.length
                ? "Choose a machine"
                : "No machines available"}
          </option>

          {machines.map((machine) => (
            <option key={machine.id} value={String(machine.id)}>
              {machine.name}
              {machine.machine_type ? ` — ${machine.machine_type}` : ""}
            </option>
          ))}
        </select>
      </section>

      {error && <p className="error-message">{error}</p>}

      <section className="content-card manuals-list">
        <div className="manuals-list-heading">
          <div>
            <h2>Available Manuals</h2>
            <p className="page-description">
              Documents associated with the selected machine.
            </p>
          </div>

          <span className="document-count">
            {manuals.length} {manuals.length === 1 ? "document" : "documents"}
          </span>
        </div>

        {loadingManuals ? (
          <p className="manuals-empty">Loading manuals...</p>
        ) : !machineId ? (
          <p className="manuals-empty">
            Select a machine above to view its manuals.
          </p>
        ) : manuals.length === 0 && !error ? (
          <p className="manuals-empty">
            No manuals are linked to this machine yet.
          </p>
        ) : (
          manuals.map((manual) => (
            <article className="manual-item" key={manual.id}>
              <div className="manual-file-icon">
                <span>PDF</span>
              </div>

              <div className="manual-file-info">
                <h3>{manual.filename}</h3>
                <p>Technical documentation · PDF</p>
              </div>

              {manual.file_url && (
                <a
                  className="manual-open-button"
                  href={`${API_URL}${manual.file_url}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open PDF
                  <span aria-hidden="true">↗</span>
                </a>
              )}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
