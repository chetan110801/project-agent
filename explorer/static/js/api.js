// Tiny fetch wrapper over the read-only JSON API. Every call returns parsed JSON or
// throws with the server's error message.
export async function api(path, params) {
  const url = new URL(path, location.origin);
  if (params) for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
  return data;
}
