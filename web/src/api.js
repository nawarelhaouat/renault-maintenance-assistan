const BASE = "/api";
let onUnauthorized = () => {};

export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = localStorage.getItem("token");
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (res.status === 401 && path !== "/auth/login") {
    onUnauthorized();
    throw new Error("Session expirée");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* réponse sans JSON */
    }
    throw new Error(typeof detail === "string" ? detail : "Requête invalide");
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  login: (username, password) => request("/auth/login", { method: "POST", body: { username, password } }),
  me: () => request("/auth/me"),
  machines: () => request("/machines"),
  conversations: () => request("/conversations"),
  conversation: (id) => request(`/conversations/${id}`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: "DELETE" }),
  chat: (payload) => request("/chat", { method: "POST", body: payload }),
  identify: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/identify", { method: "POST", form });
  },
    summary: (days = 90) => request(`/dashboard/summary?days=${days}`),
  fleet: () => request("/dashboard/fleet"),
  monthly: () => request("/dashboard/failures-monthly"),
  failureCodes: (days = 90) => request(`/dashboard/failure-codes?days=${days}`),
  modelMetrics: () => request("/dashboard/model-metrics"),
  machineDetail: (tag) => request(`/dashboard/machines/${tag}`),
};