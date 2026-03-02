export async function apiFetch(url: string, options: any = {}) {
  // Normalise base URL (remove trailing slash)
  const API_URL = (process.env.REACT_APP_API_URL ?? "").replace(/\/$/, "");
  const fullUrl = `${API_URL}${url}`;

  const access = localStorage.getItem("access");

  // Merge headers safely
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
    ...(access ? { Authorization: `Bearer ${access}` } : {}),
  };

  // Helper to perform a fetch with merged headers
  const doFetch = (overrideHeaders = headers) =>
    fetch(fullUrl, {
      ...options,
      headers: overrideHeaders,
      credentials: "include",
    });

  // If no access token, just do a simple fetch
  if (!access) {
    return doFetch();
  }

  // First attempt
  let res = await doFetch();

  // If unauthorized → try refresh
  if (res.status === 401) {
    const refresh = localStorage.getItem("refresh");

    if (!refresh) {
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      localStorage.removeItem("user");
      return res;
    }

    // Attempt refresh
    const refreshRes = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
      credentials: "include",
    });

    if (!refreshRes.ok) {
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      localStorage.removeItem("user");
      return res;
    }

    // Store new access token
    const data = await refreshRes.json();
    localStorage.setItem("access", data.access);

    const retryHeaders = {
      ...headers,
      Authorization: `Bearer ${data.access}`,
    };

    // Retry original request with new token
    res = await doFetch(retryHeaders);
  }

  return res;
}

export async function apiFetchJson(url: string, options: any = {}) {
  const res = await apiFetch(url, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}