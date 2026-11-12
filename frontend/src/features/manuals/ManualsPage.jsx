import { useState } from "react";
import "./ManualsPage.css";
import { apiFetch, responseError } from "../../shared/api";

export default function ManualsPage({
  onBack,
  machines = [],
  loadingMachines,
  isAdmin,
}) {
  const [machineId, setMachineId] = useState("");
  const [manuals, setManuals] = useState([]);
  const [loadingManuals, setLoadingManuals] = useState(false);
  const [error, setError] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  async function loadManuals(id) {
    setMachineId(id);
    setManuals([]);
    setError("");

    if (!id) return;

    setLoadingManuals(true);

    try {
      const response = await apiFetch(`/machines/${id}/manuals`);
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

  async function uploadManual(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (!machineId || !file) return;
    setUploading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("machine_id", machineId);
      body.append("file", file);
      const response = await apiFetch("/manuals/upload", {
        method: "POST",
        body,
      });
      if (!response.ok) {
        throw await responseError(response, "Could not upload this manual.");
      }
      setFile(null);
      formElement.reset();
      await loadManuals(machineId);
    } catch (requestError) {
      setError(requestError.message || "Could not upload this manual.");
    } finally {
      setUploading(false);
    }
  }

  async function deleteManual(manual) {
    if (!window.confirm(`Delete the manual "${manual.filename}"?`)) return;
    setError("");
    try {
      const response = await apiFetch(`/manuals/${manual.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw await responseError(response, "Could not delete this manual.");
      }
      setManuals((previous) => previous.filter((item) => item.id !== manual.id));
    } catch (requestError) {
      setError(requestError.message || "Could not delete this manual.");
    }
  }

  async function openManual(manual) {
    const newWindow = window.open("", "_blank");
    if (!newWindow) {
      setError("Allow pop-ups to open this manual.");
      return;
    }

    try {
      const response = await apiFetch(manual.file_url);
      if (!response.ok) {
        throw await responseError(response, "Could not open this manual.");
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      newWindow.location.href = objectUrl;
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (requestError) {
      newWindow.close();
      setError(requestError.message || "Could not open this manual.");
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

      {machineId && isAdmin && (
        <form className="content-card manuals-selector" onSubmit={uploadManual}>
          <label htmlFor="manual-upload">Upload a PDF manual</label>
          <input
            id="manual-upload"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
          <button type="submit" disabled={uploading || !file}>
            {uploading ? "Uploading and indexing..." : "Upload manual"}
          </button>
        </form>
      )}

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
                <button
                  type="button"
                  className="manual-open-button"
                  onClick={() => openManual(manual)}
                >
                  Open PDF
                  <span aria-hidden="true">↗</span>
                </button>
              )}
              {isAdmin && <button
                type="button"
                className="manual-open-button"
                onClick={() => deleteManual(manual)}
              >
                Delete
              </button>}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
