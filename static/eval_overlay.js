     
     
     
(function () {
  var overlay = document.getElementById('evalOverlay');
  if (!overlay) return;
  var steps = overlay.querySelectorAll('.ax-eval-step');
  var bar = document.getElementById('evalBar');
  var timer = null;

  window.showEvalOverlay = function () {
    overlay.classList.add('ax-on');
    var i = 0;
    steps.forEach(function (s) { s.classList.remove('ax-active', 'ax-done'); });
    bar.style.width = '0%';
    function advance() {
      if (i > 0) {
        steps[i - 1].classList.remove('ax-active');
        steps[i - 1].classList.add('ax-done');
      }
      if (i < steps.length) {
        steps[i].classList.add('ax-active');
        bar.style.width = Math.round(((i + 1) / steps.length) * 100) + '%';
        i++;
        timer = setTimeout(advance, 320 + Math.random() * 260);
      } else {
        timer = setTimeout(advance, 600);   // hold at complete
      }
    }
    advance();
  };

     
  window.addEventListener('pageshow', function () {
    overlay.classList.remove('ax-on');
    if (timer) clearTimeout(timer);
  });
})();