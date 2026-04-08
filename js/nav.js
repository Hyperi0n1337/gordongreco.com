// Copyright year
document.addEventListener('DOMContentLoaded', function () {
  var el = document.getElementById('copyright-year');
  if (el) el.textContent = new Date().getFullYear();
});

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('mobile-menu-btn');
  var menu = document.getElementById('mobile-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', function () {
    var isNowVisible = !menu.classList.contains('hidden');
    if (isNowVisible) {
      menu.classList.add('hidden');
    } else {
      menu.classList.remove('hidden');
      var links = menu.querySelectorAll('a');
      links.forEach(function(link, i) {
        link.style.opacity = '0';
        link.style.transform = 'translateY(10px)';
        link.style.transition = 'none';
        void link.offsetWidth; // force reflow
        link.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        setTimeout(function() {
          link.style.opacity = '1';
          link.style.transform = 'translateY(0)';
        }, i * 60 + 50);
      });
    }
  });

  document.querySelectorAll('#mobile-menu a').forEach(function (link) {
    link.addEventListener('click', function () {
      menu.classList.add('hidden');
    });
  });
});

// Navigation Shrink & Scroll Progress
document.addEventListener('DOMContentLoaded', function () {
  var nav = document.querySelector('nav');
  var progress = document.createElement('div');
  progress.className = 'scroll-progress-container';
  progress.innerHTML = '<div class="scroll-progress-bar" id="scroll-progress-bar"></div>';
  if (nav) {
      nav.appendChild(progress);
      var bar = document.getElementById('scroll-progress-bar');
      window.addEventListener('scroll', function () {
          if (window.scrollY > 50) {
              nav.classList.add('nav-compressed');
          } else {
              nav.classList.remove('nav-compressed');
          }
          
          var winScroll = document.body.scrollTop || document.documentElement.scrollTop;
          var height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
          var scrolled = height ? (winScroll / height) * 100 : 0;
          if (bar) bar.style.width = scrolled + '%';
      }, { passive: true });
  }
});

// IntersectionObserver Animations (Stagger & Fade)
document.addEventListener('DOMContentLoaded', function () {
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-in, .slide-up, .mask-reveal').forEach(function (el) {
    observer.observe(el);
  });
  
  // Staggered reveals
  var staggerGroups = document.querySelectorAll('.stagger-group');
  staggerGroups.forEach(function(group) {
     var items = group.querySelectorAll('.stagger-item');
     var og = new IntersectionObserver(function(entries) {
         entries.forEach(function(entry) {
             if (entry.isIntersecting) {
                 items.forEach(function(item, idx) {
                     item.style.transitionDelay = (idx * 0.1) + 's';
                     item.classList.add('visible');
                 });
                 og.unobserve(entry.target);
             }
         });
     }, {threshold: 0.1});
     og.observe(group);
  });
});

// IBKR Carousel — auto-slide and parallax waves
document.addEventListener('DOMContentLoaded', function () {
  var slides = document.querySelectorAll('.ibkr-slide');
  var indicators = document.querySelectorAll('.ibkr-indicator');
  if (slides.length === 0) return;
  var current = 0;
  var interval = 5000;
  var timer;

  function goTo(idx) {
    slides[current].classList.remove('ibkr-slide-active');
    indicators[current].classList.remove('ibkr-indicator-active');
    current = idx;
    slides[current].classList.add('ibkr-slide-active');
    indicators[current].classList.add('ibkr-indicator-active');
  }

  function next() {
    goTo((current + 1) % slides.length);
  }

  function startTimer() {
    timer = setInterval(next, interval);
  }

  indicators.forEach(function (btn, idx) {
    btn.addEventListener('click', function () {
      clearInterval(timer);
      goTo(idx);
      startTimer();
    });
  });

  var carousel = document.querySelector('.ibkr-carousel');
  if (carousel) {
    carousel.addEventListener('mouseenter', function () { clearInterval(timer); });
    carousel.addEventListener('mouseleave', startTimer);
  }

  startTimer();
  
  // Parallax waves
  var waves = document.querySelectorAll('.ibkr-bg-wave');
  if (waves.length > 0) {
      window.addEventListener('scroll', function() {
          var yOffset = window.scrollY * 0.15;
          waves[0].style.transform = 'translateY(' + yOffset + 'px)';
          if(waves[1]) waves[1].style.transform = 'translateY(' + (yOffset * 1.5) + 'px)';
          if(waves[2]) waves[2].style.transform = 'translateY(' + (yOffset * 0.8) + 'px)';
      }, {passive:true});
  }
});

// Form AJAX submit via Formspree and Floating Labels Logic
document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('lead-form');
  if (!form) return;

  var inputs = form.querySelectorAll('.form-input');
  inputs.forEach(function(input) {
      if(!input.placeholder) input.placeholder = " "; // Required for floating label CSS trick
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = form.querySelector('button[type="submit"]');
    var origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Sending...';

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'Accept': 'application/json' }
    }).then(function (response) {
      if (response.ok) {
        form.classList.add('hidden');
        document.getElementById('thank-you').classList.remove('hidden');
      } else {
        btn.disabled = false;
        btn.textContent = origText;
        alert('Something went wrong. Please try again or email us directly.');
      }
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = origText;
      alert('Network error. Please try again or email us directly.');
    });
  });
});
