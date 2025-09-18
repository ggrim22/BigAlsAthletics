
const modal = new bootstrap.Modal(document.getElementById("htmx-modal"));

htmx.on("htmx:afterSwap", (e) => {
  if (e.detail.target.id == "dialog") {
    modal.show();
  };
});

htmx.on("htmx:beforeSwap", (e) => {
  if (e.detail.target.id == "dialog" && !e.detail.xhr.response) {
    modal.hide();
    e.detail.shouldSwap = false;
  };
});

htmx.on("hidden.bs.modal", () => {
  document.getElementById("dialog").innerHTML = "";
});

htmx.on("shown.bs.modal", () => {
  var modal = document.getElementById("dialog");
  var form = modal.getElementsByTagName("form")[0];

  if (form) {
    var inputs = form.getElementsByTagName("input");
    
    for (let i = 0; i < inputs.length; i++) {
      var input = inputs.item(i);
      if (input.getAttribute("type") === "hidden") {
        continue;
      } else {
        input.focus();
        break;
      };
    };
  };
});
