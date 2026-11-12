import { useEffect, useRef, useState } from "react";
import { apiFetch, responseError } from "../shared/api";
import "./AuthPage.css";

async function postJson(path, data) {
  const response = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw await responseError(response, "The request could not be completed.");
  }
  return response.status === 204 ? null : response.json();
}

export default function AuthPage({ onAuthenticated, notice }) {
  const query = new URLSearchParams(window.location.search);
  const queryPage = query.get("auth");
  const tokenFromLink = query.get("token") || "";
  const [page, setPage] = useState(
    [
      "verify",
      "reset",
      "admin-invitation",
      "admin-registration",
      "user-invitation",
    ].includes(queryPage)
      ? queryPage === "admin-invitation"
        ? "admin-registration"
        : queryPage
      : "login"
  );
  const [role, setRole] = useState(queryPage === "admin" ? "admin" : "user");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(tokenFromLink);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(
    queryPage === "verify" && !tokenFromLink
      ? "The verification link does not contain a token."
      : ""
  );
  const [busy, setBusy] = useState(false);
  const verificationRequest = useRef(null);

  useEffect(() => {
    if (page !== "verify") return undefined;
    let active = true;
    if (token) {
      if (verificationRequest.current?.token !== token) {
        verificationRequest.current = {
          token,
          promise: postJson("/auth/verify-email", { token }),
        };
      }
      verificationRequest.current.promise
        .then((result) => {
          if (active) {
            setMessage(
              `Email verified for ${result.email}. You can sign in and use Maintenance AI while your account awaits administrator approval.`
            );
          }
        })
        .catch((requestError) => {
          if (active) setError(requestError.message);
        });
    }
    return () => {
      active = false;
    };
  }, [page, token]);

  useEffect(() => {
    if (tokenFromLink) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [tokenFromLink]);

  function showPage(nextPage) {
    setPage(nextPage);
    setMessage("");
    setError("");
    setPassword("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (page === "register") {
        const result = await postJson("/auth/register", { name, email, password });
        setMessage(result.message);
      } else if (page === "login") {
        const result = await postJson(
          role === "admin" ? "/auth/admin/login" : "/auth/user/login",
          { email, password }
        );
        onAuthenticated(result.user);
      } else if (page === "forgot") {
        const result = await postJson("/auth/forgot-password", { email });
        setMessage(result.message);
      } else if (page === "reset") {
        const result = await postJson("/auth/reset-password", { token, password });
        setMessage(result.message);
        setPage("login");
      } else if (page === "admin-registration") {
        const result = await postJson("/auth/admin-invitations/accept", {
          token,
          name,
          password,
        });
        onAuthenticated(result.user);
      } else if (page === "user-invitation") {
        const result = await postJson(
          "/auth/user-invitations/accept",
          { token, email, name: name.trim(), password }
        );
        onAuthenticated(result.user);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  const titles = {
    login: role === "admin" ? "Administrator sign in" : "User sign in",
    register: "Create a user account",
    forgot: "Reset your password",
    reset: "Choose a new password",
    verify: "Verify your email",
    "admin-registration": "Administrator registration",
    "user-invitation": "Accept user invitation",
  };
  const needsForm = page !== "verify";

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          <span aria-hidden="true">⚙</span>
          <div>
            <h1>Maintenance AI</h1>
            <p>Industrial Intelligence</p>
          </div>
        </div>
        <h2>{titles[page] || titles.login}</h2>
        {page === "admin-registration" && (
          <p className="auth-message">
            Administrator accounts can only be created with an invitation from
            an existing administrator.
          </p>
        )}
        {page === "user-invitation" && (
          <p className="auth-message">
            Accepting an administrator-issued invitation grants full access to
            Maintenance AI without separate approval. If you already have a
            pending account, enter its email and current password. New users
            should enter a name and choose a password. Codes are valid for 7
            days.
          </p>
        )}
        {page === "login" && (
          <div className="auth-role-toggle" aria-label="Account type">
            <button
              type="button"
              className={role === "user" ? "selected" : ""}
              onClick={() => setRole("user")}
            >
              User
            </button>
            <button
              type="button"
              className={role === "admin" ? "selected" : ""}
              onClick={() => setRole("admin")}
            >
              Admin
            </button>
          </div>
        )}

        {needsForm && (
          <form className="auth-form" onSubmit={handleSubmit}>
            {["register", "admin-registration", "user-invitation"].includes(page) && (
              <label>
                Name
                <input
                  autoComplete="name"
                  maxLength={150}
                  required={page !== "user-invitation"}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
            )}
            {["login", "register", "forgot", "user-invitation"].includes(page) && (
              <label>
                {page === "user-invitation" ? "Invited email address" : "Email"}
                <input
                  autoComplete="email"
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
            )}
            {["reset", "admin-registration", "user-invitation"].includes(page) && (
              <label>
                {["admin-registration", "user-invitation"].includes(page)
                  ? page === "user-invitation"
                    ? "7-character invitation code"
                    : "Administrator invitation token"
                  : "Password reset token"}
                <input
                  required
                  autoCapitalize={page === "user-invitation" ? "characters" : undefined}
                  maxLength={
                    page === "user-invitation" && tokenFromLink.length <= 7
                      ? 7
                      : 512
                  }
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                />
              </label>
            )}
            {["login", "register", "reset", "admin-registration", "user-invitation"].includes(page) && (
              <label>
                Password
                <input
                  autoComplete={
                    page === "login" ? "current-password" : "new-password"
                  }
                  minLength={
                    page === "login"
                      ? 1
                      : 8
                  }
                  maxLength={128}
                  required
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
            )}
            <button className="auth-submit" disabled={busy} type="submit">
              {busy
                ? "Please wait…"
                : page === "login"
                  ? "Sign in"
                  : page === "admin-registration"
                    ? "Register administrator account"
                    : page === "user-invitation"
                      ? "Accept invitation and continue"
                    : "Continue"}
            </button>
          </form>
        )}

        {message && <p className="auth-message" role="status">{message}</p>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        {notice && <p className="auth-error" role="alert">{notice}</p>}

        {page === "login" && (
          <div className="auth-links">
            {role === "user" && (
              <button type="button" onClick={() => showPage("register")}>
                Create an account
              </button>
            )}
            <button type="button" onClick={() => showPage("user-invitation")}>
              Accept a user invitation
            </button>
            <button type="button" onClick={() => showPage("admin-registration")}>
              Administrator registration (invitation required)
            </button>
            <button type="button" onClick={() => showPage("forgot")}>
              Forgot password?
            </button>
          </div>
        )}
        {page !== "login" && page !== "verify" && (
          <button className="auth-back" type="button" onClick={() => showPage("login")}>
            Back to sign in
          </button>
        )}
        {page === "verify" && (
          <button className="auth-back" type="button" onClick={() => showPage("login")}>
            Go to sign in
          </button>
        )}
      </section>
    </main>
  );
}
