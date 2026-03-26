export async function request(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const hasFormDataBody = typeof FormData !== "undefined" && rest.body instanceof FormData;
  const computedHeaders = hasFormDataBody ? { ...headers } : { "Content-Type": "application/json", ...headers };
  const response = await fetch(path, {
    headers: computedHeaders,
    ...rest,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorPayload.detail || "Request failed");
  }

  return response.json();
}

export async function requestForm(path, formData, options = {}) {
  return request(path, {
    method: "POST",
    body: formData,
    ...options,
  });
}
