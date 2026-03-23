export function getElement(id) {
  return document.getElementById(id);
}

export function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function splitCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function normalizeSelectableValue(rawValue, type) {
  const value = (rawValue || "").trim();
  if (!value) {
    return "";
  }
  const match = value.match(/\(([^)]+)\)\s*$/);
  if (match && match[1]) {
    return type === "languages" ? match[1].toLowerCase() : match[1].toUpperCase();
  }
  return type === "languages" ? value.toLowerCase() : value;
}

export function debounce(callback, delayMs) {
  let timeoutId = null;
  return (...args) => {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
    timeoutId = window.setTimeout(() => callback(...args), delayMs);
  };
}
