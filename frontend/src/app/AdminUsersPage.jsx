import { useCallback, useEffect, useState } from "react";
import { apiFetch, responseError } from "../shared/api";
import "./AdminUsersPage.css";

async function fetchUsers() {
  const response = await apiFetch("/admin/users");
  if (!response.ok) {
    throw await responseError(response, "Could not load user accounts.");
  }
  return response.json();
}

export default function AdminUsersPage({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [email, setEmail] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [sharedInviteCode, setSharedInviteCode] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const loadUsers = useCallback(async () => {
    try {
      setUsers(await fetchUsers());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetchUsers()
      .then((accountList) => {
        if (active) setUsers(accountList);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function updateUser(path, method = "POST", body) {
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        throw await responseError(response, "Could not update this account.");
      }
      setMessage("Account updated.");
      await loadUsers();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function inviteAdmin(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const response = await apiFetch("/admin/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!response.ok) {
        throw await responseError(response, "Could not send this invitation.");
      }
      const result = await response.json();
      setMessage(result.message);
      setEmail("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function inviteUser(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const response = await apiFetch("/admin/user-invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: userEmail }),
      });
      if (!response.ok) {
        throw await responseError(response, "Could not send this invitation.");
      }
      const result = await response.json();
      setMessage(result.message);
      setUserEmail("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createSharedInviteCode() {
    setError("");
    setMessage("");
    setSharedInviteCode("");
    try {
      const response = await apiFetch("/admin/user-invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw await responseError(response, "Could not generate an invitation code.");
      }
      const result = await response.json();
      setSharedInviteCode(result.code);
      setMessage(result.message);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function copySharedInviteCode() {
    if (!navigator.clipboard) {
      setError("Clipboard access is unavailable. Select and copy the code manually.");
      return;
    }
    try {
      await navigator.clipboard.writeText(sharedInviteCode);
      setMessage("Recruiter code copied.");
    } catch (requestError) {
      setError(`Could not copy the recruiter code: ${requestError.message}`);
    }
  }

  return (
    <section className="page-section admin-users-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1>User Management</h1>
          <p>Review registrations and manage account access.</p>
        </div>
      </header>

      <form className="form-card" onSubmit={inviteAdmin}>
        <h2>Invite an administrator</h2>
        <div className="form-row">
          <label>
            Administrator email
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button className="primary-button" type="submit">
            Send invitation
          </button>
        </div>
      </form>

      <form className="form-card" onSubmit={inviteUser}>
        <h2>Invite a user</h2>
        <p>
          Send an invite to one email address, or generate a shared code that
          multiple recruiters can use without waiting for approval. Shared
          codes expire after 7 days.
        </p>
        <div className="form-row">
          <label>
            User email
            <input
              type="email"
              required
              value={userEmail}
              onChange={(event) => setUserEmail(event.target.value)}
            />
          </label>
          <button className="primary-button" type="submit">
            Send invitation
          </button>
        </div>
        <div className="form-row">
          <button type="button" onClick={createSharedInviteCode}>
            Generate shared recruiter code
          </button>
        </div>
        {sharedInviteCode && (
          <>
            <label>
              Shared recruiter code — share privately; reusable for 7 days
              <input readOnly value={sharedInviteCode} />
            </label>
            <button type="button" onClick={copySharedInviteCode}>
              Copy recruiter code
            </button>
          </>
        )}
      </form>

      {error && <p className="error-message" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <div className="data-card">
        <h2>Registered accounts</h2>
        {loading ? (
          <p>Loading accounts…</p>
        ) : users.length === 0 ? (
          <p>No accounts are available.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((account) => (
                  <tr key={account.id}>
                    <td>{account.name}</td>
                    <td>{account.email}</td>
                    <td>{account.role}</td>
                    <td>
                      {!account.is_verified
                        ? "Email not verified"
                        : !account.is_active
                          ? "Suspended"
                        : account.is_invited && !account.is_approved
                          ? "Invited — access granted"
                        : !account.is_approved
                          ? "Awaiting approval"
                          : account.is_active
                            ? "Active"
                            : "Suspended"}
                    </td>
                    <td className="admin-user-actions">
                      {account.role === "USER" &&
                        account.is_verified &&
                        !account.is_approved &&
                        !account.is_invited && (
                          <>
                            <button
                              type="button"
                              onClick={() =>
                                updateUser(`/admin/users/${account.id}/approve`)
                              }
                            >
                              Approve
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                updateUser(`/admin/users/${account.id}/reject`)
                              }
                            >
                              Reject
                            </button>
                          </>
                        )}
                      {(account.is_approved || account.is_invited) && (
                        <button
                          type="button"
                          onClick={() =>
                            updateUser(
                              `/admin/users/${account.id}/status`,
                              "PATCH",
                              { is_active: !account.is_active }
                            )
                          }
                        >
                          {account.is_active ? "Suspend" : "Reactivate"}
                        </button>
                      )}
                      {account.id !== currentUser.id && (
                        <button
                          type="button"
                          onClick={() =>
                            updateUser(`/admin/users/${account.id}`, "DELETE")
                          }
                        >
                          Delete profile
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
