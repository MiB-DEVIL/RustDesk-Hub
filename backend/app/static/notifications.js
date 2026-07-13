(function () {
  const badge = document.getElementById("notification-badge");
  if (!badge) return;

  async function refreshNotificationBadge() {
    try {
      const response = await fetch("/api/notifications/summary", {
        credentials: "same-origin",
        cache: "no-store",
      });

      if (!response.ok) return;

      const data = await response.json();
      const total = Number(data?.counts?.total || 0);
      const critical = Number(data?.counts?.critical || 0);

      if (total <= 0) {
        badge.hidden = true;
        badge.textContent = "0";
        badge.classList.remove("critical");
        return;
      }

      badge.hidden = false;
      badge.textContent = total > 99 ? "99+" : String(total);
      badge.classList.toggle("critical", critical > 0);
    } catch (error) {
      console.debug("Notifications indisponibles", error);
    }
  }

  refreshNotificationBadge();
  window.setInterval(refreshNotificationBadge, 15000);
})();
