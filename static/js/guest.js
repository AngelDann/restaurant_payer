/* PlavPay - comportamiento de la experiencia del comensal. */
(function () {
  "use strict";

  var body = document.body;
  var csrf = body.getAttribute("data-csrf") || "";

  /* ---------- Calificación con estrellas ---------- */
  var LABELS = { 1: "Pésimo", 2: "Malo", 3: "Regular", 4: "Bueno", 5: "Excelente" };

  function paintStars(upTo, cls) {
    document.querySelectorAll(".guest-star-btn").forEach(function (btn, idx) {
      btn.classList.toggle(cls, idx < upTo);
    });
  }

  function selectRating(rating) {
    var input = document.getElementById("selected-overall-rating");
    if (!input) return;
    input.value = rating;
    paintStars(rating, "active");
    paintStars(0, "hover");
    document.querySelectorAll(".guest-star-btn").forEach(function (btn, idx) {
      btn.setAttribute("aria-pressed", idx + 1 === rating ? "true" : "false");
    });
    var label = document.getElementById("star-label-text");
    if (label) label.textContent = LABELS[rating] || "";

    var root = document.querySelector("[data-rating]");
    if (rating >= 4 && root && root.getAttribute("data-has-google") === "true") {
      setTimeout(openGoogleModal, 300);
    }
  }

  var starsRow = document.getElementById("stars-container");
  if (starsRow) {
    starsRow.addEventListener("click", function (event) {
      var btn = event.target.closest(".guest-star-btn");
      if (btn) selectRating(parseInt(btn.getAttribute("data-star"), 10));
    });
    starsRow.addEventListener("pointerover", function (event) {
      var btn = event.target.closest(".guest-star-btn");
      if (btn && event.pointerType === "mouse") paintStars(parseInt(btn.getAttribute("data-star"), 10), "hover");
    });
    starsRow.addEventListener("pointerleave", function () { paintStars(0, "hover"); });
  }

  /* ---------- Modal de Google Maps ---------- */
  var gModal = document.getElementById("google-maps-modal");
  var lastFocus = null;

  function openGoogleModal() {
    if (!gModal) return;
    lastFocus = document.activeElement;
    gModal.classList.add("open");
    gModal.setAttribute("aria-hidden", "false");
    var first = gModal.querySelector("a, button");
    if (first) first.focus();
  }
  function closeGoogleModal() {
    if (!gModal) return;
    gModal.classList.remove("open");
    gModal.setAttribute("aria-hidden", "true");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  if (gModal) {
    gModal.addEventListener("click", function (event) {
      if (event.target === gModal || event.target.closest("[data-close-google]")) closeGoogleModal();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && gModal.classList.contains("open")) closeGoogleModal();
    });
    var confirm = gModal.querySelector("[data-google-confirm]");
    if (confirm) {
      confirm.addEventListener("click", function () {
        var url = gModal.getAttribute("data-track-url");
        var rating = document.getElementById("selected-overall-rating");
        if (url) {
          fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              "X-CSRFToken": csrf,
              "X-Requested-With": "XMLHttpRequest"
            },
            body: new URLSearchParams({
              overall_rating: rating ? rating.value : "5",
              redirected_to_google: "true"
            })
          });
        }
        closeGoogleModal();
      });
    }
  }

  /* ---------- Calificar platillos (pulgares) ---------- */
  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-thumb]");
    if (!btn) return;
    var dish = btn.getAttribute("data-dish");
    var type = btn.getAttribute("data-thumb");
    var input = document.getElementById("input-dish-" + dish);
    var up = document.getElementById("btn-up-" + dish);
    var down = document.getElementById("btn-down-" + dish);
    if (!input || !up || !down) return;

    var value = type === "up" ? "1" : "0";
    var same = input.value === value;
    input.value = same ? "" : value;
    up.classList.toggle("active", !same && type === "up");
    down.classList.toggle("active", !same && type === "down");
    up.setAttribute("aria-pressed", String(!same && type === "up"));
    down.setAttribute("aria-pressed", String(!same && type === "down"));
  });

  /* ---------- Mostrar u ocultar bloques (monto de propina) ---------- */
  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-toggle]");
    if (!btn) return;
    var target = document.querySelector(btn.getAttribute("data-toggle"));
    if (!target) return;
    target.hidden = !target.hidden;
    btn.setAttribute("aria-expanded", String(!target.hidden));
    if (!target.hidden) {
      var field = target.querySelector("input");
      if (field) field.focus();
    }
  });

  /* ---------- Menú: conserva el scroll al agregar y marca la categoría visible ---------- */
  var menuRoot = document.querySelector("[data-menu]");
  if (menuRoot) {
    var key = "plav-menu-scroll:" + location.pathname;
    var saved = sessionStorage.getItem(key);
    if (saved !== null) {
      sessionStorage.removeItem(key);
      window.scrollTo(0, parseInt(saved, 10) || 0);
      var bar = document.querySelector(".guest-floating-bottom");
      if (bar) bar.classList.add("is-bumped");
    }
    document.addEventListener("htmx:beforeRequest", function () {
      sessionStorage.setItem(key, String(window.scrollY));
    });

    var pills = Array.prototype.slice.call(document.querySelectorAll(".guest-cat-pill"));
    var sections = pills.map(function (p) { return document.querySelector(p.getAttribute("href")); });
    if (pills.length && "IntersectionObserver" in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var idx = sections.indexOf(entry.target);
          pills.forEach(function (p, i) { p.classList.toggle("active", i === idx); });
          var active = pills[idx];
          if (active && active.scrollIntoView) active.scrollIntoView({ block: "nearest", inline: "center" });
        });
      }, { rootMargin: "-130px 0px -65% 0px" });
      sections.forEach(function (s) { if (s) observer.observe(s); });
    }
  }
})();
