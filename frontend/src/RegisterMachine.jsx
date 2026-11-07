
import { useState } from "react";
import "./RegisterMachine.css";

const API_URL = "http://127.0.0.1:8000";

export default function RegisterMachine({ onRegistered, onCancel }) {
  const [form, setForm] = useState({
    name: "",
    machine_type: "",
    manufacturer: "",
    model_number: "",
    serial_number: "",
    address: "",
    location: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/machines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          manufacturer: form.manufacturer || null,
          model_number: form.model_number || null,
          serial_number: form.serial_number || null,
          address: form.address || null,
          location: form.location || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : "Could not register the machine."
        );
      }

      setSuccess("Machine registered successfully.");

      // Give the confirmation time to appear before returning to the machine list.
      window.setTimeout(() => onRegistered(data), 1000);
    } catch (err) {
      setError(err.message || "Could not connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-content register-page">
      <div className="register-card">
        <button
          type="button"
          className="back-button"
          onClick={onCancel}
        >
          <span aria-hidden="true">←</span>
          Back to Dashboard
        </button>

        <h1>Register a Machine</h1>
        <p className="register-description">
          Add a machine to your maintenance assistant.
          You can link its manuals after registration.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <label>
              Machine name *
              <input
                name="name"
                value={form.name}
                onChange={handleChange}
                placeholder="e.g. CNC-01"
                maxLength={100}
                required
              />
            </label>

            <label>
              Machine type *
              <input
                name="machine_type"
                value={form.machine_type}
                onChange={handleChange}
                placeholder="e.g. CNC milling machine"
                maxLength={100}
                required
              />
            </label>

            <label>
              Manufacturer
              <input
                name="manufacturer"
                value={form.manufacturer}
                onChange={handleChange}
                placeholder="e.g. Siemens"
              />
            </label>

            <label>
              Model number
              <input
                name="model_number"
                value={form.model_number}
                onChange={handleChange}
                placeholder="Enter model number"
              />
            </label>



            <label className="full-width">
              Installation location
              <input
                name="location"
                value={form.location}
                onChange={handleChange}
                placeholder="e.g. Production Line 1"
              />
            </label>
          </div>

          {error && (
            <p className="register-error" role="alert">
              {error}
            </p>
          )}

          {success && (
            <p role="status">
              {success}
            </p>
          )}

          <button
            type="submit"
            className="register-submit"
            disabled={loading}
          >
            {loading ? "Registering..." : "Register Machine"}
          </button>
        </form>
      </div>
    </section>
  );
}
