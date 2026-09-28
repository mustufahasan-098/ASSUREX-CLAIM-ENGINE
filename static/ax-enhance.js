/* ═══════════════════════════════════════════════════════
   AssureX Enhancement Layer — progressive, opt-out safe
   • Aurora background w/ parallax + particle network
   • Scroll progress beam + reveal-on-scroll
   • 3D card tilt + magnetic buttons + click ripples
   • Count-up stat numbers
   Everything checks element existence first; zero errors
   if markup differs. Respects prefers-reduced-motion.
   ═══════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 1 · aurora background ---------- */
  var bg = document.createElement('div');
  bg.className = 'ax-bg';
  bg.innerHTML =
    '<div class="ax-bg__parallax">' +
      '<div class="ax-bg__blob ax-bg__blob--1"></div>' +
      '<div class="ax-bg__blob ax-bg__blob--2"></div>' +
      '<div class="ax-bg__blob ax-bg__blob--3"></div>' +
    '</div>' +
    '<div class="ax-bg__grid"></div>' +
    '<div class="ax-bg__noise"></div>';
  document.body.appendChild(bg);

  /* particle canvas */
  var canvas = document.createElement('canvas');
  canvas.className = 'ax-bg__canvas';
  bg.appendChild(canvas);
  var ctx = canvas.getContext('2d');
  var parts = [], W, H;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  var COUNT = window.innerWidth < 700 ? 28 : 55;
  for (var i = 0; i < COUNT; i++) {
    parts.push({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - .5) * .35,
      vy: (Math.random() - .5) * .35,
      r: Math.random() * 1.6 + .4
    });
  }

  function drawParticles() {
    if (reduced) return;
    ctx.clearRect(0, 0, W, H);
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, 6.29);
      ctx.fillStyle = 'rgba(140,160,255,.35)';
      ctx.fill();
      // connections
      for (var j = i + 1; j < parts.length; j++) {
        var q = parts[j];
        var dx = p.x - q.x, dy = p.y - q.y;
        var d = dx * dx + dy * dy;
        if (d < 15000) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = 'rgba(124,92,255,' + (0.12 * (1 - d / 15000)) + ')';
          ctx.lineWidth = .6;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(drawParticles);
  }
  if (!reduced) drawParticles();

  /* cursor parallax */
  if (!reduced) {
    document.addEventListener('mousemove', function (e) {
      var px = (e.clientX / window.innerWidth - .5);
      var py = (e.clientY / window.innerHeight - .5);
      bg.style.setProperty('--ax-px', px.toFixed(3));
      bg.style.setProperty('--ax-py', py.toFixed(3));
    }, { passive: true });
  }

  /* ---------- 2 · scroll progress beam ---------- */
  var prog = document.createElement('div');
  prog.className = 'ax-progress';
  document.body.appendChild(prog);
  window.addEventListener('scroll', function () {
    var h = document.documentElement;
    var p = h.scrollTop / (h.scrollHeight - h.clientHeight || 1);
    prog.style.transform = 'scaleX(' + p + ')';
  }, { passive: true });

  /* ---------- 3 · reveal on scroll ---------- */
  if ('IntersectionObserver' in window && !reduced) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('ax-in'); io.unobserve(en.target); }
      });
    }, { threshold: .12 });
    document.querySelectorAll('.ax-reveal-s').forEach(function (el) { io.observe(el); });
  }

  /* ---------- 4 · 3D card tilt ---------- */
  if (!reduced && window.matchMedia('(pointer:fine)').matches) {
    document.querySelectorAll('.ax-card, .ax-model-card').forEach(function (card) {
      card.addEventListener('mousemove', function (e) {
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - .5;
        var y = (e.clientY - r.top) / r.height - .5;
        card.style.transform =
          'perspective(900px) rotateY(' + (x * 5) + 'deg) rotateX(' + (-y * 5) + 'deg) translateY(-3px)';
      });
      card.addEventListener('mouseleave', function () {
        card.style.transform = '';
      });
    });
  }

  /* ---------- 5 · magnetic buttons ---------- */
  if (!reduced && window.matchMedia('(pointer:fine)').matches) {
    document.querySelectorAll('.ax-btn, .ax-btn-login').forEach(function (btn) {
      btn.addEventListener('mousemove', function (e) {
        var r = btn.getBoundingClientRect();
        btn.style.setProperty('--ax-mx', ((e.clientX - r.left - r.width / 2) * .18) + 'px');
        btn.style.setProperty('--ax-my', ((e.clientY - r.top - r.height / 2) * .3) + 'px');
      });
      btn.addEventListener('mouseleave', function () {
        btn.style.setProperty('--ax-mx', '0px');
        btn.style.setProperty('--ax-my', '0px');
      });
    });
  }

  /* ---------- 6 · click ripple ---------- */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.ax-btn, .ax-btn-login');
    if (!btn || reduced) return;
    var r = btn.getBoundingClientRect();
    var rip = document.createElement('span');
    rip.className = 'ax-ripple';
    var size = Math.max(r.width, r.height) * 2;
    rip.style.width = rip.style.height = size + 'px';
    rip.style.left = (e.clientX - r.left - size / 2) + 'px';
    rip.style.top = (e.clientY - r.top - size / 2) + 'px';
    btn.appendChild(rip);
    setTimeout(function () { rip.remove(); }, 700);
  });

  /* ---------- 7 · count-up stats ---------- */
  if (!reduced && 'IntersectionObserver' in window) {
    var so = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        so.unobserve(en.target);
        var el = en.target;
        var end = parseFloat(el.textContent.replace(/[^\d.]/g, ''));
        if (isNaN(end) || end === 0) return;
        var suffix = el.textContent.replace(/[\d.,]/g, '');
        var start = 0, t0 = null, dur = 900;
        function tick(t) {
          if (!t0) t0 = t;
          var p = Math.min((t - t0) / dur, 1);
          var eased = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(end * eased).toLocaleString() + suffix;
          if (p < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      });
    }, { threshold: .5 });
    document.querySelectorAll('.ax-stat-value').forEach(function (el) { so.observe(el); });
  }

  /* ---------- 8 · back-to-top ---------- */
  var top = document.createElement('button');
  top.className = 'ax-top-btn';
  top.innerHTML = '↑';
  top.title = 'Back to top';
  document.body.appendChild(top);
  top.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
  });
  window.addEventListener('scroll', function () {
    top.classList.toggle('ax-show', window.scrollY > 400);
  }, { passive: true });
})();