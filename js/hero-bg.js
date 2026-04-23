/**
 * Interactive backgrounds for Gordon Greco
 * 1. Hero canvas — data visualization network mesh (nodes connected by lines based on cursor proximity)
 * 2. CTA break canvas — slower ambient version of the same
 */
(function () {
  'use strict';

  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initNetworkCanvas(canvas, opts) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var width, height, dpr;
    var particles = [];
    var mouse = { x: -1000, y: -1000 };
    
    var numParticles = opts.numParticles || 60;
    var maxDistance = opts.maxDistance || 150;
    var mouseDistance = opts.mouseDistance || 200;
    var color = opts.color || '200, 169, 126'; // Gold rgb
    
    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      var rect = canvas.parentElement.getBoundingClientRect();
      width = rect.width; height = rect.height;
      canvas.width = width * dpr; canvas.height = height * dpr;
      canvas.style.width = width + 'px'; canvas.style.height = height + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      initParticles();
    }
    
    function initParticles() {
      particles = [];
      for (var i = 0; i < numParticles; i++) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          radius: Math.random() * 1.5 + 0.5
        });
      }
    }
    
    function draw() {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#0e0e0e';
      ctx.fillRect(0, 0, width, height);
      
      // Draw grid lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
      ctx.lineWidth = 1;
      var gridSize = 60;
      for (var x = (Date.now() * 0.01) % gridSize; x < width; x += gridSize) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
      }
      for (var y = (Date.now() * 0.01) % gridSize; y < height; y += gridSize) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
      }

      // Update and draw particles
      ctx.fillStyle = 'rgba(' + color + ', 0.6)';
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        
        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;
        
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
        
        for (var j = i + 1; j < particles.length; j++) {
          var p2 = particles[j];
          var dx = p.x - p2.x;
          var dy = p.y - p2.y;
          var dist = Math.sqrt(dx*dx + dy*dy);
          
          if (dist < maxDistance) {
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(' + color + ', ' + (1 - dist / maxDistance) * 0.3 + ')';
            ctx.lineWidth = 0.5;
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
        
        // Mouse interaction
        var dxm = p.x - mouse.x;
        var dym = p.y - mouse.y;
        var distm = Math.sqrt(dxm*dxm + dym*dym);
        if (distm < mouseDistance) {
          ctx.beginPath();
          ctx.strokeStyle = 'rgba(' + color + ', ' + (1 - distm / mouseDistance) * 0.6 + ')';
          ctx.lineWidth = 1;
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.stroke();
        }
      }
    }
    
    var animId = null;
    function animate() {
      draw();
      animId = requestAnimationFrame(animate);
    }
    
    canvas.addEventListener('mousemove', function(e) {
      if (reducedMotion) return;
      var rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    });
    canvas.addEventListener('mouseleave', function() {
      mouse.x = -1000;
      mouse.y = -1000;
    });
    
    var obs = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) { if (!animId && !reducedMotion) animId = requestAnimationFrame(animate); }
      else { if (animId) { cancelAnimationFrame(animId); animId = null; } }
    }, { threshold: 0 });

    resize();
    window.addEventListener('resize', resize);
    obs.observe(canvas.parentElement);
    
    if (reducedMotion) {
      draw();
    }
  }

  // Init Hero
  initNetworkCanvas(document.getElementById('hero-canvas'), {
    numParticles: window.innerWidth > 768 ? 80 : 40,
    maxDistance: 130,
    mouseDistance: 220,
    color: '200, 169, 126'
  });

  // Init CTA Sections
  document.querySelectorAll('.cta-break-canvas').forEach(function(canvas) {
    initNetworkCanvas(canvas, {
      numParticles: window.innerWidth > 768 ? 40 : 20,
      maxDistance: 100,
      mouseDistance: 150,
      color: '200, 169, 126'
    });
  });

  // Body background styles
  var style = document.createElement('style');
  style.textContent = [
    'body { background-color: #faf9f7; }',
    'section.bg-white, section.bg-gray-50 {',
    '  background-image: radial-gradient(circle, rgba(200,169,126,0.1) 1px, transparent 1px);',
    '  background-size: 32px 32px;',
    '}'
  ].join('\n');
  document.head.appendChild(style);
})();
