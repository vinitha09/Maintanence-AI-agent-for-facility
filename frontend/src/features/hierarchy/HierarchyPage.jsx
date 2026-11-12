import { useState } from "react";
import { apiFetch, responseError } from "../../shared/api";
import "./HierarchyPage.css";

function HierarchyNodes({ nodes, allNodes, machines, machineField }) {
  if (!nodes.length) return null;

  return (
    <ul className="hierarchy-tree">
      {nodes.map((node) => {
        const children = allNodes.filter(
          (item) => item.parent_id === node.id
        );
        const assignedMachines = machines.filter(
          (machine) => machine[machineField] === node.id
        );

        return (
          <li key={node.id}>
            <div className="hierarchy-node">
              <strong>{node.name}</strong>
              {node.location_type && (
                <span className="hierarchy-node-type">
                  {node.location_type}
                </span>
              )}
            </div>
            {assignedMachines.length > 0 && (
              <ul className="hierarchy-machine-list">
                {assignedMachines.map((machine) => (
                  <li key={machine.id}>
                    {machine.machine_name}
                    {machine.machine_code ? ` · ${machine.machine_code}` : ""}
                  </li>
                ))}
              </ul>
            )}
            <HierarchyNodes
              nodes={children}
              allNodes={allNodes}
              machines={machines}
              machineField={machineField}
            />
          </li>
        );
      })}
    </ul>
  );
}

export default function HierarchyPage({
  organizations,
  facilities,
  machines,
  systems,
  locations,
  isAdmin,
  onBack,
  onChanged,
}) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [systemFacilityId, setSystemFacilityId] = useState("");
  const [locationFacilityId, setLocationFacilityId] = useState("");
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(null);

  async function create(path, payload) {
    setError("");
    setSaving(true);
    try {
      const response = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw await responseError(response, "Could not save this hierarchy item.");
      }
      await onChanged();
      return true;
    } catch (requestError) {
      setError(requestError.message || "Could not connect to the server.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function submitOrganization(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    if (await create("/organizations", { name: form.get("name") })) {
      formElement.reset();
    }
  }

  async function submitFacility(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    if (
      await create("/facilities", {
        organization_id: Number(form.get("organization_id")),
        name: form.get("name"),
      })
    ) {
      formElement.reset();
    }
  }

  async function submitSystem(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    if (
      await create("/hierarchy/functional-systems", {
        facility_id: Number(form.get("facility_id")),
        parent_id: form.get("parent_id") ? Number(form.get("parent_id")) : null,
        name: form.get("name"),
        description: form.get("description") || null,
      })
    ) {
      formElement.reset();
      setSystemFacilityId("");
    }
  }

  async function submitLocation(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    if (
      await create("/hierarchy/physical-locations", {
        facility_id: Number(form.get("facility_id")),
        parent_id: form.get("parent_id") ? Number(form.get("parent_id")) : null,
        name: form.get("name"),
        location_type: form.get("location_type"),
      })
    ) {
      formElement.reset();
      setLocationFacilityId("");
    }
  }

  return (
    <section className="page-content hierarchy-page">
      <button className="page-back-button" onClick={onBack}>
        <span aria-hidden="true">←</span> Back to Dashboard
      </button>
      <div className="page-heading">
        <p className="eyebrow">{isAdmin ? "ADMINISTRATION" : "FACILITY STRUCTURE"}</p>
        <h1>Organization &amp; facility hierarchy</h1>
        <p className="page-description">
          {isAdmin
            ? "Create facilities and organize equipment by function and physical location."
            : "View facilities and equipment organized by function and physical location."}
        </p>
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      {isAdmin && <div className="hierarchy-grid">
        <form className="content-card hierarchy-form" onSubmit={submitOrganization}>
          <h2>Organization</h2>
          <label>Name<input name="name" required maxLength={150} /></label>
          <button disabled={saving}>Add organization</button>
        </form>
        <form className="content-card hierarchy-form" onSubmit={submitFacility}>
          <h2>Facility</h2>
          <label>
            Organization
            <select name="organization_id" required defaultValue="">
              <option value="" disabled>Select organization</option>
              {organizations.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>Name<input name="name" required maxLength={150} /></label>
          <button disabled={saving || organizations.length === 0}>Add facility</button>
        </form>
        <form className="content-card hierarchy-form" onSubmit={submitSystem}>
          <h2>Functional system</h2>
          <label>
            Facility
            <select
              name="facility_id"
              required
              value={systemFacilityId}
              onChange={(event) => setSystemFacilityId(event.target.value)}
            >
              <option value="" disabled>Select facility</option>
              {facilities.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>
            Parent system (optional)
            <select name="parent_id" defaultValue="">
              <option value="">Top-level system</option>
              {systems.filter((item) => String(item.facility_id) === systemFacilityId).map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>Name<input name="name" required maxLength={150} /></label>
          <label>Description<textarea name="description" rows={2} /></label>
          <button disabled={saving || facilities.length === 0}>Add system</button>
        </form>
        <form className="content-card hierarchy-form" onSubmit={submitLocation}>
          <h2>Physical location</h2>
          <label>
            Facility
            <select
              name="facility_id"
              required
              value={locationFacilityId}
              onChange={(event) => setLocationFacilityId(event.target.value)}
            >
              <option value="" disabled>Select facility</option>
              {facilities.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>
            Parent location (optional)
            <select name="parent_id" defaultValue="">
              <option value="">Top-level location</option>
              {locations.filter((item) => String(item.facility_id) === locationFacilityId).map((item) => (
                <option key={item.id} value={item.id}>{item.name} · {item.location_type}</option>
              ))}
            </select>
          </label>
          <label>
            Location type
            <select name="location_type" required>
              <option value="BUILDING">Building</option>
              <option value="FLOOR">Floor</option>
              <option value="ROOM">Room</option>
              <option value="AREA">Area</option>
            </select>
          </label>
          <label>Name<input name="name" required maxLength={150} /></label>
          <button disabled={saving || facilities.length === 0}>Add location</button>
        </form>
      </div>}
      <section className="content-card hierarchy-overview">
        <h2>Current structure</h2>
        <p>
          {organizations.length} organizations · {facilities.length} facilities
          {" · "}{systems.length} systems · {locations.length} locations
        </p>
        {organizations.length === 0 ? (
          <p className="hierarchy-empty">
            Add an organization to see the hierarchy diagram.
          </p>
        ) : (
          <div className="organization-flow">
            {organizations.map((organization) => {
              const organizationFacilities = facilities.filter(
                (facility) => facility.organization_id === organization.id
              );
              const isSelected =
                selectedOrganizationId === organization.id;

              return (
                <section
                  className={`organization-flow-group${isSelected ? " selected" : ""}`}
                  key={organization.id}
                >
                  <button
                    className="organization-flow-node"
                    type="button"
                    aria-expanded={isSelected}
                    aria-controls={`organization-flow-${organization.id}`}
                    onClick={() =>
                      setSelectedOrganizationId(
                        isSelected ? null : organization.id
                      )
                    }
                  >
                    <span>Organization</span>
                    <strong>{organization.name}</strong>
                    <span aria-hidden="true" className="organization-flow-toggle">
                      {isSelected ? "−" : "+"}
                    </span>
                  </button>
                  {isSelected && (
                    <div
                      className="organization-flow-details"
                      id={`organization-flow-${organization.id}`}
                    >
                      {organizationFacilities.length === 0 ? (
                        <p className="hierarchy-empty">
                          No facilities have been added to this organization.
                        </p>
                      ) : (
                        <div className="facility-flow-list">
                          {organizationFacilities.map((facility) => (
                            <article
                              className="facility-flow-card"
                              key={facility.id}
                            >
                              <div className="facility-flow-node">
                                <span>Facility</span>
                                <strong>{facility.name}</strong>
                              </div>
                              <div className="facility-flow-branches">
                                <section className="hierarchy-branch">
                                  <h3>Functional systems</h3>
                                  <HierarchyNodes
                                    nodes={systems.filter(
                                      (item) =>
                                        item.facility_id === facility.id &&
                                        item.parent_id == null
                                    )}
                                    allNodes={systems}
                                    machines={machines}
                                    machineField="functional_system_id"
                                  />
                                  {!systems.some(
                                    (item) => item.facility_id === facility.id
                                  ) && (
                                    <p className="hierarchy-empty">
                                      No functional systems
                                    </p>
                                  )}
                                </section>
                                <section className="hierarchy-branch">
                                  <h3>Physical locations</h3>
                                  <HierarchyNodes
                                    nodes={locations.filter(
                                      (item) =>
                                        item.facility_id === facility.id &&
                                        item.parent_id == null
                                    )}
                                    allNodes={locations}
                                    machines={machines}
                                    machineField="physical_location_id"
                                  />
                                  {!locations.some(
                                    (item) => item.facility_id === facility.id
                                  ) && (
                                    <p className="hierarchy-empty">
                                      No physical locations
                                    </p>
                                  )}
                                </section>
                              </div>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </section>
    </section>
  );
}
