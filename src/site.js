/* Enlarge a drawing, and print a plan. This file makes no network requests. */
(function () {
  var printButton = document.querySelector(".js-print");
  if (printButton) {
    printButton.addEventListener("click", function () {
      window.print();
    });
  }

  var dialog = document.getElementById("lightbox");
  if (!dialog || typeof dialog.showModal !== "function") return;

  var scroll = dialog.querySelector(".lightbox-scroll");
  var img = dialog.querySelector("img");
  var closeButton = dialog.querySelector(".lightbox-close");
  var fitButton = dialog.querySelector(".lightbox-fit");
  var actual = false;

  function center() {
    scroll.scrollLeft = Math.max(0, (scroll.scrollWidth - scroll.clientWidth) / 2);
    scroll.scrollTop = Math.max(0, (scroll.scrollHeight - scroll.clientHeight) / 2);
  }

  function applySize() {
    img.classList.toggle("is-actual", actual);
    img.classList.toggle("is-fit", !actual);
    fitButton.textContent = actual ? "Fit on screen" : "Actual size";
  }

  function openDrawing(link) {
    var source = link.querySelector("img");
    actual = window.matchMedia("(max-width: 720px)").matches;
    applySize();
    img.alt = source ? source.alt : "";
    img.onload = function () {
      applySize();
      center();
    };
    img.src = link.getAttribute("href");
    if (img.complete && img.naturalWidth) {
      applySize();
      center();
    }
    dialog.showModal();
  }

  document.querySelectorAll("a.drawing-link").forEach(function (link) {
    link.addEventListener("click", function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
        return;
      }
      event.preventDefault();
      openDrawing(link);
    });
  });

  fitButton.addEventListener("click", function () {
    actual = !actual;
    applySize();
    center();
  });

  closeButton.addEventListener("click", function () {
    dialog.close();
  });

  scroll.addEventListener("click", function (event) {
    if (event.target === scroll) dialog.close();
  });

  dialog.addEventListener("close", function () {
    img.removeAttribute("src");
    img.alt = "";
  });
})();
