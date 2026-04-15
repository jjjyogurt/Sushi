import { getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

function buildVersionName(prefix) {
  const now = new Date();
  return `${prefix} ${now.toISOString().slice(0, 10)}`;
}

function renderStatus(targetId, message) {
  const target = getElement(targetId);
  if (target) {
    target.textContent = message;
  }
}

function resolveActive(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }
  return items.find((item) => item.is_active) || items[0];
}

function tableRow(content, index) {
  return `<tr><td>${index + 1}</td><td>${content}</td></tr>`;
}

function activateVocPanel() {
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === "voc");
  });
  document.querySelectorAll(".nav-btn[data-section]").forEach((button) => {
    button.classList.toggle("active", button.dataset.section === "voc");
  });
}

function setVocCreateVisible(isVisible) {
  const container = getElement("voc-create-container");
  const toggleButton = getElement("voc-toggle-create-btn");
  if (!container || !toggleButton) {
    return;
  }
  container.classList.toggle("is-hidden", !isVisible);
  toggleButton.textContent = isVisible ? t("dashboardHideForm") : t("dashboardNewProject");
}

function parseTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isDividerRow(cells) {
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function createTextElement(tagName, text, className = "") {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  element.textContent = text;
  return element;
}

function resolveSelectableProjectId(projects, preferredId) {
  if (!Array.isArray(projects) || projects.length === 0) {
    return null;
  }
  const hasPreferred = preferredId !== null && projects.some((project) => project.id === preferredId);
  if (hasPreferred) {
    return preferredId;
  }
  return projects[0].id;
}

function renderMarkdownReport(markdown, target) {
  if (!(target instanceof HTMLElement)) {
    return;
  }

  target.replaceChildren();
  const source = (markdown || "").trim();
  if (!source) {
    target.append(createTextElement("p", t("reportPlaceholder"), "meta"));
    return;
  }

  const lines = source.split(/\r?\n/);
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = Math.min(6, headingMatch[1].length);
      target.append(createTextElement(`h${level}`, headingMatch[2], "voc-md-heading"));
      index += 1;
      continue;
    }

    if (trimmed.startsWith("|")) {
      const tableLines = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        tableLines.push(lines[index].trim());
        index += 1;
      }

      const parsedRows = tableLines.map(parseTableRow);
      const hasHeaderDivider = parsedRows.length > 1 && isDividerRow(parsedRows[1]);
      const table = document.createElement("table");
      table.className = "voc-md-table";
      const thead = document.createElement("thead");
      const tbody = document.createElement("tbody");

      if (hasHeaderDivider) {
        const headerRow = document.createElement("tr");
        parsedRows[0].forEach((cell) => {
          headerRow.append(createTextElement("th", cell));
        });
        thead.append(headerRow);
        parsedRows.slice(2).forEach((row) => {
          const bodyRow = document.createElement("tr");
          row.forEach((cell) => {
            bodyRow.append(createTextElement("td", cell));
          });
          tbody.append(bodyRow);
        });
      } else {
        parsedRows.forEach((row) => {
          const bodyRow = document.createElement("tr");
          row.forEach((cell) => {
            bodyRow.append(createTextElement("td", cell));
          });
          tbody.append(bodyRow);
        });
      }

      if (thead.childNodes.length > 0) {
        table.append(thead);
      }
      table.append(tbody);
      const tableWrap = document.createElement("div");
      tableWrap.className = "voc-md-table-wrap";
      tableWrap.append(table);
      target.append(tableWrap);
      continue;
    }

    if (/^\s*-\s+/.test(line)) {
      const list = document.createElement("ul");
      list.className = "voc-md-list";
      while (index < lines.length && /^\s*-\s+/.test(lines[index])) {
        const currentLine = lines[index];
        const content = currentLine.replace(/^\s*-\s+/, "");
        const indent = currentLine.match(/^\s*/)?.[0].length ?? 0;
        const item = createTextElement("li", content, "voc-md-list-item");
        if (indent > 0) {
          item.style.marginLeft = `${Math.min(indent * 8, 24)}px`;
        }
        list.append(item);
        index += 1;
      }
      target.append(list);
      continue;
    }

    const paragraphLines = [];
    while (index < lines.length) {
      const currentLine = lines[index];
      const currentTrimmed = currentLine.trim();
      if (!currentTrimmed) {
        break;
      }
      if (
        /^(#{1,6})\s+/.test(currentTrimmed) ||
        currentTrimmed.startsWith("|") ||
        /^\s*-\s+/.test(currentLine)
      ) {
        break;
      }
      paragraphLines.push(currentTrimmed);
      index += 1;
    }
    target.append(createTextElement("p", paragraphLines.join(" "), "voc-md-paragraph"));
  }
}

export function createVocController({ request, requestForm, runTask }) {
  let state = {
    projects: [],
    uploads: [],
    selectedProjectId: null,
    selectedUploadId: null,
    reportId: null,
    reportMode: "preview",
    skillVersions: {
      cleaner: null,
      analyzer: null,
    },
  };

  function setVocState(updater) {
    state =
      typeof updater === "function"
        ? updater(state)
        : {
            ...state,
            ...updater,
          };
    return state;
  }

  function setReportMode(mode) {
    const reportRendered = getElement("voc-report-rendered");
    const reportEditor = getElement("voc-report-editor");
    const previewButton = getElement("voc-report-preview-btn");
    const editButton = getElement("voc-report-edit-btn");
    const reportInput = getElement("voc-report-content");

    if (!(reportRendered instanceof HTMLElement) || !(reportEditor instanceof HTMLElement)) {
      return;
    }

    const isPreview = mode !== "edit";
    reportRendered.classList.toggle("is-hidden", !isPreview);
    reportEditor.classList.toggle("is-hidden", isPreview);

    if (previewButton instanceof HTMLButtonElement) {
      previewButton.classList.toggle("is-active", isPreview);
    }
    if (editButton instanceof HTMLButtonElement) {
      editButton.classList.toggle("is-active", !isPreview);
    }

    setVocState((previous) => ({
      ...previous,
      reportMode: isPreview ? "preview" : "edit",
    }));

    if (isPreview && reportInput instanceof HTMLTextAreaElement) {
      renderMarkdownReport(reportInput.value, reportRendered);
    }
  }

  function syncReportView(content) {
    const reportInput = getElement("voc-report-content");
    const reportRendered = getElement("voc-report-rendered");

    if (reportInput instanceof HTMLTextAreaElement) {
      reportInput.value = content || "";
    }
    renderMarkdownReport(content || "", reportRendered);
  }

  async function loadProjects() {
    const payload = await request("/voc/projects");
    const projects = Array.isArray(payload.items) ? payload.items : [];
    const select = getElement("voc-project-select");
    if (!(select instanceof HTMLSelectElement)) {
      return;
    }
    const selectedId = resolveSelectableProjectId(projects, state.selectedProjectId);
    const hasProjects = projects.length > 0;
    select.innerHTML = hasProjects
      ? projects.map((project) => `<option value="${project.id}">${project.name}</option>`).join("")
      : `<option value="">${t("vocNoProjectsYet")}</option>`;
    select.disabled = !hasProjects;
    select.value = selectedId === null ? "" : String(selectedId);
    setVocState((previous) => ({
      ...previous,
      projects,
      selectedProjectId: selectedId,
      uploads: selectedId === null ? [] : previous.uploads,
      selectedUploadId: selectedId === null ? null : previous.selectedUploadId,
      reportId: selectedId === null ? null : previous.reportId,
    }));

    if (selectedId === null) {
      renderStatus("voc-upload-meta", t("noUploadsYet"));
      renderStatus("voc-report-meta", t("noReportYet"));
      syncReportView("");
      return;
    }

    await loadUploads(selectedId);
    await loadReport(selectedId);
  }

  async function createProject() {
    activateVocPanel();
    const nameInput = getElement("voc-project-name");
    const descriptionInput = getElement("voc-project-description");
    if (!(nameInput instanceof HTMLInputElement) || !(descriptionInput instanceof HTMLTextAreaElement)) {
      return;
    }
    const name = nameInput.value.trim();
    const description = descriptionInput.value.trim();
    if (!name) {
      throw new Error(t("errorProjectNameRequired"));
    }
    const payload = await request("/voc/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
    if (payload && payload.id) {
      setVocState((previous) => ({
        ...previous,
        selectedProjectId: payload.id,
      }));
    }
    nameInput.value = "";
    descriptionInput.value = "";
    await loadProjects();
    activateVocPanel();
    setVocCreateVisible(false);
  }

  async function loadUploads(projectId) {
    const payload = await request(`/voc/uploads?project_id=${projectId}`);
    const uploads = Array.isArray(payload.items) ? payload.items : [];
    const latest = uploads[0];
    setVocState((previous) => ({
      ...previous,
      uploads,
      selectedUploadId: latest ? latest.id : null,
    }));
    renderStatus(
      "voc-upload-meta",
      latest ? t("latestUploadMeta", { filename: latest.filename, rows: latest.total_rows }) : t("noUploadsYet")
    );
  }

  async function uploadFile() {
    const input = getElement("voc-upload-input");
    if (!(input instanceof HTMLInputElement) || !input.files || input.files.length === 0) {
      throw new Error(t("errorSelectCsv"));
    }
    if (!state.selectedProjectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const formData = new FormData();
    formData.append("project_id", String(state.selectedProjectId));
    formData.append("file", input.files[0]);
    const payload = await requestForm("/voc/uploads", formData);
    setVocState((previous) => ({
      ...previous,
      selectedUploadId: payload.id,
    }));
    renderStatus("voc-upload-meta", t("uploadedMeta", { filename: payload.filename, rows: payload.total_rows }));
    input.value = "";
  }

  async function startCleaning() {
    if (!state.selectedUploadId) {
      throw new Error(t("errorUploadBeforeCleaning"));
    }
    const payload = await request("/voc/runs/clean", {
      method: "POST",
      body: JSON.stringify({ upload_id: state.selectedUploadId }),
    });
    renderStatus("voc-clean-meta", t("cleaningStatus", { status: payload.status }));
    await loadCleanedRows();
  }

  async function loadCleanedRows() {
    if (!state.selectedUploadId) {
      return;
    }
    const payload = await request(`/voc/rows?upload_id=${state.selectedUploadId}&status=cleaned&limit=50`);
    const rows = Array.isArray(payload.items) ? payload.items : [];
    const tbody = getElement("voc-cleaned-rows");
    if (!tbody) {
      return;
    }
    tbody.innerHTML = rows
      .map((row, index) => {
        const cleaned = row.cleaned_content || "";
        return tableRow(cleaned.slice(0, 280), index);
      })
      .join("");
  }

  async function downloadCleaned() {
    if (!state.selectedUploadId) {
      throw new Error(t("errorNoCleanedDataset"));
    }
    const payload = await request(`/voc/rows?upload_id=${state.selectedUploadId}&status=cleaned&limit=500`);
    const rows = Array.isArray(payload.items) ? payload.items : [];
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "voc_cleaned_rows.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  }

  async function startAnalysis() {
    if (!state.selectedUploadId) {
      throw new Error(t("errorUploadBeforeAnalysis"));
    }
    const report = await request("/voc/runs/analyze", {
      method: "POST",
      body: JSON.stringify({ upload_id: state.selectedUploadId }),
    });
    setVocState((previous) => ({
      ...previous,
      reportId: report.id,
    }));
    syncReportView(report.content || "");
    setReportMode("preview");
    renderStatus("voc-analysis-meta", t("analysisCompleted"));
  }

  function clearAnalysisResult() {
    setVocState((previous) => ({
      ...previous,
      reportId: null,
    }));
    syncReportView("");
    setReportMode("preview");
    renderStatus("voc-analysis-meta", t("analysisCleared"));
    renderStatus("voc-report-meta", t("noReportYet"));
  }

  async function loadReport(projectId) {
    try {
      const report = await request(`/voc/reports?project_id=${projectId}`);
      setVocState((previous) => ({
        ...previous,
        reportId: report.id,
      }));
      syncReportView(report.content || "");
      renderStatus("voc-report-meta", t("reportStatus", { status: report.status }));
    } catch {
      syncReportView("");
      renderStatus("voc-report-meta", t("noReportYet"));
    }
  }

  async function saveReport() {
    if (!state.reportId) {
      throw new Error(t("errorNoReportToSave"));
    }
    const reportInput = getElement("voc-report-content");
    if (!(reportInput instanceof HTMLTextAreaElement)) {
      return;
    }
    const payload = await request(`/voc/reports/${state.reportId}`, {
      method: "PUT",
      body: JSON.stringify({ content: reportInput.value }),
    });
    syncReportView(payload.content || reportInput.value);
    renderStatus("voc-report-meta", t("reportSavedStatus", { status: payload.status }));
  }

  async function publishReport() {
    if (!state.reportId) {
      throw new Error(t("errorNoReportToPublish"));
    }
    const payload = await request(`/voc/reports/${state.reportId}/publish`, { method: "POST" });
    renderStatus(
      "voc-report-meta",
      payload.allowed ? t("reportPublished") : t("publishBlocked", { reason: payload.reason })
    );
  }

  async function loadSkill(type, inputId, metaId) {
    const payload = await request(`/voc/settings/skills?skill_type=${type}`);
    const active = resolveActive(payload.items);
    setVocState((previous) => ({
      ...previous,
      skillVersions: {
        ...previous.skillVersions,
        [type]: active,
      },
    }));
    const input = getElement(inputId);
    if (input instanceof HTMLTextAreaElement && active) {
      input.value = active.content || "";
    }
    if (active) {
      renderStatus(metaId, t("statusLabel", { status: active.status }));
    }
  }

  async function saveSkillSettings(type, inputId, metaId) {
    const input = getElement(inputId);
    if (!(input instanceof HTMLTextAreaElement)) {
      return;
    }
    const created = await request("/voc/settings/skills", {
      method: "POST",
      body: JSON.stringify({
        skill_type: type,
        name: buildVersionName(`${type}-skill`),
        content: input.value,
      }),
    });
    setVocState((previous) => ({
      ...previous,
      skillVersions: {
        ...previous.skillVersions,
        [type]: created,
      },
    }));
    const validated = await request(`/voc/settings/skills/${created.id}/validate`, { method: "POST" });
    setVocState((previous) => ({
      ...previous,
      skillVersions: {
        ...previous.skillVersions,
        [type]: validated,
      },
    }));
    const active = await request(`/voc/settings/skills/${validated.id}/activate`, { method: "POST" });
    setVocState((previous) => ({
      ...previous,
      skillVersions: {
        ...previous.skillVersions,
        [type]: active,
      },
    }));
    renderStatus(metaId, t("statusLabel", { status: active.status }));
  }

  async function resetSkillToDefault(type, inputId, metaId) {
    const input = getElement(inputId);
    if (!(input instanceof HTMLTextAreaElement)) {
      return;
    }
    const payload = await request("/voc/settings/skills/defaults");
    const field = type === "cleaner" ? "cleaner" : "analyzer";
    input.value = payload[field] ?? "";
    renderStatus(metaId, t("defaultLoadedSaveToApply"));
  }

  function bindVocControls() {
    const form = getElement("voc-project-form");
    if (form instanceof HTMLFormElement) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        event.stopPropagation();
        void runTask(async () => {
          await createProject();
        }, t("vocProjectCreated"));
      });
    }
    const createButton = getElement("voc-project-create-btn");
    if (createButton instanceof HTMLButtonElement) {
      createButton.addEventListener("click", () => {
        void runTask(async () => {
          await createProject();
        }, t("vocProjectCreated"));
      });
    }
    const toggleButton = getElement("voc-toggle-create-btn");
    if (toggleButton instanceof HTMLButtonElement) {
      toggleButton.addEventListener("click", () => {
        const isHidden = getElement("voc-create-container")?.classList.contains("is-hidden");
        setVocCreateVisible(Boolean(isHidden));
      });
    }

    const projectSelect = getElement("voc-project-select");
    if (projectSelect instanceof HTMLSelectElement) {
      projectSelect.addEventListener("change", () => {
        const projectId = Number(projectSelect.value);
        if (Number.isNaN(projectId)) {
          return;
        }
        setVocState((previous) => ({
          ...previous,
          selectedProjectId: projectId,
        }));
        void runTask(async () => {
          await loadUploads(projectId);
          await loadReport(projectId);
        });
      });
    }

    const uploadButton = getElement("voc-upload-btn");
    if (uploadButton instanceof HTMLButtonElement) {
      uploadButton.addEventListener("click", () => {
        void runTask(async () => {
          await uploadFile();
        }, t("vocDataUploaded"));
      });
    }

    const cleanButton = getElement("voc-clean-btn");
    if (cleanButton instanceof HTMLButtonElement) {
      cleanButton.addEventListener("click", () => {
        void runTask(async () => {
          await startCleaning();
        }, t("cleaningCompleted"));
      });
    }

    const downloadButton = getElement("voc-download-clean-btn");
    if (downloadButton instanceof HTMLButtonElement) {
      downloadButton.addEventListener("click", () => {
        void runTask(async () => {
          await downloadCleaned();
        });
      });
    }

    const analyzeButton = getElement("voc-analyze-btn");
    if (analyzeButton instanceof HTMLButtonElement) {
      analyzeButton.addEventListener("click", () => {
        void runTask(async () => {
          await startAnalysis();
        }, t("analysisCompleted"));
      });
    }
    const rerunAnalyzeButton = getElement("voc-rerun-analyze-btn");
    if (rerunAnalyzeButton instanceof HTMLButtonElement) {
      rerunAnalyzeButton.addEventListener("click", () => {
        void runTask(async () => {
          await startAnalysis();
        }, t("analysisRerunCompleted"));
      });
    }
    const clearAnalysisButton = getElement("voc-clear-analysis-btn");
    if (clearAnalysisButton instanceof HTMLButtonElement) {
      clearAnalysisButton.addEventListener("click", () => {
        clearAnalysisResult();
      });
    }

    const saveReportButton = getElement("voc-report-save-btn");
    if (saveReportButton instanceof HTMLButtonElement) {
      saveReportButton.addEventListener("click", () => {
        void runTask(async () => {
          await saveReport();
        }, t("reportSaved"));
      });
    }

    const publishReportButton = getElement("voc-report-publish-btn");
    const previewReportButton = getElement("voc-report-preview-btn");
    const editReportButton = getElement("voc-report-edit-btn");
    const reportInput = getElement("voc-report-content");
    if (publishReportButton instanceof HTMLButtonElement) {
      publishReportButton.addEventListener("click", () => {
        void runTask(async () => {
          await publishReport();
        });
      });
    }
    if (previewReportButton instanceof HTMLButtonElement) {
      previewReportButton.addEventListener("click", () => {
        setReportMode("preview");
      });
    }
    if (editReportButton instanceof HTMLButtonElement) {
      editReportButton.addEventListener("click", () => {
        setReportMode("edit");
      });
    }
    if (reportInput instanceof HTMLTextAreaElement) {
      reportInput.addEventListener("input", () => {
        const reportRendered = getElement("voc-report-rendered");
        renderMarkdownReport(reportInput.value, reportRendered);
      });
    }

    const cleanerSave = getElement("voc-cleaner-skill-save");
    const cleanerReset = getElement("voc-cleaner-skill-reset");
    if (cleanerSave instanceof HTMLButtonElement) {
      cleanerSave.addEventListener("click", () => {
        void runTask(async () => {
          await saveSkillSettings("cleaner", "voc-cleaner-skill-input", "voc-cleaner-skill-meta");
        }, t("cleanerSettingsSaved"));
      });
    }
    if (cleanerReset instanceof HTMLButtonElement) {
      cleanerReset.addEventListener("click", () => {
        void runTask(async () => {
          await resetSkillToDefault("cleaner", "voc-cleaner-skill-input", "voc-cleaner-skill-meta");
        }, t("cleanerDefaultLoaded"));
      });
    }

    const analyzerSave = getElement("voc-analyzer-skill-save");
    const analyzerReset = getElement("voc-analyzer-skill-reset");
    if (analyzerSave instanceof HTMLButtonElement) {
      analyzerSave.addEventListener("click", () => {
        void runTask(async () => {
          await saveSkillSettings("analyzer", "voc-analyzer-skill-input", "voc-analyzer-skill-meta");
        }, t("analyzerSettingsSaved"));
      });
    }
    if (analyzerReset instanceof HTMLButtonElement) {
      analyzerReset.addEventListener("click", () => {
        void runTask(async () => {
          await resetSkillToDefault("analyzer", "voc-analyzer-skill-input", "voc-analyzer-skill-meta");
        }, t("analyzerDefaultLoaded"));
      });
    }

  }

  async function loadSettings() {
    await loadSkill("cleaner", "voc-cleaner-skill-input", "voc-cleaner-skill-meta");
    await loadSkill("analyzer", "voc-analyzer-skill-input", "voc-analyzer-skill-meta");
  }

  return {
    bindVocControls,
    loadProjects,
    loadSettings,
    setReportMode,
  };
}
