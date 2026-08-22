// Show only the fields that belong to the selected account type.
(function () {
  var form = document.getElementById("signup");
  if (!form) return;

  var groups = form.querySelectorAll(".field-group");

  function sync() {
    var picked = form.querySelector('input[name="role"]:checked');
    var role = picked ? picked.value : "student";
    groups.forEach(function (group) {
      var mine = group.dataset.role === role;
      group.hidden = !mine;
      group.querySelectorAll("input").forEach(function (input) {
        input.disabled = !mine;
      });
    });
  }

  form.querySelectorAll('input[name="role"]').forEach(function (radio) {
    radio.addEventListener("change", sync);
  });

  sync();
})();
