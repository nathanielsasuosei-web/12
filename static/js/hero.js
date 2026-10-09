// Animated equaliser bars behind the hero. Skipped when the visitor prefers reduced motion.
(function () {
  var canvas = document.getElementById("hero-canvas");
  if (!canvas || !canvas.getContext) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var ctx = canvas.getContext("2d");
  var bars = 56;
  var start = performance.now();
  var width = 0, height = 0, dpr = 1;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function level(i, t) {
    // Layered sine waves give a loose, beat-like movement without audio input.
    var x = i / bars;
    var a = Math.sin(t * 2.1 + x * 9.0) * 0.5 + 0.5;
    var b = Math.sin(t * 3.7 - x * 14.0 + 1.3) * 0.5 + 0.5;
    var kick = Math.pow(Math.max(0, Math.sin(t * 2.4)), 6);
    return Math.min(1, 0.18 + a * 0.35 + b * 0.25 + kick * 0.35 * (1 - x));
  }

  function frame(now) {
    var t = (now - start) / 1000;
    ctx.clearRect(0, 0, width, height);
    var gap = 6;
    var barWidth = (width - gap * (bars - 1)) / bars;
    for (var i = 0; i < bars; i++) {
      var h = level(i, t) * height * 0.9;
      var x = i * (barWidth + gap);
      var grad = ctx.createLinearGradient(0, height - h, 0, height);
      grad.addColorStop(0, "rgba(255, 59, 77, 0.85)");
      grad.addColorStop(1, "rgba(127, 10, 20, 0.15)");
      ctx.fillStyle = grad;
      ctx.fillRect(x, height - h, barWidth, h);
    }
    requestAnimationFrame(frame);
  }

  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(frame);
})();
