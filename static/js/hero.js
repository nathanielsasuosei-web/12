// Animated hero background: a glowing red equalizer that breathes to a fake beat, plus drifting embers.
(function () {
  var canvas = document.getElementById("hero-canvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var width = 0, height = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
  var particles = [];
  var bars = 64;
  var start = performance.now();

  function resize() {
    var rect = canvas.getBoundingClientRect();
    width = rect.width;
    height = rect.height;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    particles = [];
    var count = Math.min(70, Math.round(width / 22));
    for (var i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.8 + 0.4,
        vy: -(Math.random() * 0.25 + 0.05),
        hue: 350 + Math.random() * 25, // red → orange embers
        a: Math.random() * 0.6 + 0.2
      });
    }
  }

  function drawBars(t) {
    var barWidth = width / bars;
    var base = height * 0.82;
    ctx.save();
    ctx.shadowColor = "rgba(255,30,44,0.55)";
    ctx.shadowBlur = 18;
    for (var i = 0; i < bars; i++) {
      var pos = i / bars;
      var beat = Math.pow(Math.max(0, Math.sin(t * 3.1)), 8) * 0.6;
      var wave = (Math.sin(t * 1.7 + pos * 9) + Math.sin(t * 2.9 - pos * 13) + 2) / 4;
      var h = height * (0.08 + 0.42 * wave * (0.55 + beat) * (0.35 + 0.65 * Math.sin(pos * Math.PI)));
      var grad = ctx.createLinearGradient(0, base - h, 0, base);
      grad.addColorStop(0, "rgba(255,210,63,0.95)");
      grad.addColorStop(0.35, "rgba(255,90,20,0.85)");
      grad.addColorStop(1, "rgba(255,30,44,0.15)");
      ctx.fillStyle = grad;
      var x = i * barWidth + barWidth * 0.2;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, base - h, barWidth * 0.6, h, 4) : ctx.rect(x, base - h, barWidth * 0.6, h);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawParticles() {
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.y += p.vy;
      if (p.y < -4) { p.y = height + 4; p.x = Math.random() * width; }
      ctx.beginPath();
      ctx.fillStyle = "hsla(" + p.hue + ", 95%, 60%, " + p.a + ")";
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function frame(now) {
    var t = (now - start) / 1000;
    ctx.clearRect(0, 0, width, height);
    drawParticles();
    drawBars(t);
    if (!reduceMotion) requestAnimationFrame(frame);
  }

  window.addEventListener("resize", function () { resize(); });
  resize();
  requestAnimationFrame(frame);
})();
