(() => {
  const state = document.getElementById("connection-state");
  const machineList = document.getElementById("machine-list");
  const eventList = document.getElementById("event-list");
  const taskList = document.getElementById("dashboard-task-list");
  const alertList = document.getElementById("supervision-alert-list");

  const text = (value) => String(value ?? "");

  const formatDate = (value) => {
    if (!value) return "-";
    const date = new Date(value + (value.endsWith("Z") ? "" : "Z"));
    return Number.isNaN(date.getTime())
      ? value
      : date.toLocaleString("fr-FR");
  };

  function setStat(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function renderMachines(clients) {
    if (!machineList) return;
    machineList.replaceChildren();

    if (!clients.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Aucune machine enregistrée.";
      machineList.appendChild(empty);
      return;
    }

    clients.forEach((client) => {
      const row = document.createElement("a");
      row.className = "machine-row";
      row.href = `/machines/${client.id}`;

      const avatar = document.createElement("div");
      avatar.className = "machine-avatar";
      avatar.textContent =
        text(client.name).slice(0, 1).toUpperCase() || "?";

      const main = document.createElement("div");
      main.className = "machine-main";

      const name = document.createElement("strong");
      name.textContent = text(client.name);

      const subtitle = document.createElement("span");
      subtitle.textContent =
        `${text(client.hostname)} · ${text(client.group_name)}`;

      main.append(name, subtitle);

      const meta = document.createElement("div");
      meta.className = "machine-meta";

      const chip = document.createElement("span");
      chip.className = `health-chip ${text(client.health)}`;
      chip.textContent = text(client.health_label);

      const details = document.createElement("small");
      details.textContent =
        `RAM ${text(client.ram_gb)} Go · ` +
        `Disque ${text(client.disk_used_percent)} %`;

      meta.append(chip, details);
      row.append(avatar, main, meta);
      machineList.appendChild(row);
    });
  }

  function renderEvents(events) {
    if (!eventList) return;
    eventList.replaceChildren();

    if (!events.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Aucun événement récent.";
      eventList.appendChild(empty);
      return;
    }

    events.forEach((event) => {
      const item = document.createElement("div");
      item.className = "timeline-item";

      const dot = document.createElement("span");
      dot.className =
        `timeline-dot ${text(event.level).toLowerCase()}`;

      const body = document.createElement("div");
      const title = document.createElement("div");
      title.className = "timeline-title";
      title.textContent =
        `${text(event.hostname)} · ${text(event.event_type)}`;

      const message = document.createElement("p");
      message.textContent = text(event.message);

      const date = document.createElement("small");
      date.textContent = formatDate(event.created_at);

      body.append(title, message, date);
      item.append(dot, body);
      eventList.appendChild(item);
    });
  }

  function renderTasks(tasks) {
    if (!taskList) return;
    taskList.replaceChildren();

    if (!tasks.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Aucune tâche récente.";
      taskList.appendChild(empty);
      return;
    }

    const labels = {
      pending: "En attente",
      running: "En cours",
      success: "Succès",
      failed: "Échec",
      cancelled: "Annulée"
    };

    tasks.forEach((task) => {
      const row = document.createElement("a");
      row.className = "dashboard-task-row";
      row.href = `/tasks/${task.uuid}`;

      const left = document.createElement("div");
      const machine = document.createElement("strong");
      machine.textContent = text(task.machine);
      const action = document.createElement("span");
      action.textContent = text(task.action_type);
      left.append(machine, action);

      const right = document.createElement("div");
      const status = document.createElement("span");
      status.className = `task-status task-${text(task.status)}`;
      status.textContent =
        labels[task.status] || text(task.status);

      const date = document.createElement("small");
      date.textContent = formatDate(task.created_at);

      right.append(status, date);
      row.append(left, right);
      taskList.appendChild(row);
    });
  }

  function addAlert(kind, alert, severity, subtitle) {
    const row = document.createElement("a");
    row.className = `supervision-alert ${severity}`;
    row.href = `/machines/${alert.client_id}`;

    const label = document.createElement("span");
    label.textContent = kind;

    const machine = document.createElement("strong");
    machine.textContent = text(alert.machine);

    row.append(label, machine);

    if (subtitle) {
      const small = document.createElement("small");
      small.textContent = subtitle;
      row.appendChild(small);
    }

    alertList.appendChild(row);
  }

  function renderAlerts(alerts) {
    if (!alertList) return;
    alertList.replaceChildren();

    (alerts.disk || []).forEach((alert) => {
      addAlert(
        "Disque critique",
        alert,
        "danger",
        `${text(alert.used_percent)} % utilisé · ` +
        `${text(alert.free_gb)} Go libres`
      );
    });

    (alerts.long_offline || []).forEach((alert) => {
      addAlert(
        "Hors ligne depuis plus de 24 h",
        alert,
        "danger",
        formatDate(alert.last_seen)
      );
    });

    (alerts.stale_inventory || []).forEach((alert) => {
      addAlert(
        "Inventaire obsolète ou absent",
        alert,
        "warning",
        alert.updated_at
          ? formatDate(alert.updated_at)
          : "Aucun inventaire"
      );
    });

    (alerts.missing_agent_version || []).forEach((alert) => {
      addAlert(
        "Version Agent absente",
        alert,
        "warning",
        ""
      );
    });

    if (!alertList.children.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Aucune alerte prioritaire.";
      alertList.appendChild(empty);
    }
  }

  function update(snapshot) {
    setStat("stat-clients", snapshot.stats.clients);
    setStat("stat-online", snapshot.stats.online);
    setStat("stat-offline", snapshot.stats.offline);
    setStat("stat-warnings", snapshot.stats.warnings);
    setStat("stat-health", `${snapshot.stats.fleet_health} %`);
    setStat("stat-inventory", `${snapshot.stats.inventory_coverage} %`);
    setStat(
      "stat-success-rate",
      `${snapshot.stats.success_rate_24h} %`
    );
    setStat("stat-failed-24h", snapshot.stats.failed_24h);
    setStat("stat-disk-used", `${snapshot.stats.disk_used_percent} % utilisé`);
    setStat("stat-disk-free", snapshot.stats.disk_free_gb);
    setStat("stat-disk-total", snapshot.stats.disk_total_gb);
    setStat("stat-ram", snapshot.stats.ram_gb);

    const diskBar = document.getElementById("disk-capacity-bar");
    if (diskBar) {
      diskBar.style.width =
        `${Math.min(snapshot.stats.disk_used_percent, 100)}%`;
      diskBar.classList.toggle(
        "critical",
        snapshot.stats.disk_used_percent >= 90
      );
    }

    setStat(
      "dashboard-task-pending",
      snapshot.tasks?.counters?.pending ?? 0
    );
    setStat(
      "dashboard-task-running",
      snapshot.tasks?.counters?.running ?? 0
    );
    setStat(
      "dashboard-task-success",
      snapshot.tasks?.counters?.success ?? 0
    );
    setStat(
      "dashboard-task-failed",
      snapshot.tasks?.counters?.failed ?? 0
    );

    renderMachines(snapshot.clients || []);
    renderEvents(snapshot.events || []);
    renderTasks(snapshot.tasks?.recent || []);
    renderAlerts(snapshot.alerts || {});
  }

  function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(
      `${protocol}://${location.host}/ws/dashboard`
    );

    socket.addEventListener("open", () => {
      state.classList.remove("disconnected");
      state.querySelector("span:last-child").textContent =
        "Temps réel connecté";
    });

    socket.addEventListener("message", (event) => {
      update(JSON.parse(event.data));
    });

    socket.addEventListener("close", () => {
      state.classList.add("disconnected");
      state.querySelector("span:last-child").textContent =
        "Reconnexion…";
      window.setTimeout(connect, 3000);
    });

    socket.addEventListener("error", () => socket.close());
  }

  connect();
})();
