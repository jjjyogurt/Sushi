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
