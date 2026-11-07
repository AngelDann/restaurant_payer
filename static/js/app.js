document.body.addEventListener("htmx:afterSwap", function (event) {
  if (event.detail && event.detail.target) {
    event.detail.target.classList.add("border-success");
  }
});

document.body.addEventListener("htmx:afterRequest", function (event) {
  if (event.detail && !event.detail.successful) {
    console.warn("HTMX request failed", event.detail);
  }
});
