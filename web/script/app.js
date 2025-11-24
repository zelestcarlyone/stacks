// Stacks Dashboard JavaScript

// ============================================================================
// GLOBAL STATE
// ============================================================================

let lastData = "{}";
let lastLog = "{}";
let consoleInterval = null;
const md5Regex = /[a-fA-F0-9]{32}/;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleString();
}

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + " " + sizes[i];
}

function colorize(line) {
  const template = document.getElementById("log-line-template");
  const clone = template.content.firstElementChild.cloneNode(true);

  const parts = line.split("] ");
  if (parts.length < 3) {
    clone.querySelector(".log-message").textContent = line;
    return clone;
  }

  const date = parts[0] + "]";
  const level = parts[1] + "]";
  const logger = parts[2] + "]";
  const message = parts.slice(3).join("] ");

  // Fill in template fields
  clone.querySelector(".log-date").textContent = date;
  clone.querySelector(".log-class").textContent = level;
  clone.querySelector(".log-logger").textContent = logger;
  clone.querySelector(".log-message").textContent = message;

  // Add level-specific class
  if (level.includes("[DEBUG")) clone.querySelector(".log-class").classList.add("debug");
  else if (level.includes("[INFO")) clone.querySelector(".log-class").classList.add("info");
  else if (level.includes("[WARNING") || level.includes("[WARN")) clone.querySelector(".log-class").classList.add("warning");
  else if (level.includes("[ERROR")) clone.querySelector(".log-class").classList.add("error");

  return clone;
}

// Extract MD5 from either MD5 string or URL
function extractMD5(input) {
  const match = input.match(md5Regex);
  return match ? match[0].toLowerCase() : null;
}

// ============================================================================
// API HELPER FUNCTIONS
// ============================================================================

function apiHeaders() {
  return {
    "Content-Type": "application/json",
  };
}

function apiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    credentials: "same-origin", // Always include session cookie
    headers: {
      ...apiHeaders(),
      ...(options.headers || {}),
    },
  });
}

// ============================================================================
// API FUNCTIONS - VERSION & STATUS
// ============================================================================

function getVersion() {
  fetch("/api/version")
    .then((r) => r.json())
    .then((data) => {
      document.getElementById("version").innerHTML = "Version " + data.version;
      document.getElementById("version").classList.add("visible");
    })
    .catch((err) => console.error("Failed to load version:", err));
}

function updateStatus() {
  apiFetch("/api/status")
    .then((r) => {
      if (r.status === 401 || r.status === 403) {
        console.error("Session authentication failed. Status:", r.status);
        window.location.href = "/login";
        throw new Error("Authentication failed - redirecting to login");
      }
      return r.json();
    })
    .then((data) => {
      // Only update when there is a change in data
      const newDataString = JSON.stringify(data);
      if (lastData == newDataString) {
        return;
      } else {
        lastData = newDataString;
      }

      // Update stats
      const successCount = data.recent_history.filter((h) => h.success).length;
      const failCount = data.recent_history.filter((h) => !h.success).length;

      document.getElementById("stat-queue").textContent = data.queue_size;
      document.getElementById("stat-success").textContent = successCount;
      document.getElementById("stat-failed").textContent = failCount;

      // Update fast download stat
      const fastCard = document.getElementById("stat-fast-card");
      if (data.fast_download && data.fast_download.available) {
        const downloadsLeft = data.fast_download.downloads_left;
        const downloadsPerDay = data.fast_download.downloads_per_day;
        if (downloadsLeft !== null && downloadsPerDay !== null) {
          document.getElementById("stat-fast").textContent = `${downloadsLeft}/${downloadsPerDay}`;
          fastCard.style.display = "block";
        } else {
          fastCard.style.display = "none";
        }
      } else {
        fastCard.style.display = "none";
      }

      // Update current download
      const currentDiv = document.getElementById("current-download");
      if (data.current) {
        const progress = data.current.progress || {};
        const percent = progress.percent || 0;
        const downloaded = formatBytes(progress.downloaded || 0);
        const total = formatBytes(progress.total_size || 0);

        document.getElementById("current-title").textContent = data.current.title;
        document.getElementById("current-md5").textContent = data.current.md5;
        document.getElementById("current-time").textContent = "Started: " + formatTime(data.current.started_at);
        document.getElementById("current-progress-bar").style.width = percent + "%";
        document.getElementById("current-progress-text").textContent = `${percent.toFixed(1)}% - ${downloaded} / ${total}`;
        currentDiv.style.display = "block";
      } else {
        currentDiv.style.display = "none";
      }

      // Update queue
      document.getElementById("queue-count").textContent = data.queue_size;
      updateQueueList(data.queue);

      // Update history
      document.getElementById("history-count").textContent = data.recent_history.length;
      updateHistoryList(data.recent_history);
    })
    .catch((err) => console.error("Failed to update status:", err));
}

// ============================================================================
// API FUNCTIONS - CONSOLE/LOGS
// ============================================================================

function updateConsole() {
  apiFetch("/api/logs")
    .then((r) => {
      if (r.status === 401 || r.status === 403) {
        window.location.href = "/login";
        throw new Error("Authentication failed");
      }
      return r.json();
    })
    .then((data) => {
      const box = document.getElementById("console");

      // If nothing changed, skip DOM ops
      const joined = data.lines.join("\n");
      if (joined === lastLog) return;
      lastLog = joined;

      // Clear the container
      box.innerHTML = "";

      // Append each log line as a DOM node
      data.lines.forEach((line) => {
        box.appendChild(colorize(line));
      });

      // Auto-scroll
      box.scrollTop = box.scrollHeight;
    });
}

function activateConsoleTab() {
  // Start polling
  if (!consoleInterval) {
    updateConsole();
    consoleInterval = setInterval(updateConsole, 1000);
  }
}

function deactivateConsoleTab() {
  // Stop polling
  if (consoleInterval) {
    clearInterval(consoleInterval);
    consoleInterval = null;
  }
}

// ============================================================================
// API FUNCTIONS - QUEUE
// ============================================================================

function removeFromQueue(md5) {
  apiFetch("/api/queue/remove", {
    method: "POST",
    body: JSON.stringify({ md5: md5 }),
  })
    .then((r) => r.json())
    .then(() => updateStatus())
    .catch((err) => console.error("Failed to remove item:", err));
}

function clearQueue() {
  apiFetch("/api/queue/clear", { method: "POST" })
    .then((r) => r.json())
    .then(() => updateStatus())
    .catch((err) => console.error("Failed to clear queue:", err));
}

function addDownload() {
  const input = document.getElementById("manual-add");
  const value = input.value.trim();

  if (!value) {
    toasts.show({
      title: "Add Download",
      message: "Please enter an MD5 or URL",
      type: "error",
    });
    return;
  }

  // Extract MD5 from input
  const md5 = extractMD5(value);

  if (!md5) {
    toasts.show({
      title: "Add Download",
      message: "No valid MD5 found in input",
      type: "error",
    });
    return;
  }
  apiFetch("/api/queue/add", {
    method: "POST",
    body: JSON.stringify({
      md5: md5,
      title: null,
      source: "manual",
    }),
  })
    .then((r) => {
      if (r.status === 401 || r.status === 403) {
        throw new Error("Authentication failed. Please refresh the page.");
      }
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${r.statusText}`);
      }
      return r.json();
    })
    .then((data) => {
      if (data.success) {
        toasts.show({
          title: "Add Download",
          message: `Successfully added ${md5} to queue`,
          type: "success",
        });
        input.value = "";
        updateStatus();
      } else {
        toasts.show({
          title: "Add Download",
          message: data.message || "Failed to add to queue",
          type: "error",
        });
      }
    })
    .catch((err) => {
      console.error("Failed to add download:", err);
      toasts.show({
        title: "Add Download",
        message: "Error: " + err.message,
        type: "error",
      });
    });
}

// ============================================================================
// API FUNCTIONS - HISTORY
// ============================================================================

function clearHistory() {
  apiFetch("/api/history/clear", { method: "POST" })
    .then((r) => r.json())
    .then(() => updateStatus())
    .catch((err) => console.error("Failed to clear history:", err));
}

function retryFailed(md5) {
  apiFetch("/api/history/retry", {
    method: "POST",
    body: JSON.stringify({ md5: md5 }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        updateStatus();
      } else {
        toasts.show({
          title: "Retry",
          message: data.message || "Failed to retry",
          type: "error",
        });
      }
    })
    .catch((err) => console.error("Failed to retry download:", err));
}

// ============================================================================
// API FUNCTIONS - SETTINGS
// ============================================================================

function loadSettings() {
  // Load and display API key
  apiFetch("/api/key")
    .then((r) => r.json())
    .then((data) => {
      document.getElementById("display-api-key").value = data.api_key;
    })
    .catch((err) => {
      console.error("Failed to load API key:", err);
      document.getElementById("display-api-key").value = "Error loading key";
    });

  apiFetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      // Login credentials
      document.getElementById("setting-authentification-enabled").checked = !config.login?.disable;
      document.getElementById("setting-username").value = config.login?.username || "";
      document.getElementById("setting-new-password").value = "";

      // Downloads
      document.getElementById("setting-delay").value = config.downloads?.delay || 2;
      document.getElementById("setting-retry-count").value = config.downloads?.retry_count || 3;
      document.getElementById("setting-resume-attempts").value = config.downloads?.resume_attempts || 3;

      // Fast Download
      document.getElementById("setting-fast-enabled").checked = !!config.fast_download?.enabled;
      document.getElementById("setting-fast-key").value = config.fast_download?.key || "";

      // FlareSolverr
      document.getElementById("setting-flaresolverr-enabled").checked = !!config.flaresolverr?.enabled;
      document.getElementById("setting-flaresolverr-url").value = config.flaresolverr?.url || "http://localhost:8191";
      document.getElementById("setting-flaresolverr-timeout").value = config.flaresolverr?.timeout || 60;

      // Queue
      document.getElementById("setting-max-history").value = config.queue?.max_history || 100;

      // Logging
      document.getElementById("setting-log-level").value = config.logging?.level || "WARNING";
    })
    .catch((err) => console.error("Failed to load settings:", err));
}

function saveSettings() {
  const newPassword = document.getElementById("setting-new-password").value;

  const config = {
    downloads: {
      delay: parseInt(document.getElementById("setting-delay").value),
      retry_count: parseInt(document.getElementById("setting-retry-count").value),
      resume_attempts: parseInt(document.getElementById("setting-resume-attempts").value),
    },
    fast_download: {
      enabled: document.getElementById("setting-fast-enabled").checked,
      key: document.getElementById("setting-fast-key").value || null,
    },
    flaresolverr: {
      enabled: document.getElementById("setting-flaresolverr-enabled").checked,
      url: document.getElementById("setting-flaresolverr-url").value || "http://localhost:8191",
      timeout: parseInt(document.getElementById("setting-flaresolverr-timeout").value) || 60,
    },
    queue: {
      max_history: parseInt(document.getElementById("setting-max-history").value),
    },
    logging: {
      level: document.getElementById("setting-log-level").value,
    },
    login: {
      username: document.getElementById("setting-username").value,
      disable: !document.getElementById("setting-authentification-enabled").checked,
    },
  };

  // Only include password if it's been changed
  if (newPassword) {
    config.login.new_password = newPassword;
  }

  apiFetch("/api/config", {
    method: "POST",
    body: JSON.stringify(config),
  })
    .then((r) => {
      if (r.status === 401 || r.status === 403) {
        throw new Error("Session authentication failed. Please refresh the page.");
      }
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${r.statusText}`);
      }
      return r.json();
    })
    .then((data) => {
      if (data.success) {
        if (newPassword) {
          toasts.show({
            title: "Settings",
            message: "Settings saved successfully! Your password has been updated. Changes are now active.",
            type: "success",
          });
        } else {
          toasts.show({
            title: "Settings",
            message: "Settings saved successfully! Changes are now active.",
            type: "success",
          });
        }
        document.getElementById("setting-new-password").value = "";
      } else {
        toasts.show({
          title: "Settings",
          message: "Failed to save settings: " + (data.error || "Unknown error"),
          type: "error",
        });
      }
    })
    .catch((err) => {
      console.error("Failed to save settings:", err);
      toasts.show({
        title: "Settings",
        message: "Failed to save settings: " + err.message,
        type: "error",
      });
    });
}

function regenerateApiKey() {
  apiFetch("/api/key/regenerate", {
    method: "POST",
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        document.getElementById("display-api-key").value = data.api_key;
        toasts.show({
          title: "API Key",
          message: "New API key generated!\n\nDon't forget to update your external tools with the new key.",
          type: "success",
        });
      } else {
        toasts.show({
          title: "API Key",
          message: "Failed to regenerate API key: " + (data.error || "Unknown error"),
          type: "error",
        });
      }
    })
    .catch((err) => {
      console.error("Failed to regenerate API key:", err);
      toasts.show({
        title: "API Key",
        message: "Failed to regenerate API key: " + err.message,
        type: "error",
      });
    });
}

function testFastKey() {
  const key = document.getElementById("setting-fast-key").value;
  const resultDiv = document.getElementById("key-test-result");

  if (!key) {
    resultDiv.className = "test-result error";
    resultDiv.textContent = "Please enter a key first";
    return;
  }

  resultDiv.className = "test-result";
  resultDiv.textContent = "Testing key...";
  resultDiv.style.display = "block";

  apiFetch("/api/config/test_key", {
    method: "POST",
    body: JSON.stringify({ key: key }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        resultDiv.className = "test-result success";
        resultDiv.textContent = `✓ Key is valid! Downloads available: ${data.downloads_left}/${data.downloads_per_day}`;
      } else {
        resultDiv.className = "test-result error";
        resultDiv.textContent = `✗ ${data.error}`;
      }
    })
    .catch((err) => {
      resultDiv.className = "test-result error";
      resultDiv.textContent = `✗ Connection error: ${err.message}`;
    });
}

function testFlaresolverr() {
  const url = document.getElementById("setting-flaresolverr-url").value;
  const timeout = parseInt(document.getElementById("setting-flaresolverr-timeout").value) || 10;
  const resultDiv = document.getElementById("flaresolverr-test-result");

  if (!url) {
    resultDiv.className = "test-result error";
    resultDiv.textContent = "Please enter a FlareSolverr URL first";
    return;
  }

  resultDiv.className = "test-result";
  resultDiv.textContent = "Testing connection...";
  resultDiv.style.display = "block";

  apiFetch("/api/config/test_flaresolverr", {
    method: "POST",
    body: JSON.stringify({ url: url, timeout: timeout }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        resultDiv.className = "test-result success";
        resultDiv.textContent = `✓ ${data.message}`;
      } else {
        resultDiv.className = "test-result error";
        resultDiv.textContent = `✗ ${data.error}`;
      }
    })
    .catch((err) => {
      resultDiv.className = "test-result error";
      resultDiv.textContent = `✗ Connection error: ${err.message}`;
    });
}

// ============================================================================
// UI UPDATE FUNCTIONS
// ============================================================================

function updateQueueList(queue) {
  const queueList = document.getElementById("queue-list");

  if (queue.length === 0) {
    queueList.innerHTML = document.getElementById("queue-empty-template").innerHTML;
    return;
  }

  // Clear list
  queueList.innerHTML = "";

  // Get template
  const template = document.getElementById("queue-item-template");

  // Add each item
  queue.forEach((item) => {
    const clone = template.content.cloneNode(true);
    const listItem = clone.querySelector(".list-item");

    clone.querySelector(".item-title").textContent = item.title;
    clone.querySelector(".item-md5").textContent = item.md5;
    clone.querySelector(".item-time").textContent = "Added: " + formatTime(item.added_at);

    const removeBtn = clone.querySelector(".btn-danger");
    removeBtn.onclick = () => removeFromQueue(item.md5);

    queueList.appendChild(clone);
  });
}

function updateHistoryList(history) {
  const historyList = document.getElementById("history-list");

  if (history.length === 0) {
    historyList.innerHTML = document.getElementById("history-empty-template").innerHTML;
    return;
  }

  // Clear list
  historyList.innerHTML = "";

  // Get template
  const template = document.getElementById("history-item-template");

  // Add each item
  history.forEach((item) => {
    const clone = template.content.cloneNode(true);

    // Status icon
    const statusIcon = clone.querySelector(".item-status-icon");
    if (item.success) {
      statusIcon.textContent = "✓";
      statusIcon.className = "item-status-icon success-icon";
    } else {
      statusIcon.textContent = "✗";
      statusIcon.className = "item-status-icon error-icon";
    }

    // Title
    clone.querySelector(".item-title-text").textContent = item.title;

    // Method icon (fast vs mirror)
    const methodIcon = clone.querySelector(".item-method-icon");
    if (item.success && item.used_fast_download) {
      methodIcon.textContent = "⚡";
      methodIcon.title = "Fast";
      methodIcon.style.fontSize = "0.8em";
      methodIcon.style.opacity = "0.7";
    } else if (item.success) {
      methodIcon.textContent = "🌐";
      methodIcon.title = "Mirror";
      methodIcon.style.fontSize = "0.8em";
      methodIcon.style.opacity = "0.7";
    } else {
      methodIcon.textContent = "";
    }

    // MD5 and time
    clone.querySelector(".item-md5").textContent = item.md5;
    clone.querySelector(".item-time").textContent = formatTime(item.completed_at);

    // Error message (if failed)
    if (item.error) {
      const errorDiv = clone.querySelector(".item-error");
      errorDiv.textContent = item.error;
      errorDiv.style.display = "block";
    }

    // Retry button (if failed)
    if (!item.success) {
      const retryBtn = clone.querySelector(".retry-btn");
      retryBtn.style.display = "inline-block";
      retryBtn.onclick = () => retryFailed(item.md5);
    }

    historyList.appendChild(clone);
  });
}

// ============================================================================
// EVENT HANDLERS & INITIALIZATION
// ============================================================================

// Tab switching
document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    const tabName = button.dataset.tab;

    // Update buttons
    document.querySelectorAll(".tab-button").forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");

    // Update content
    document.querySelectorAll(".tab-content").forEach((content) => content.classList.remove("active"));
    document.getElementById(`${tabName}-tab`).classList.add("active");

    // Load settings when switching to settings tab
    if (tabName === "settings") {
      loadSettings();
    } else if (tabName === "console") {
      updateConsole();
    }
  });
});

// Add download button handler
document.querySelector(".add-item .btn-success").addEventListener("click", addDownload);

// Add download on Enter key
document.getElementById("manual-add").addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    addDownload();
  }
});

// Console tab polling (legacy interval)
setInterval(() => {
  const consoleTab = document.getElementById("console-tab");
  if (consoleTab && consoleTab.classList.contains("active")) {
    updateConsole();
  }
}, 1000);

// Clipboard initialization
document.addEventListener("DOMContentLoaded", () => {
  const clipboard = new ClipboardJS('[data-clipboard-action="copy"]');
  clipboard.on("success", function (e) {
    e.clearSelection();
  });
});

// Initialize and start polling
updateStatus();
getVersion();
setInterval(updateStatus, 2000);
