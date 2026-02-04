export async function apiFetch(url: string, options: any = {}) {

if (!access) {
  // No token → do not attempt refresh
  return fetch(url, { ...options, headers });
}


  const access = localStorage.getItem("access");

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
    ...(access ? { "Authorization": `Bearer ${access}` } : {}),
  };

  let res = await fetch(url, { ...options, headers });

if (res.status === 401) {
  const refresh = localStorage.getItem("refresh");

  if (!refresh) {
    localStorage.removeItem("access");
    localStorage.removeItem("user");
    return res;
  }

  const refreshRes = await fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (!refreshRes.ok) {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("user");
    return res;
  }

  const data = await refreshRes.json();
  localStorage.setItem("access", data.access);

  const retryHeaders = {
    ...headers,
    "Authorization": `Bearer ${data.access}`,
  };

  res = await fetch(url, { ...options, headers: retryHeaders });
}

  return res;
}

export async function apiFetchJson(url: string, options: any = {}) {
  const res = await apiFetch(url, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
