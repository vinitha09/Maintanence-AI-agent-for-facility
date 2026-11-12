import { useMemo, useState } from "react";
import "./RegisterMachine.css";
import { apiFetch, responseError } from "../../shared/api";

export default function RegisterMachine({
  onRegistered,
  onCancel,
  facilities = [],
  systems = [],
  locations = [],
}) {
  const [form, setForm] = useState({
    facility_id: "",
    functional_system_id: "",
    physical_location_id: "",
    machine_name: "",
    machine_code: "",
    description: "",
    status: "ACTIVE",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const facilitySystems = useMemo(
    () => systems.filter((item) => String(item.facility_id) === form.facility_id),
    [systems, form.facility_id]
  );
  const facilityLocations = useMemo(
    () => locations.filter((item) => String(item.facility_id) === form.facility_id),
    [locations, form.facility_id]
  );

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((previous) => ({
      ...previous,
      [name]: value,
      ...(name === "facility_id"
        ? { functional_system_id: "", physical_location_id: "" }
        : {}),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      const response = await apiFetch("/machines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          facility_id: Number(form.facility_id),
          functional_system_id: form.functional_system_id
            ? Number(form.functional_system_id)
            : null,
          physical_location_id: form.physical_location_id
            ? Number(form.physical_location_id)
            : null,
          machine_name: form.machine_name,
          machine_code: form.machine_code,
          description: form.description || null,
          status: form.status,
        }),
      });
      if (!response.ok) {
        throw await responseError(response, "Could not register the machine.");
      }
      const data = await response.json();
      setSuccess("Machine registered successfully.");
      window.setTimeout(() => onRegistered(data), 700);
    } catch (requestError) {
      setError(requestError.message || "Could not connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-content register-page">
      <div className="register-card">
        <button type="button" className="back-button" onClick={onCancel}>
          <span aria-hidden="true">←</span> Back to Dashboard
        </button>
        <h1>Register a Machine</h1>
        <p className="register-description">
          Register one machine record and link it to both facility hierarchies.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <label>
              Facility *
              <select
                name="facility_id"
                value={form.facility_id}
                onChange={handleChange}
                required
              >
                <option value="">Select a facility</option>
                {facilities.map((facility) => (
                  <option key={facility.id} value={facility.id}>{facility.name}</option>
                ))}
              </select>
            </label>
            <label>
              Machine name *
              <input
                name="machine_name"
                value={form.machine_name}
                onChange={handleChange}
                placeholder="e.g. Vacuum Pump 01"
                maxLength={150}
                required
              />
            </label>
            <label>
              Machine code *
              <input
                name="machine_code"
                value={form.machine_code}
                onChange={handleChange}
                placeholder="e.g. VP-001"
                maxLength={80}
                required
              />
            </label>
            <label>
              Functional system
              <select
                name="functional_system_id"
                value={form.functional_system_id}
                onChange={handleChange}
                disabled={!form.facility_id}
              >
                <option value="">Not assigned</option>
                {facilitySystems.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label>
              Physical location
              <select
                name="physical_location_id"
                value={form.physical_location_id}
                onChange={handleChange}
                disabled={!form.facility_id}
              >
                <option value="">Not assigned</option>
                {facilityLocations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.location_type}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select name="status" value={form.status} onChange={handleChange}>
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
                <option value="MAINTENANCE">Under maintenance</option>
              </select>
            </label>
            <label className="full-width">
              Description
              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                rows={3}
                maxLength={4000}
              />
            </label>
          </div>
          {error && <p className="register-error" role="alert">{error}</p>}
          {success && <p role="status">{success}</p>}
          <button type="submit" className="register-submit" disabled={loading || facilities.length === 0}>
            {loading ? "Registering..." : "Register Machine"}
          </button>
          {facilities.length === 0 && (
            <p>Create an organization and facility before registering machines.</p>
          )}
        </form>
      </div>
    </section>
  );
}
