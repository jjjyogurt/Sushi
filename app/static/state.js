function initialState() {
  return {
    profiles: [],
    selectedProfileId: null,
    openProjectMenuId: null,
    editingProjectId: null,
    videos: [],
    selectedVideoId: null,
    currentUser: null,
    appUsers: [],
    tokenInputs: {
      markets: [],
      languages: [],
      keyProducts: [],
    },
    editTokenInputs: {
      markets: [],
      languages: [],
      keyProducts: [],
    },
    analysisLanguageByVideoId: {},
    transcriptExpanded: false,
    searchCandidates: [],
    newVideoIds: [],
  };
}

let state = initialState();

export function getState() {
  return state;
}

export function setState(patchOrUpdater) {
  state =
    typeof patchOrUpdater === "function"
      ? patchOrUpdater(state)
      : {
          ...state,
          ...patchOrUpdater,
        };
  return state;
}

export function resetState() {
  state = initialState();
  return state;
}
