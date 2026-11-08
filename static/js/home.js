/* Portada: demostración interactiva de la cuenta en mesa. */
(function () {
  "use strict";

  var phone = document.querySelector("[data-demo-phone]");
  if (!phone) return;

  var SUBTOTAL = 450;
  var tipLine = phone.querySelector("[data-demo-tip]");
  var totalLine = phone.querySelector("[data-demo-total]");

  function money(n) { return "$" + n.toFixed(2); }

  function update() {
    var chosen = phone.querySelector("input[name='demo-tip']:checked");
    var pct = chosen ? parseFloat(chosen.value) : 0;
    var tip = SUBTOTAL * pct / 100;
    tipLine.textContent = money(tip);
    totalLine.textContent = money(SUBTOTAL + tip);
  }

  phone.addEventListener("change", update);
  update();

  // El teléfono se inclina hacia el cursor (solo con puntero fino y sin reducir movimiento).
  var fine = window.matchMedia("(pointer: fine)").matches;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var stage = phone.closest("[data-demo-stage]");
  if (!stage || !fine || reduce) return;

  stage.addEventListener("pointermove", function (event) {
    var rect = stage.getBoundingClientRect();
    var x = (event.clientX - rect.left) / rect.width - 0.5;
    var y = (event.clientY - rect.top) / rect.height - 0.5;
    phone.style.setProperty("--ry", (x * 12).toFixed(2) + "deg");
    phone.style.setProperty("--rx", (-y * 10).toFixed(2) + "deg");
  });
  stage.addEventListener("pointerleave", function () {
    phone.style.setProperty("--ry", "0deg");
    phone.style.setProperty("--rx", "0deg");
  });
})();
