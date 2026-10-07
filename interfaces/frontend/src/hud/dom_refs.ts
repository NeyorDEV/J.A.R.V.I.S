// Références DOM du HUD partagées entre modules (extraites de main.ts).

// ── DOM refs ──────────────────────────────────────────────────────────────────
export const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
export const statusEl = document.getElementById("status-text") as HTMLDivElement;
export const errorEl = document.getElementById("error-text") as HTMLDivElement;
export const badgeEl = document.getElementById("connection-badge") as HTMLDivElement;
export const badgeLabelEl = document.getElementById(
  "connection-label"
) as HTMLSpanElement;
export const muteButtonEl = document.getElementById("mute-button") as HTMLButtonElement;
export const micBtnEl = document.getElementById("mic-btn") as HTMLButtonElement;
export const jarvisMenuBtn = document.getElementById("jarvis-menu-btn") as HTMLButtonElement;
export const jarvisMenuDropdown = document.getElementById("jarvis-menu-dropdown") as HTMLDivElement;
export const apiKeysButtonEl = document.getElementById("api-keys-button") as HTMLButtonElement;
export const apiKeysCloseBtn = document.getElementById("api-keys-close-btn") as HTMLSpanElement;
export const apiKeysSaveBtn = document.getElementById("api-keys-save-btn") as HTMLButtonElement;
export const helpOverlayEl = document.getElementById("help-overlay") as HTMLDivElement;
export const timerHudEl = document.getElementById("timer-hud") as HTMLDivElement;
export const timerDisplayEl = document.getElementById("timer-display") as HTMLDivElement;
export const timerProgressEl = document.getElementById("timer-progress") as HTMLDivElement;
export const subtitleToggleButtonEl = document.getElementById("subtitle-toggle") as HTMLButtonElement;
export const keyboardToggleButtonEl = document.getElementById("keyboard-toggle") as HTMLButtonElement;
export const keyboardHudEl = document.getElementById("keyboard-hud") as HTMLDivElement;
export const keyboardInputEl = document.getElementById("keyboard-input") as HTMLInputElement;
export const visualizerHudEl = document.getElementById("visualizer-hud") as HTMLDivElement;

export const settingsButtonEl = document.getElementById("settings-button") as HTMLButtonElement;
export const settingsModalEl = document.getElementById("settings-modal") as HTMLDivElement;
export const haToggleBtn = document.getElementById("ha-toggle-btn") as HTMLButtonElement;
export const haPanel = document.getElementById("ha-panel") as HTMLDivElement;
export const settingsCloseBtn = document.getElementById("settings-close-btn") as HTMLSpanElement;
export const settingsNameEl = document.getElementById("settings-name") as HTMLInputElement;
export const settingsAgeEl = document.getElementById("settings-age") as HTMLInputElement;
export const settingsAppsListEl = document.getElementById("settings-apps-list") as HTMLDivElement;
export const appAddNameEl = document.getElementById("app-add-name") as HTMLInputElement;
export const appAddPathEl = document.getElementById("app-add-path") as HTMLInputElement;
export const appAddBtn = document.getElementById("app-add-btn") as HTMLButtonElement;
export const settingsSaveBtn = document.getElementById("settings-save-btn") as HTMLButtonElement;

// New settings fields DOM refs
export const settingsMicSelect = document.getElementById("settings-mic") as HTMLSelectElement;
export const settingsCameraSelect = document.getElementById("settings-camera") as HTMLSelectElement;
export const settingsMusiqueLien = document.getElementById("settings-musique-lien") as HTMLInputElement;
export const appDetectBtn = document.getElementById("app-detect-btn") as HTMLButtonElement;
export const appDetectSelect = document.getElementById("app-detect-select") as HTMLSelectElement;

// (Refs courses extraites dans panels/shopping_panel.ts)
// Swarm 3D Command Center Modal DOM refs
export const swarmLoungeHud = document.getElementById("swarm-lounge-hud") as HTMLDivElement;
export const swarmLoungeClose = document.getElementById("swarm-lounge-close") as HTMLButtonElement;
export const swarmTerminalLogs = document.getElementById("swarm-terminal-logs") as HTMLDivElement;
