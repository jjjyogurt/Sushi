export async function request(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...headers },
    ...rest,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorPayload.detail || "Request failed");
  }

  return response.json();
}
