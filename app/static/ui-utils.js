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

const LANGUAGE_LABELS = {
  en: "English",
  de: "German",
  es: "Spanish",
  "es-419": "Spanish (Latin America)",
  fr: "French",
  ja: "Japanese",
  it: "Italian",
  nl: "Dutch",
  pl: "Polish",
  pt: "Portuguese",
  "pt-br": "Portuguese (Brazil)",
  "pt-pt": "Portuguese (Portugal)",
  hi: "Hindi",
  id: "Indonesian",
  th: "Thai",
  vi: "Vietnamese",
  ar: "Arabic",
  tr: "Turkish",
  ko: "Korean",
  "zh-hans": "Chinese (Simplified)",
  "zh-hant": "Chinese (Traditional)",
};

export function formatLanguageLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  const normalized = raw.toLowerCase();
  return LANGUAGE_LABELS[normalized] || raw;
}

const MARKET_LABELS_BY_CODE = {
  US: "United States",
  CA: "Canada",
  GB: "United Kingdom",
  DE: "Germany",
  FR: "France",
  ES: "Spain",
  IT: "Italy",
  NL: "Netherlands",
  SE: "Sweden",
  PL: "Poland",
  JP: "Japan",
  KR: "South Korea",
  TW: "Taiwan",
  HK: "Hong Kong",
  SG: "Singapore",
  IN: "India",
  AU: "Australia",
  BR: "Brazil",
  MX: "Mexico",
  AE: "United Arab Emirates",
};

const MARKET_NORMALIZATION = {
  global: "Global",
  us: "United States",
  usa: "United States",
  "united states": "United States",
  ca: "Canada",
  canada: "Canada",
  gb: "United Kingdom",
  uk: "United Kingdom",
  "united kingdom": "United Kingdom",
  de: "Germany",
  germany: "Germany",
  fr: "France",
  france: "France",
  es: "Spain",
  spain: "Spain",
  it: "Italy",
  italy: "Italy",
  nl: "Netherlands",
  netherlands: "Netherlands",
  se: "Sweden",
  sweden: "Sweden",
  pl: "Poland",
  poland: "Poland",
  jp: "Japan",
  japan: "Japan",
  kr: "South Korea",
  korea: "South Korea",
  "south korea": "South Korea",
  tw: "Taiwan",
  taiwan: "Taiwan",
  hk: "Hong Kong",
  "hong kong": "Hong Kong",
  sg: "Singapore",
  singapore: "Singapore",
  in: "India",
  india: "India",
  au: "Australia",
  australia: "Australia",
  br: "Brazil",
  brazil: "Brazil",
  mx: "Mexico",
  mexico: "Mexico",
  ae: "United Arab Emirates",
  "united arab emirates": "United Arab Emirates",
  uae: "United Arab Emirates",
};

const LANGUAGE_NORMALIZATION = {
  english: "en",
  en: "en",
  german: "de",
  de: "de",
  spanish: "es",
  es: "es",
  "spanish (latin america)": "es-419",
  "es-419": "es-419",
  french: "fr",
  fr: "fr",
  italian: "it",
  it: "it",
  dutch: "nl",
  nl: "nl",
  polish: "pl",
  pl: "pl",
  portuguese: "pt",
  pt: "pt",
  "portuguese (brazil)": "pt-br",
  "pt-br": "pt-br",
  "portuguese (portugal)": "pt-pt",
  "pt-pt": "pt-pt",
  japanese: "ja",
  ja: "ja",
  korean: "ko",
  ko: "ko",
  "chinese (simplified)": "zh-hans",
  "zh-hans": "zh-hans",
  "chinese (traditional)": "zh-hant",
  "zh-hant": "zh-hant",
  hindi: "hi",
  hi: "hi",
  indonesian: "id",
  id: "id",
  thai: "th",
  th: "th",
  vietnamese: "vi",
  vi: "vi",
  arabic: "ar",
  ar: "ar",
  turkish: "tr",
  tr: "tr",
};

export function formatMarketLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  if (raw.toLowerCase() === "global") {
    return "Global";
  }
  if (MARKET_LABELS_BY_CODE[raw.toUpperCase()]) {
    return MARKET_LABELS_BY_CODE[raw.toUpperCase()];
  }
  return raw;
}

export function normalizeSelectableValue(rawValue, type) {
  const value = (rawValue || "").trim();
  if (!value) {
    return "";
  }
  const match = value.match(/\(([^)]+)\)\s*$/);
  if (match && match[1]) {
    if (type === "languages") {
      return match[1].toLowerCase().replace(/_/g, "-");
    }
    return value.replace(/\s*\([^)]+\)\s*$/, "").trim();
  }
  if (type === "languages") {
    const normalizedLanguage = value.toLowerCase().replace(/_/g, "-");
    return LANGUAGE_NORMALIZATION[normalizedLanguage] || normalizedLanguage;
  }
  const normalizedMarket = value.toLowerCase();
  return MARKET_NORMALIZATION[normalizedMarket] || value;
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
