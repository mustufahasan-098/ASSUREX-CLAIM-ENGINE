// AssureX CSRF helper: injects the token into every form on the page.
// Forms rendered server-side get the token via the meta tag; this runs
// once per page load, before any submit can happen.
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function (form) {
      if (form.querySelector('input[name="csrf_token"]')) return;
      var input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'csrf_token';
      input.value = meta.content;
      form.appendChild(input);
    });
  });
})();