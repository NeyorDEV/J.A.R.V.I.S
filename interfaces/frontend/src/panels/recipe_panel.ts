// ── Panneau recette (style verre : css/13 et css/14) ─────────────────────────
import { makePanelDraggable } from "../ui/draggable";

export function initRecipePanel(): void {
  const recipeModal = document.getElementById("recipe-modal");
  const closeRecipeBtn = document.getElementById("close-recipe");
  const recipeHeader = document.getElementById("recipe-header");

  if (closeRecipeBtn && recipeModal) {
    closeRecipeBtn.addEventListener("click", () => {
      recipeModal.classList.add("hidden");
      recipeModal.classList.remove("visible");
    });
  }
  if (recipeModal && recipeHeader) {
    makePanelDraggable(recipeModal as HTMLDivElement, recipeHeader as HTMLDivElement);
  }
}
