/* PlavPay - comportamiento compartido del panel y el sitio público. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Toasts ---------- */
  function toast(message, kind) {
    var stack = document.getElementById("toast-stack");
    if (!stack) return;
    var el = document.createElement("div");
    el.className = "toast-item" + (kind === "error" ? " is-error" : "");
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    var icon = document.createElement("i");
    icon.className = "bi " + (kind === "error" ? "bi-exclamation-octagon-fill" : "bi-check-circle-fill");
    var text = document.createElement("span");
    text.textContent = message;
    el.appendChild(icon);
    el.appendChild(text);
    stack.appendChild(el);
    setTimeout(function () {
      el.classList.add("is-leaving");
      setTimeout(function () { el.remove(); }, 300);
    }, 3200);
  }
  window.plavToast = toast;

  /* ---------- Confirmación propia (reemplaza window.confirm) ---------- */
  var dialog = document.getElementById("confirm-dialog");

  function askConfirm(message, onAccept) {
    if (!dialog || typeof dialog.showModal !== "function") {
      if (window.confirm(message)) onAccept();
      return;
    }
    dialog.querySelector("[data-confirm-message]").textContent = message;
    dialog.returnValue = "";
    dialog.addEventListener("close", function handler() {
      dialog.removeEventListener("close", handler);
      if (dialog.returnValue === "accept") onAccept();
    });
    dialog.showModal();
  }

  // Formularios normales: <form data-confirm="¿Seguro?">
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm || form.dataset.confirmed) return;
    event.preventDefault();
    askConfirm(form.dataset.confirm, function () {
      form.dataset.confirmed = "1";
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.submit();
    });
  }, true);

  // Formularios HTMX: hx-confirm usa este diálogo en lugar del nativo
  document.addEventListener("htmx:confirm", function (event) {
    if (!event.detail.question) return;
    event.preventDefault();
    askConfirm(event.detail.question, function () { event.detail.issueRequest(true); });
  });

  /* ---------- Respuesta visual a los cambios HTMX ---------- */
  document.addEventListener("htmx:afterSwap", function () {
    if (reduceMotion) return;
    document.querySelectorAll("[data-flash-on-swap]").forEach(function (el) {
      el.classList.remove("swap-flash");
      void el.offsetWidth;
      el.classList.add("swap-flash");
    });
  });

  document.addEventListener("htmx:afterRequest", function (event) {
    if (event.detail && !event.detail.successful && event.detail.xhr && event.detail.xhr.status !== 0) {
      toast("No se pudo completar la acción. Inténtalo de nuevo.", "error");
    }
  });
  document.addEventListener("htmx:sendError", function () {
    toast("Sin conexión con el servidor. Revisa tu red.", "error");
  });

  /* ---------- Copiar al portapapeles ---------- */
  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-copy]");
    if (!btn) return;
    var value = btn.getAttribute("data-copy");
    var done = function () { toast("Enlace copiado"); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(done, function () { toast("No se pudo copiar el enlace", "error"); });
    } else {
      var tmp = document.createElement("textarea");
      tmp.value = value;
      document.body.appendChild(tmp);
      tmp.select();
      try { document.execCommand("copy"); done(); } catch (e) { toast("No se pudo copiar el enlace", "error"); }
      tmp.remove();
    }
  });

  /* ---------- Mostrar / ocultar contraseña ---------- */
  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-toggle-password]");
    if (!btn) return;
    var input = document.querySelector(btn.getAttribute("data-toggle-password"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
    var icon = btn.querySelector(".bi");
    if (icon) icon.className = "bi " + (show ? "bi-eye-slash" : "bi-eye");
  });

  /* ---------- Filtro en vivo del catálogo ---------- */
  document.addEventListener("input", function (event) {
    var input = event.target.closest("[data-filter]");
    if (!input) return;
    var query = input.value.trim().toLowerCase();
    var scope = document.querySelector(input.getAttribute("data-filter"));
    if (!scope) return;
    var shown = 0;
    scope.querySelectorAll("[data-filter-text]").forEach(function (item) {
      var match = item.getAttribute("data-filter-text").toLowerCase().indexOf(query) !== -1;
      item.hidden = !match;
      if (match) shown += 1;
    });
    scope.querySelectorAll("[data-filter-group]").forEach(function (group) {
      group.hidden = !group.querySelector("[data-filter-text]:not([hidden])");
    });
    var empty = document.querySelector("[data-filter-empty]");
    if (empty) empty.hidden = shown !== 0;
  });

  /* ---------- Conteo animado de cifras (una vez, al cargar el tablero) ---------- */
  function countUp(el) {
    var target = parseFloat(el.getAttribute("data-countup"));
    if (isNaN(target) || reduceMotion) return;
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var duration = 900;
    var start = null;
    function fmt(n) { return n.toFixed(decimals); }
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = fmt(target);
    }
    requestAnimationFrame(step);
  }
  document.querySelectorAll("[data-countup]").forEach(countUp);
})();
