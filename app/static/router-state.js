const projectRoutePattern = /^\/projects\/(\d+)\/?$/;

export function getProjectIdFromRoute(pathname = window.location.pathname) {
  const match = pathname.match(projectRoutePattern);
  if (!match || !match[1]) {
    return null;
  }
  const projectId = Number(match[1]);
  return Number.isNaN(projectId) ? null : projectId;
}

export function navigateToProject(projectId) {
  if (!projectId) {
    return;
  }
  window.location.assign(`/projects/${projectId}`);
}

export function syncProjectRoute(projectId) {
  const target = projectId ? `/projects/${projectId}` : "/";
  if (window.location.pathname === target) {
    return;
  }
  window.history.replaceState({}, "", target);
}

export function getVideoIdFromRouteSearch() {
  const params = new URLSearchParams(window.location.search);
  const id = Number(params.get("video"));
  return Number.isNaN(id) ? null : id;
}

export function clearVideoQueryParam() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("video")) {
    return;
  }
  url.searchParams.delete("video");
  window.history.replaceState({}, "", `${url.pathname}${url.search}`);
}

export function navigateToProjectVideo(projectId, videoId) {
  if (!projectId || !videoId) {
    return;
  }
  window.location.assign(`/projects/${projectId}?video=${videoId}`);
}
