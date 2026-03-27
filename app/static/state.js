function initialState() {
  return {
    profiles: [],
    selectedProfileId: null,
    videos: [],
    selectedVideoId: null,
    tokenInputs: {
      markets: [],
      languages: [],
    },
    transcriptExpanded: false,
    searchCandidates: [],
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
