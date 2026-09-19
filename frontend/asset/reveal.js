/* reveal.js — subtelne scroll-reveal (IntersectionObserver)
   Automatycznie oznacza sekcje klasą .rv i odsłania przy wejściu w viewport.
   Zero zależności; respektuje prefers-reduced-motion.
*/
(function () {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var SEL = '.hgrid, .statline, .prt-section-head, .bgrid > *, .ad-slot, .discover-search, .discover-tags';
  function init() {
    var els = document.querySelectorAll(SEL + ':not(.rv-done)');
    if (!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('rv-in');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    els.forEach(function (el, i) {
      el.classList.add('rv');
      el.style.transitionDelay = Math.min((i % 6) * 60, 240) + 'ms';
      io.observe(el);
      el.classList.add('rv-done');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
