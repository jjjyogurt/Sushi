import { getElement } from "./ui-utils.js";

export function createAgentSettingsController({ request, runTask }) {
  const state = {
    maxChars: 0,
    defaultContent: "",
  };

  function updateMeta(contentLength) {
    const metaElement = getElement("agent-settings-meta");
    if (!metaElement) {
      return;
    }
    if (state.maxChars > 0) {
      metaElement.textContent = `${contentLength}/${state.maxChars} chars`;
      return;
    }
    metaElement.textContent = `${contentLength} chars`;
  }

  async function loadSettings() {
    const input = getElement("agent-settings-input");
    if (!(input instanceof HTMLTextAreaElement)) {
      return;
    }

    const payload = await request("/agent-settings");
    const content = String(payload.content || "");
    state.maxChars = Number(payload.max_chars || 0);
    state.defaultContent = String(payload.default_content || "");
    input.value = content;
    updateMeta(content.length);
  }

  async function saveSettings() {
    const input = getElement("agent-settings-input");
    if (!(input instanceof HTMLTextAreaElement)) {
      return;
    }

    const payload = await request("/agent-settings", {
      method: "PUT",
      body: JSON.stringify({ content: input.value }),
    });
    const saved = String(payload.content || "");
    input.value = saved;
    updateMeta(saved.length);
  }

  async function resetSettings() {
    const input = getElement("agent-settings-input");
    if (!(input instanceof HTMLTextAreaElement)) {
      return;
    }

    const payload = await request("/agent-settings/reset", { method: "POST" });
    const resetValue = String(payload.content || "");
    state.defaultContent = String(payload.default_content || resetValue);
    input.value = resetValue;
    updateMeta(resetValue.length);
  }

  function bindAgentSettingsControls() {
    const input = getElement("agent-settings-input");
    const saveButton = getElement("save-agent-settings-btn");
    const resetButton = getElement("reset-agent-settings-btn");
    if (!(input instanceof HTMLTextAreaElement) || !(saveButton instanceof HTMLButtonElement)) {
      return;
    }

    input.addEventListener("input", () => {
      updateMeta(input.value.length);
    });

    saveButton.addEventListener("click", () => {
      void runTask(async () => {
        await saveSettings();
      }, "Agent settings saved.");
    });

    if (resetButton instanceof HTMLButtonElement) {
      resetButton.addEventListener("click", () => {
        void runTask(async () => {
          await resetSettings();
        }, "Agent settings reset.");
      });
    }
  }

  return {
    bindAgentSettingsControls,
    loadSettings,
  };
}
