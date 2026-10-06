// ── Recipe Modal Logic ───────────────────────────────────────────────────────
export function initRecipePanel(): void {

  const recipeModal = document.getElementById("recipe-modal");
  const closeRecipeBtn = document.getElementById("close-recipe");
  const recipeHeader = document.getElementById("recipe-header");

  if (closeRecipeBtn && recipeModal) {
    closeRecipeBtn.addEventListener("click", () => {
      recipeModal.classList.add("hidden");
    });
  }
  // Drag & Drop for Recipe Modal
  if (recipeModal && recipeHeader) {
    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    recipeHeader.addEventListener("mousedown", (e) => {
      isDragging = true;
      const rect = recipeModal.getBoundingClientRect();
      offsetX = e.clientX - rect.left;
      offsetY = e.clientY - rect.top;
      recipeModal.style.cursor = "grabbing";
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
    
      // Prevent dragging outside the window
      let newX = e.clientX - offsetX;
      let newY = e.clientY - offsetY;
    
      // Boundaries
      const maxX = window.innerWidth - recipeModal.offsetWidth;
      const maxY = window.innerHeight - recipeModal.offsetHeight;
    
      newX = Math.max(0, Math.min(newX, maxX));
      newY = Math.max(0, Math.min(newY, maxY));

      recipeModal.style.left = `${newX}px`;
      recipeModal.style.top = `${newY}px`;
      recipeModal.style.transform = "none"; // disable original translation for dragging
    });

    document.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        recipeModal.style.cursor = "default";
      }
    });
  }
}
