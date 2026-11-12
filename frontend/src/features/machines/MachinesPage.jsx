import { useState } from "react";
import { apiFetch, responseError } from "../../shared/api";
import "./MachinesPage.css";

export default function MachinesPage({
  machines,
  facilities,
  systems,
  locations,
  isAdmin,
  canRegister,
  onRegister,
  onChanged,
}) {
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function beginEdit(machine) {
    setEditing({
      ...machine,
      facility_id: String(machine.facility_id),
      functional_system_id: machine.functional_system_id
        ? String(machine.functional_system_id)
        : "",
      physical_location_id: machine.physical_location_id
        ? String(machine.physical_location_id)
        : "",
    });
    setError("");
  }

  function updateField(name, value) {
    setEditing((previous) => ({
      ...previous,
      [name]: value,
      ...(name === "facility_id"
        ? { functional_system_id: "", physical_location_id: "" }
        : {}),
    }));
  }

  async function saveMachine(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const response = await apiFetch(`/machines/${editing.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          facility_id: Number(editing.facility_id),
          functional_system_id: editing.functional_system_id
            ? Number(editing.functional_system_id)
            : null,
          physical_location_id: editing.physical_location_id
            ? Number(editing.physical_location_id)
            : null,
          machine_name: editing.machine_name,
          machine_code: editing.machine_code,
          description: editing.description || null,
          status: editing.status,
        }),
      });
      if (!response.ok) {
        throw await responseError(response, "Could not update this machine.");
      }
      onChanged(await response.json());
      setEditing(null);
    } catch (requestError) {
      setError(requestError.message || "Could not update this machine.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteMachine(machine) {
    if (!window.confirm(`Archive ${machine.machine_name}? Its maintenance history and manuals will be preserved.`)) {
      return;
    }
    setError("");
    try {
      const response = await apiFetch(`/machines/${machine.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw await responseError(response, "Could not delete this machine.");
      }
      onChanged({ id: machine.id, deleted: true });
    } catch (requestError) {
      setError(requestError.message || "Could not delete this machine.");
    }
  }

  const selectedSystems = systems.filter(
    (item) => String(item.facility_id) === editing?.facility_id
  );
  const selectedLocations = locations.filter(
    (item) => String(item.facility_id) === editing?.facility_id
  );

  return (
    <section className="page-content machines-page">
      <div className="page-heading machines-heading">
        <div>
          <p className="eyebrow">EQUIPMENT</p>
          <h1>Machines</h1>
          <p className="page-description">Shared machine records linked to functional and physical hierarchies.</p>
        </div>
        {canRegister && (
          <button type="button" onClick={onRegister}>Register machine</button>
        )}
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      {editing && (
        <form className="content-card machine-edit-form" onSubmit={saveMachine}>
          <h2>Edit {editing.machine_name}</h2>
          <label>
            Machine name
            <input value={editing.machine_name} onChange={(event) => updateField("machine_name", event.target.value)} required maxLength={150} />
          </label>
          <label>
            Machine code
            <input value={editing.machine_code} onChange={(event) => updateField("machine_code", event.target.value)} required maxLength={80} />
          </label>
          <label>
            Facility
            <select value={editing.facility_id} onChange={(event) => updateField("facility_id", event.target.value)} required>
              {facilities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Functional system
            <select value={editing.functional_system_id} onChange={(event) => updateField("functional_system_id", event.target.value)}>
              <option value="">Not assigned</option>
              {selectedSystems.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Physical location
            <select value={editing.physical_location_id} onChange={(event) => updateField("physical_location_id", event.target.value)}>
              <option value="">Not assigned</option>
              {selectedLocations.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.location_type}</option>)}
            </select>
          </label>
          <label>
            Status
            <select value={editing.status} onChange={(event) => updateField("status", event.target.value)}>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
              <option value="MAINTENANCE">Under maintenance</option>
            </select>
          </label>
          <label className="machine-edit-description">
            Description
            <textarea value={editing.description ?? ""} onChange={(event) => updateField("description", event.target.value)} rows={3} />
          </label>
          <div className="machine-edit-actions">
            <button type="submit" disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>
            <button type="button" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </form>
      )}
      <section className="content-card machine-directory">
        {machines.length === 0 ? (
          <p>No machines have been registered yet.</p>
        ) : machines.map((machine) => (
          <article className="machine-row" key={machine.id}>
            <div>
              <strong>{machine.machine_name}</strong>
              <p>{machine.machine_code} · {machine.status}</p>
              <small>
                {facilities.find((item) => item.id === machine.facility_id)?.name ?? "Facility"}
                {machine.functional_system_id
                  ? ` · ${systems.find((item) => item.id === machine.functional_system_id)?.name ?? "System"}`
                  : ""}
                {machine.physical_location_id
                  ? ` · ${locations.find((item) => item.id === machine.physical_location_id)?.name ?? "Location"}`
                  : ""}
              </small>
            </div>
            <button type="button" onClick={() => beginEdit(machine)}>Edit</button>
            {isAdmin && (
              <button type="button" onClick={() => deleteMachine(machine)}>Archive</button>
            )}
          </article>
        ))}
      </section>
    </section>
  );
}
