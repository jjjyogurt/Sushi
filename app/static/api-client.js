export class ApiError extends Error {
  constructor(message, { status = 0, detail = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function messageFromDetail(detail) {
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return "Request failed";
}

export async function request(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const hasFormDataBody = typeof FormData !== "undefined" && rest.body instanceof FormData;
  const computedHeaders = hasFormDataBody ? { ...headers } : { "Content-Type": "application/json", ...headers };
  const response = await fetch(path, {
    headers: computedHeaders,
    credentials: "same-origin",
    ...rest,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: "Request failed" }));
    const rawDetail = errorPayload.detail;
    throw new ApiError(messageFromDetail(rawDetail), { status: response.status, detail: rawDetail });
  }

  if (response.status === 204) {
    return {};
  }
  const responseType = response.headers.get("content-type") || "";
  if (!responseType.includes("application/json")) {
    return {};
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
