/* Duplicate-confirmation dialog: close with Escape, the backdrop or the back button. */
(() => {
  const modal = document.querySelector("[data-modal]");
  if (!modal) return;

  const close = () => {
    document.body.classList.remove("overflow-hidden");
    modal.remove();
  };

  document.body.classList.add("overflow-hidden");

  modal.querySelectorAll("[data-modal-close]").forEach((element) => {
    element.addEventListener("click", close);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });

  // Keep the safe option focused so Enter does not save a duplicate by accident.
  modal.querySelector("button[data-modal-close]")?.focus();
})();
