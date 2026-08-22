// A reward amount only makes sense on paid projects.
(function () {
  var form = document.getElementById("project-form");
  if (!form) return;

  var budgetField = document.getElementById("budget-field");
  var budgetInput = budgetField.querySelector("input");

  function sync() {
    var picked = form.querySelector('input[name="project_type"]:checked');
    var paid = picked && picked.value !== "experience";
    budgetField.hidden = !paid;
    budgetInput.disabled = !paid;
    if (!paid) budgetInput.value = "";
  }

  form.querySelectorAll('input[name="project_type"]').forEach(function (radio) {
    radio.addEventListener("change", sync);
  });

  sync();
})();
