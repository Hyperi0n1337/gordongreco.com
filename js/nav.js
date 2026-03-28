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
    menu.classList.toggle('hidden');
  });

  document.querySelectorAll('#mobile-menu a').forEach(function (link) {
    link.addEventListener('click', function () {
      menu.classList.add('hidden');
    });
  });
});

// Fade-in on scroll (IntersectionObserver)
document.addEventListener('DOMContentLoaded', function () {
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-in').forEach(function (el) {
    observer.observe(el);
  });
});

// IBKR Carousel — auto-slide with crossfade
document.addEventListener('DOMContentLoaded', function () {
  var slides = document.querySelectorAll('.ibkr-slide');
  var indicators = document.querySelectorAll('.ibkr-indicator');
  if (slides.length === 0) return;
  var current = 0;
  var interval = 8000;
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
});

// Form AJAX submit via Formspree
document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('lead-form');
  if (!form) return;

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
