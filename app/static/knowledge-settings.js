import { getElement } from "./ui-utils.js";
import { iconSvg } from "./icons.js";
import { t } from "./i18n.js";

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function createKnowledgeSettingsController({ request, requestForm, runTask, getState }) {
  const state = {
    bases: [],
    selectedProjectId: null,
    selectedKnowledgeBaseId: null,
  };

  function selectedProjectIdFromState() {
    if (state.selectedProjectId) {
      return state.selectedProjectId;
    }
    const globalState = getState();
    return globalState.selectedProfileId || null;
  }

  function renderProjectOptions() {
    const select = getElement("knowledge-project-select");
    if (!(select instanceof HTMLSelectElement)) {
      return;
    }
    const globalState = getState();
    select.innerHTML = `<option value="">${t("selectProject")}</option>`;
    globalState.profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = String(profile.id);
      option.textContent = profile.name;
      select.appendChild(option);
    });
    const selected = selectedProjectIdFromState();
    select.value = selected ? String(selected) : "";
  }

  function renderKnowledgeBases() {
    const select = getElement("knowledge-base-select");
    const meta = getElement("knowledge-base-meta");
    if (!(select instanceof HTMLSelectElement)) {
      return;
    }
    select.innerHTML = `<option value="">${t("selectLibrary")}</option>`;
    state.bases.forEach((base) => {
      const option = document.createElement("option");
      option.value = String(base.id);
      option.textContent = base.is_active ? `${base.name} (${t("active")})` : base.name;
      select.appendChild(option);
    });
    if (state.selectedKnowledgeBaseId) {
      select.value = String(state.selectedKnowledgeBaseId);
    }
    if (meta) {
      meta.textContent = t("knowledgeLibrariesCount", { count: state.bases.length });
    }
  }

  async function loadKnowledgeBases() {
    const projectId = selectedProjectIdFromState();
    if (!projectId) {
      state.bases = [];
      state.selectedKnowledgeBaseId = null;
      renderKnowledgeBases();
      renderSources([]);
      renderSummary("");
      return;
    }

    const response = await request(`/knowledge/bases?monitor_profile_id=${projectId}`);
    const items = Array.isArray(response.items) ? response.items : [];
    state.bases = items;
    const active = items.find((item) => item.is_active);
    state.selectedKnowledgeBaseId = state.selectedKnowledgeBaseId || (active ? active.id : items[0]?.id || null);
    renderKnowledgeBases();
    await loadSourcesAndSummary();
  }

  function renderSources(items) {
    const list = getElement("knowledge-source-list");
    if (!list) {
      return;
    }
    if (!items.length) {
      list.innerHTML = `<li class="meta">${t("noSourcesInLibrary")}</li>`;
      return;
    }
    list.innerHTML = items
      .map(
        (item) => `
        <li class="knowledge-source-item">
          <div class="knowledge-source-info">
            <div class="knowledge-source-title">
              ${escapeHtml(item.title)}
              <span class="knowledge-source-badge ${escapeHtml(item.status.toLowerCase())}">${escapeHtml(item.status)}</span>
            </div>
            <div class="knowledge-source-meta">${escapeHtml(item.source_type)}</div>
          </div>
          <button class="btn btn-secondary btn-icon-only" data-delete-source-id="${item.id}" type="button" title="${escapeHtml(
            t("deleteSource")
          )}">
            ${iconSvg("delete")}
          </button>
        </li>
      `
      )
      .join("");
  }

  function renderSummary(markdownText) {
    const summary = getElement("knowledge-summary-output");
    if (!(summary instanceof HTMLTextAreaElement)) {
      return;
    }
    summary.value = markdownText || "";
  }

  async function loadSourcesAndSummary() {
    const projectId = selectedProjectIdFromState();
    const kbId = state.selectedKnowledgeBaseId;
    if (!projectId || !kbId) {
      renderSources([]);
      renderSummary("");
      return;
    }
    const sourcesResponse = await request(
      `/knowledge/sources?monitor_profile_id=${projectId}&knowledge_base_id=${kbId}`
    );
    const summaryResponse = await request(
      `/knowledge/summary?monitor_profile_id=${projectId}&knowledge_base_id=${kbId}`
    );
    renderSources(Array.isArray(sourcesResponse.items) ? sourcesResponse.items : []);
    renderSummary(summaryResponse.knowledge_md || "");
  }

  async function createKnowledgeBase() {
    const input = getElement("knowledge-base-name-input");
    const projectId = selectedProjectIdFromState();
    if (!(input instanceof HTMLInputElement) || !projectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const name = input.value.trim();
    if (!name) {
      throw new Error(t("errorKnowledgeBaseNameRequired"));
    }
    await request("/knowledge/bases", {
      method: "POST",
      body: JSON.stringify({ monitor_profile_id: projectId, name }),
    });
    input.value = "";
    await loadKnowledgeBases();
  }

  async function renameKnowledgeBase() {
    const kbId = state.selectedKnowledgeBaseId;
    const input = getElement("knowledge-base-rename-input");
    if (!kbId || !(input instanceof HTMLInputElement)) {
      throw new Error(t("errorSelectKnowledgeBaseFirst"));
    }
    const name = input.value.trim();
    if (!name) {
      throw new Error(t("errorNewKnowledgeBaseNameRequired"));
    }
    await request(`/knowledge/bases/${kbId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    input.value = "";
    await loadKnowledgeBases();
  }

  async function activateKnowledgeBase() {
    const kbId = state.selectedKnowledgeBaseId;
    if (!kbId) {
      throw new Error(t("errorSelectKnowledgeBaseFirst"));
    }
    await request(`/knowledge/bases/${kbId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: true }),
    });
    await loadKnowledgeBases();
  }

  async function deleteKnowledgeBase() {
    const kbId = state.selectedKnowledgeBaseId;
    if (!kbId) {
      throw new Error(t("errorSelectKnowledgeBaseFirst"));
    }
    if (!window.confirm(t("confirmDeleteKnowledgeBase"))) {
      return;
    }
    await request(`/knowledge/bases/${kbId}`, { method: "DELETE" });
    state.selectedKnowledgeBaseId = null;
    await loadKnowledgeBases();
  }

  async function uploadFileSource() {
    const projectId = selectedProjectIdFromState();
    const kbId = state.selectedKnowledgeBaseId;
    const input = getElement("knowledge-file-input");
    if (!projectId || !kbId || !(input instanceof HTMLInputElement) || !input.files || !input.files[0]) {
      throw new Error(t("errorSelectProjectKnowledgeBaseAndFile"));
    }
    const form = new FormData();
    form.append("monitor_profile_id", String(projectId));
    form.append("knowledge_base_id", String(kbId));
    form.append("file", input.files[0]);
    await requestForm("/knowledge/sources/file", form);
    input.value = "";
    await loadSourcesAndSummary();
  }

  async function addUrlSource() {
    const projectId = selectedProjectIdFromState();
    const kbId = state.selectedKnowledgeBaseId;
    const urlInput = getElement("knowledge-url-input");
    const titleInput = getElement("knowledge-url-title-input");
    if (!projectId || !kbId || !(urlInput instanceof HTMLInputElement)) {
      throw new Error(t("errorSelectProjectAndKnowledgeBase"));
    }
    const url = urlInput.value.trim();
    const title = titleInput instanceof HTMLInputElement ? titleInput.value.trim() : "";
    if (!url) {
      throw new Error(t("errorUrlRequired"));
    }
    await request("/knowledge/sources/url", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: projectId,
        knowledge_base_id: kbId,
        url,
        title,
      }),
    });
    urlInput.value = "";
    if (titleInput instanceof HTMLInputElement) {
      titleInput.value = "";
    }
    await loadSourcesAndSummary();
  }

  function bindKnowledgeSettingsControls() {
    const projectSelect = getElement("knowledge-project-select");
    const kbSelect = getElement("knowledge-base-select");
    const createBtn = getElement("create-knowledge-base-btn");
    const renameBtn = getElement("rename-knowledge-base-btn");
    const activateBtn = getElement("activate-knowledge-base-btn");
    const deleteKbBtn = getElement("delete-knowledge-base-btn");
    const uploadBtn = getElement("upload-knowledge-file-btn");
    const addUrlBtn = getElement("add-knowledge-url-btn");
    const sourceList = getElement("knowledge-source-list");

    // UI Toggle Elements
    const renameTrigger = getElement("rename-kb-trigger");
    const renameForm = getElement("kb-rename-form");
    const cancelRenameBtn = getElement("cancel-rename-btn");
    const uploadFileTrigger = getElement("upload-file-trigger");
    const fileUploadForm = getElement("file-upload-form");
    const cancelFileBtn = getElement("cancel-file-btn");
    const addUrlTrigger = getElement("add-url-trigger");
    const urlAddForm = getElement("url-add-form");
    const cancelUrlBtn = getElement("cancel-url-btn");

    if (renameTrigger && renameForm && cancelRenameBtn) {
      renameTrigger.addEventListener("click", () => {
        renameForm.classList.remove("is-hidden");
        const input = getElement("knowledge-base-rename-input");
        if (input instanceof HTMLInputElement) {
          const selectedKb = state.bases.find((b) => b.id === state.selectedKnowledgeBaseId);
          input.value = selectedKb ? selectedKb.name : "";
        }
      });
      cancelRenameBtn.addEventListener("click", () => renameForm.classList.add("is-hidden"));
    }

    if (uploadFileTrigger && fileUploadForm && cancelFileBtn) {
      uploadFileTrigger.addEventListener("click", () => {
        fileUploadForm.classList.remove("is-hidden");
        urlAddForm?.classList.add("is-hidden");
      });
      cancelFileBtn.addEventListener("click", () => fileUploadForm.classList.add("is-hidden"));
    }

    if (addUrlTrigger && urlAddForm && cancelUrlBtn) {
      addUrlTrigger.addEventListener("click", () => {
        urlAddForm.classList.remove("is-hidden");
        fileUploadForm?.classList.add("is-hidden");
      });
      cancelUrlBtn.addEventListener("click", () => urlAddForm.classList.add("is-hidden"));
    }

    if (projectSelect instanceof HTMLSelectElement) {
      projectSelect.addEventListener("change", () => {
        const parsed = Number(projectSelect.value);
        state.selectedProjectId = Number.isNaN(parsed) || !projectSelect.value ? null : parsed;
        state.selectedKnowledgeBaseId = null;
        void runTask(async () => {
          await loadKnowledgeBases();
        });
      });
    }

    if (kbSelect instanceof HTMLSelectElement) {
      kbSelect.addEventListener("change", () => {
        const parsed = Number(kbSelect.value);
        state.selectedKnowledgeBaseId = Number.isNaN(parsed) || !kbSelect.value ? null : parsed;
        void runTask(async () => {
          await loadSourcesAndSummary();
        });
      });
    }

    if (createBtn instanceof HTMLButtonElement) {
      createBtn.addEventListener("click", () => {
        void runTask(async () => {
          await createKnowledgeBase();
        }, t("knowledgeBaseCreated"));
      });
    }
    if (renameBtn instanceof HTMLButtonElement) {
      renameBtn.addEventListener("click", () => {
        void runTask(async () => {
          await renameKnowledgeBase();
          renameForm?.classList.add("is-hidden");
        }, t("libraryRenamed"));
      });
    }
    if (activateBtn instanceof HTMLButtonElement) {
      activateBtn.addEventListener("click", () => {
        void runTask(async () => {
          await activateKnowledgeBase();
        }, t("libraryActivated"));
      });
    }
    if (deleteKbBtn instanceof HTMLButtonElement) {
      deleteKbBtn.addEventListener("click", () => {
        void runTask(async () => {
          await deleteKnowledgeBase();
        }, t("libraryDeleted"));
      });
    }
    if (uploadBtn instanceof HTMLButtonElement) {
      uploadBtn.addEventListener("click", () => {
        void runTask(async () => {
          await uploadFileSource();
          fileUploadForm?.classList.add("is-hidden");
        }, t("knowledgeFileUploaded"));
      });
    }
    if (addUrlBtn instanceof HTMLButtonElement) {
      addUrlBtn.addEventListener("click", () => {
        void runTask(async () => {
          await addUrlSource();
          urlAddForm?.classList.add("is-hidden");
        }, t("knowledgeUrlAdded"));
      });
    }
    if (sourceList) {
      sourceList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }
        const button = target.closest("[data-delete-source-id]");
        if (!(button instanceof HTMLElement)) {
          return;
        }
        const sourceId = Number(button.dataset.deleteSourceId);
        if (Number.isNaN(sourceId)) {
          return;
        }
        void runTask(async () => {
          await request(`/knowledge/sources/${sourceId}`, { method: "DELETE" });
          await loadSourcesAndSummary();
        }, t("knowledgeSourceDeleted"));
      });
    }
  }

  async function loadSettings() {
    renderProjectOptions();
    await loadKnowledgeBases();
  }

  return {
    bindKnowledgeSettingsControls,
    loadSettings,
    syncProjectSelection() {
      renderProjectOptions();
    },
  };
}
