export const API_URL =
  import.meta.env.VITE_API_URL ||
  "https://maintanence.prod.page";

export function apiFetch(path, options = {}) {
  const url = path.startsWith("http")
    ? path
    : `${API_URL}${path.startsWith("/") ? "" : "/"}${path}`;

  const headers = new Headers(options.headers || {});

  return fetch(url, {
    ...options,
    credentials: "include",
    headers,
  });
}

export async function responseError(response, fallback) {
  const data = await response.json().catch(() => ({}));
  return new Error(data.detail || fallback);
}
