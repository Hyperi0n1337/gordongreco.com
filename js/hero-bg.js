/**
 * Interactive backgrounds for Gordon Greco
 * 1. Hero canvas — dark gradient orbs, mouse-reactive
 * 2. CTA break canvas — same effect, smaller
 * 3. Body — CSS dot grid + subtle gradient blobs via CSS (no canvas needed)
 */
(function () {
  'use strict';

  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Shared dark-canvas renderer
  function initDarkCanvas(canvas, opts) {
    var ctx = canvas.getContext('2d');
    var width, height, dpr;
    var mouseX = 0.5, mouseY = 0.5;
    var targetMouseX = 0.5, targetMouseY = 0.5;
    var animId = null;
    var orbs = opts.orbs;

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      var rect = canvas.parentElement.getBoundingClientRect();
      width = rect.width; height = rect.height;
      canvas.width = width * dpr; canvas.height = height * dpr;
      canvas.style.width = width + 'px'; canvas.style.height = height + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawOrb(orb, time) {
      var drift = Math.sin(time * 0.0015 + orb.x * 10) * 0.03;
      var mx = (mouseX - 0.5) * 0.12;
      var my = (mouseY - 0.5) * 0.12;
      var cx = (orb.x + drift + mx * (1 - orb.r)) * width;
      var cy = (orb.y + drift * 0.7 + my * (1 - orb.r)) * height;
      var radius = orb.r * Math.max(width, height);
      var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      var c = orb.color;
      grad.addColorStop(0, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',0.3)');
      grad.addColorStop(0.5, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',0.1)');
      grad.addColorStop(1, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);
    }

    function animate(time) {
      mouseX += (targetMouseX - mouseX) * 0.06;
      mouseY += (targetMouseY - mouseY) * 0.06;
      for (var i = 0; i < orbs.length; i++) {
        orbs[i].x += orbs[i].vx;
        orbs[i].y += orbs[i].vy;
        if (orbs[i].x < -0.1 || orbs[i].x > 1.1) orbs[i].vx *= -1;
        if (orbs[i].y < -0.1 || orbs[i].y > 1.1) orbs[i].vy *= -1;
      }
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#0e0e0e';
      ctx.fillRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'screen';
      for (var i = 0; i < orbs.length; i++) drawOrb(orbs[i], time);
      ctx.globalCompositeOperation = 'source-over';
      animId = requestAnimationFrame(animate);
    }

    function onPointerMove(e) {
      var rect = canvas.getBoundingClientRect();
      targetMouseX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      targetMouseY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    }
    function onTouchMove(e) {
      if (e.touches.length > 0) {
        var rect = canvas.getBoundingClientRect();
        targetMouseX = Math.max(0, Math.min(1, (e.touches[0].clientX - rect.left) / rect.width));
        targetMouseY = Math.max(0, Math.min(1, (e.touches[0].clientY - rect.top) / rect.height));
      }
    }

    var obs = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) { if (!animId) animId = requestAnimationFrame(animate); }
      else { if (animId) { cancelAnimationFrame(animId); animId = null; } }
    }, { threshold: 0 });

    resize();
    window.addEventListener('resize', resize);
    document.addEventListener('mousemove', onPointerMove);
    document.addEventListener('touchmove', onTouchMove, { passive: true });
    obs.observe(canvas.parentElement);

    if (reducedMotion) {
      ctx.fillStyle = '#0e0e0e'; ctx.fillRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'screen';
      for (var i = 0; i < orbs.length; i++) drawOrb(orbs[i], 0);
      ctx.globalCompositeOperation = 'source-over';
    } else {
      animId = requestAnimationFrame(animate);
    }
  }

  // =============================================
  // HERO CANVAS
  // =============================================
  var heroCanvas = document.getElementById('hero-canvas');
  if (heroCanvas) {
    initDarkCanvas(heroCanvas, {
      orbs: [
        { x: 0.25, y: 0.3, r: 0.35, vx: 0.0008, vy: 0.0006, color: [200, 169, 126] },
        { x: 0.75, y: 0.6, r: 0.4,  vx: -0.0006, vy: 0.0007, color: [90, 70, 50] },
        { x: 0.5,  y: 0.8, r: 0.3,  vx: 0.0009, vy: -0.0005, color: [160, 130, 95] },
        { x: 0.3,  y: 0.7, r: 0.25, vx: -0.0007, vy: -0.0004, color: [60, 50, 40] },
        { x: 0.8,  y: 0.2, r: 0.3,  vx: 0.0005, vy: 0.0009, color: [140, 110, 75] },
      ]
    });
  }

  // =============================================
  // CTA BREAK CANVAS
  // =============================================
  var ctaCanvas = document.getElementById('cta-canvas');
  if (ctaCanvas) {
    initDarkCanvas(ctaCanvas, {
      orbs: [
        { x: 0.2, y: 0.4, r: 0.5,  vx: 0.0006, vy: 0.0004, color: [200, 169, 126] },
        { x: 0.8, y: 0.5, r: 0.45, vx: -0.0005, vy: 0.0006, color: [120, 95, 65] },
        { x: 0.5, y: 0.3, r: 0.35, vx: 0.0007, vy: -0.0003, color: [170, 140, 100] },
      ]
    });
  }

  // =============================================
  // BODY BACKGROUND — CSS-based (injected styles)
  // Dot grid via radial-gradient + floating blobs via pseudo-elements
  // =============================================
  var style = document.createElement('style');
  style.textContent = [
    // Dot grid on all light sections
    'section.bg-white, section.bg-gray-50 {',
    '  background-image: radial-gradient(circle, rgba(200,169,126,0.08) 1px, transparent 1px);',
    '  background-size: 28px 28px;',
    '}',
    // Floating gradient blobs on white sections
    'section.bg-white::before, section.bg-gray-50::before {',
    '  content: "";',
    '  position: absolute;',
    '  top: -20%;',
    '  right: -10%;',
    '  width: 50%;',
    '  height: 140%;',
    '  background: radial-gradient(ellipse at center, rgba(200,169,126,0.045) 0%, transparent 70%);',
    '  pointer-events: none;',
    '  z-index: 0;',
    '  animation: blobDrift1 25s ease-in-out infinite alternate;',
    '}',
    'section.bg-white::after, section.bg-gray-50::after {',
    '  content: "";',
    '  position: absolute;',
    '  bottom: -15%;',
    '  left: -15%;',
    '  width: 45%;',
    '  height: 130%;',
    '  background: radial-gradient(ellipse at center, rgba(200,169,126,0.035) 0%, transparent 70%);',
    '  pointer-events: none;',
    '  z-index: 0;',
    '  animation: blobDrift2 30s ease-in-out infinite alternate;',
    '}',
    // Ensure content is above blobs
    'section.bg-white > *, section.bg-gray-50 > * {',
    '  position: relative;',
    '  z-index: 1;',
    '}',
    // Make sections position relative for pseudo-elements
    'section.bg-white, section.bg-gray-50 {',
    '  position: relative;',
    '  overflow: hidden;',
    '}',
    '@keyframes blobDrift1 {',
    '  0% { transform: translate(0, 0) scale(1); }',
    '  100% { transform: translate(-5%, 8%) scale(1.1); }',
    '}',
    '@keyframes blobDrift2 {',
    '  0% { transform: translate(0, 0) scale(1); }',
    '  100% { transform: translate(6%, -5%) scale(1.05); }',
    '}',
  ].join('\n');
  document.head.appendChild(style);

  // Remove body-canvas element if present (replaced by CSS approach)
  var bodyCanvas = document.getElementById('body-canvas');
  if (bodyCanvas) bodyCanvas.remove();

})();
