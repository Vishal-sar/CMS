import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API, withCredentials: true });

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config || {};
    const url = cfg.url || "";
    if (err.response?.status === 401 && !cfg._retry && !url.includes("/auth/")) {
      cfg._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh").finally(() => { refreshing = null; });
        await refreshing;
        return api(cfg);
      } catch (e) {
        window.dispatchEvent(new CustomEvent("session-expired"));
      }
    }
    return Promise.reject(err);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (d == null) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x?.msg ? `${x.loc?.slice(-1)[0] ?? ""}: ${x.msg}` : JSON.stringify(x))).join("; ");
  return d.msg || JSON.stringify(d);
}

export const fileUrl = (id) => (id ? `${API}/files/${id}` : null);

export async function downloadFile(path, params = {}, filename = "export.csv") {
  const r = await api.get(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export async function uploadFile(file, context) {
  const fd = new FormData();
  fd.append("file", file); fd.append("context", context);
  const { data } = await api.post("/files", fd);
  return data;
}
