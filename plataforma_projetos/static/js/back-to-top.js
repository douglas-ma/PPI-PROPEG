document.addEventListener('DOMContentLoaded', function () {
  var button = document.getElementById('back-to-top');
  if (!button) return;

  var mainContent = document.getElementById('main-content');
  var updateScheduled = false;

  function currentScrollPosition() {
    return Math.max(
      window.scrollY || 0,
      document.documentElement.scrollTop || 0,
      mainContent ? mainContent.scrollTop : 0
    );
  }

  function updateVisibility() {
    updateScheduled = false;
    button.classList.toggle('is-visible', currentScrollPosition() > 280);
  }

  function scheduleVisibilityUpdate() {
    if (updateScheduled) return;
    updateScheduled = true;
    window.requestAnimationFrame(updateVisibility);
  }

  window.addEventListener('scroll', scheduleVisibilityUpdate, { passive: true });
  window.addEventListener('resize', scheduleVisibilityUpdate, { passive: true });
  if (mainContent) {
    mainContent.addEventListener('scroll', scheduleVisibilityUpdate, { passive: true });
  }

  button.addEventListener('click', function () {
    var behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    window.scrollTo({ top: 0, behavior: behavior });
    document.documentElement.scrollTo({ top: 0, behavior: behavior });
    if (mainContent) mainContent.scrollTo({ top: 0, behavior: behavior });
  });

  updateVisibility();
});
