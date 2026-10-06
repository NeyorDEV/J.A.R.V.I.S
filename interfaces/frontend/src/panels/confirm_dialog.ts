import { wsRef } from "../ws_link";

// Popup de confirmation avant action destructrice (désinstallation, suppression...)
const confirmDialogOverlay = document.getElementById("confirm-dialog-overlay") as HTMLDivElement;
const confirmDialogMessage = document.getElementById("confirm-dialog-message") as HTMLDivElement;
const confirmDialogConfirmBtn = document.getElementById("confirm-dialog-confirm") as HTMLButtonElement;
const confirmDialogCancelBtn = document.getElementById("confirm-dialog-cancel") as HTMLButtonElement;
let confirmDialogPendingId: string | null = null;

export function showConfirmDialog(id: string, message: string) {
  confirmDialogPendingId = id;
  if (confirmDialogMessage) confirmDialogMessage.textContent = message;
  confirmDialogOverlay?.classList.remove("hidden");
}

function answerConfirmDialog(confirmed: boolean) {
  if (!confirmDialogPendingId) return;
  wsRef.current?.send(JSON.stringify({ type: "confirm_response", id: confirmDialogPendingId, confirmed }));
  confirmDialogPendingId = null;
  confirmDialogOverlay?.classList.add("hidden");
}

export function initConfirmDialog(): void {
  confirmDialogConfirmBtn?.addEventListener("click", () => answerConfirmDialog(true));
  confirmDialogCancelBtn?.addEventListener("click", () => answerConfirmDialog(false));
}
