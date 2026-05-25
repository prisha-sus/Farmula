export const API_BASE =
  import.meta.env.VITE_FASTAPI_URL || "http://127.0.0.1:8006";

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload?.detail
        ? payload.detail
        : "Request failed";
    throw new Error(message);
  }

  return payload;
}
