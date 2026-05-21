import { escapeHtml } from "./ui-utils.js";

const ICON_IDS = Object.freeze({
  add: "add",
  arrow_back: "arrow-back",
  auto_awesome: "auto-awesome",
  bookmark: "bookmark",
  bookmark_add: "bookmark-add",
  bookmark_remove: "bookmark-remove",
  bookmarks: "bookmarks",
  check_circle: "check-circle",
  close: "close",
  dashboard: "dashboard",
  delete: "delete",
  description: "description",
  expand_more: "expand-more",
  forum: "forum",
  help: "help",
  history: "history",
  insights: "insights",
  logout: "logout",
  more_vert: "more-vert",
  notifications: "notifications",
  notifications_active: "notifications-active",
  open_in_full: "open-in-full",
  queue_play_next: "queue-play-next",
  settings: "settings",
  video_library: "video-library",
  voice_chat: "voice-chat",
});

export function iconSvg(name, className = "") {
  const iconId = ICON_IDS[name];
  if (!iconId) {
    return "";
  }
  const extraClass = className ? ` ${escapeHtml(className)}` : "";
  return `<svg class="app-icon${extraClass}" aria-hidden="true" focusable="false"><use href="/static/icons.svg?v=20260521-two-corner-expand#icon-${iconId}"></use></svg>`;
}
