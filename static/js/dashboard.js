/**
 * InstaFlow Dashboard Controller
 * ==============================
 * Orquestador de la interfaz de usuario, sondeo asíncrono de trabajos,
 * actualización reactiva de métricas, pipeline de etapas y terminal de registros.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Estado global de la aplicación cliente
  const state = {
    currentJobId: null,
    pollingInterval: null,
    isScraping: false,
    lastScrapedProfile: null,
    lastPosts: [],
    screenshotUrl: null,
  };

  // Elementos del DOM
  const elements = {
    // Entradas
    inputUsername: document.getElementById("input-username"),
    selectLimit: document.getElementById("select-limit"),
    chkDownloadImages: document.getElementById("chk-download-images"),
    chkScreenshot: document.getElementById("chk-screenshot"),
    btnStart: document.getElementById("btn-start-scrape"),
    btnCancel: document.getElementById("btn-cancel-scrape"),

    // Indicadores superiores
    dotBrowser: document.getElementById("dot-browser"),
    textBrowserStatus: document.getElementById("text-browser-status"),
    dotSession: document.getElementById("dot-session"),
    textSessionStatus: document.getElementById("text-session-status"),
    textLastRun: document.getElementById("text-last-run"),

    // Barra de progreso y etapas
    progressBar: document.getElementById("job-progress-bar"),
    stagesContainer: document.getElementById("stages-timeline-container"),
    logsConsole: document.getElementById("activity-logs-console"),

    // Tarjetas de Métricas
    valFollowers: document.getElementById("metric-val-followers"),
    valFollowing: document.getElementById("metric-val-following"),
    valTotalPosts: document.getElementById("metric-val-total-posts"),
    valCollectedPosts: document.getElementById("metric-val-collected-posts"),
    valAvailableImages: document.getElementById("metric-val-images"),
    valExtractionStatus: document.getElementById("metric-val-status"),

    // Tarjeta de Perfil
    profileAvatar: document.getElementById("profile-avatar-img"),
    profileUsername: document.getElementById("profile-display-username"),
    profileFullName: document.getElementById("profile-display-fullname"),
    profileBio: document.getElementById("profile-display-bio"),
    profilePrivacyBadge: document.getElementById("profile-privacy-badge"),
    profileVerifiedBadge: document.getElementById("profile-verified-badge"),
    profileLinkIg: document.getElementById("profile-link-ig"),
    btnViewScreenshot: document.getElementById("btn-view-screenshot"),

    // Modales
    modalScreenshot: document.getElementById("modal-screenshot"),
    modalScreenshotImg: document.getElementById("modal-screenshot-img"),
    btnCloseScreenshotModal: document.getElementById("btn-close-screenshot-modal"),

    // Galería
    postsCountBadge: document.getElementById("gallery-posts-count"),
    btnExportJson: document.getElementById("btn-export-json"),
    btnExportCsv: document.getElementById("btn-export-csv"),
  };

  // ==========================================================================
  // INICIALIZACIÓN Y DIAGNÓSTICO
  // ==========================================================================
  initSystem();

  async function initSystem() {
    setupEventListeners();
    await checkHealthStatus();
  }

  async function checkHealthStatus() {
    const health = await InstaFlowAPI.checkHealth();
    if (health.status === "healthy") {
      // Estado del navegador
      if (health.chrome_available) {
        elements.dotBrowser.className = "status-dot active";
        elements.textBrowserStatus.textContent = "Chrome Listo";
      } else {
        elements.dotBrowser.className = "status-dot danger";
        elements.textBrowserStatus.textContent = "Chrome no detectado";
      }

      // Estado de la sesión / cookies
      if (health.cookies_present) {
        elements.dotSession.className = "status-dot active";
        elements.textSessionStatus.textContent = "Cookies Configuradas";
      } else {
        elements.dotSession.className = "status-dot warning";
        elements.textSessionStatus.textContent = "Modo Público (Sin cookies)";
      }
    } else {
      elements.dotBrowser.className = "status-dot danger";
      elements.textBrowserStatus.textContent = "Servidor Desconectado";
      elements.dotSession.className = "status-dot danger";
      elements.textSessionStatus.textContent = "Error de conexión";
    }
  }

  // ==========================================================================
  // MANEJADORES DE EVENTOS
  // ==========================================================================
  function setupEventListeners() {
    // Iniciar scraping
    elements.btnStart.addEventListener("click", handleStartScrape);

    // Permitir iniciar con tecla Enter en el input de usuario
    elements.inputUsername.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleStartScrape();
      }
    });

    // Cancelar trabajo
    elements.btnCancel.addEventListener("click", handleCancelScrape);

    // Abrir modal de captura
    if (elements.btnViewScreenshot) {
      elements.btnViewScreenshot.addEventListener("click", () => {
        if (state.screenshotUrl) {
          elements.modalScreenshotImg.src = state.screenshotUrl;
          elements.modalScreenshot.classList.add("active");
        }
      });
    }

    // Cerrar modal de captura
    if (elements.btnCloseScreenshotModal) {
      elements.btnCloseScreenshotModal.addEventListener("click", () => {
        elements.modalScreenshot.classList.remove("active");
      });
    }

    if (elements.modalScreenshot) {
      elements.modalScreenshot.addEventListener("click", (e) => {
        if (e.target === elements.modalScreenshot) {
          elements.modalScreenshot.classList.remove("active");
        }
      });
    }

    // Exportaciones
    if (elements.btnExportJson) {
      elements.btnExportJson.addEventListener("click", () => {
        if (state.currentJobId) {
          window.location.href = InstaFlowAPI.getExportJsonUrl(state.currentJobId);
        }
      });
    }

    if (elements.btnExportCsv) {
      elements.btnExportCsv.addEventListener("click", () => {
        if (state.currentJobId) {
          window.location.href = InstaFlowAPI.getExportCsvUrl(state.currentJobId);
        }
      });
    }
  }

  // ==========================================================================
  // FLUJO DE EXTRACCIÓN (SCRAPING WORKFLOW)
  // ==========================================================================
  async function handleStartScrape() {
    const rawUsername = elements.inputUsername.value.trim();
    if (!rawUsername) {
      alert("Por favor, introduzca un nombre de usuario de Instagram válido.");
      elements.inputUsername.focus();
      return;
    }

    const maxPosts = parseInt(elements.selectLimit.value, 10) || 12;
    const downloadImages = elements.chkDownloadImages.checked;
    const captureScreenshot = elements.chkScreenshot.checked;

    // Resetear UI para nueva ejecución
    setScrapingState(true);
    resetDashboardViews();

    try {
      addTerminalLog("info", `Solicitando extracción para @${rawUsername}...`);
      const response = await InstaFlowAPI.startScrape({
        username: rawUsername,
        max_posts: maxPosts,
        download_images: downloadImages,
        capture_screenshot: captureScreenshot,
      });

      state.currentJobId = response.job_id;
      addTerminalLog("success", `Trabajo aceptado [ID: ${response.job_id.substring(0, 8)}].`);

      // Iniciar sondeo periódico
      startPolling(response.job_id);
    } catch (err) {
      addTerminalLog("error", `Fallo al iniciar extracción: ${err.message}`);
      alert(`Error al iniciar la extracción: ${err.message}`);
      setScrapingState(false);
    }
  }

  async function handleCancelScrape() {
    if (!state.currentJobId) return;

    elements.btnCancel.disabled = true;
    elements.btnCancel.textContent = "Cancelando...";
    try {
      await InstaFlowAPI.cancelJob(state.currentJobId);
      addTerminalLog("warning", "Solicitud de cancelación enviada al servidor.");
    } catch (err) {
      addTerminalLog("error", `Error al solicitar cancelación: ${err.message}`);
    }
  }

  function startPolling(jobId) {
    if (state.pollingInterval) clearInterval(state.pollingInterval);

    state.pollingInterval = setInterval(async () => {
      try {
        const job = await InstaFlowAPI.getJobStatus(jobId);
        updateJobProgressUI(job);

        // Si terminó el trabajo (completado, parcial, fallido o cancelado)
        if (["completed", "partial", "failed", "cancelled"].includes(job.status)) {
          stopPolling();
          setScrapingState(false);
          finalizeJobUI(job);
        }
      } catch (err) {
        console.error("Error en sondeo:", err);
      }
    }, 1200);
  }

  function stopPolling() {
    if (state.pollingInterval) {
      clearInterval(state.pollingInterval);
      state.pollingInterval = null;
    }
  }

  function setScrapingState(isScraping) {
    state.isScraping = isScraping;
    elements.btnStart.disabled = isScraping;
    elements.inputUsername.disabled = isScraping;
    elements.selectLimit.disabled = isScraping;

    if (isScraping) {
      elements.btnStart.innerHTML = `<span class="spinner"></span> Analizando...`;
      elements.btnCancel.style.display = "inline-flex";
      elements.btnCancel.disabled = false;
      elements.btnCancel.textContent = "Cancelar ejecución";
    } else {
      elements.btnStart.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Analizar perfil`;
      elements.btnCancel.style.display = "none";
    }
  }

  // ==========================================================================
  // ACTUALIZACIÓN DE INTERFAZ Y ETAPAS
  // ==========================================================================
  function updateJobProgressUI(job) {
    // Actualizar barra de progreso
    const percent = Math.min(100, Math.max(0, job.progress_percent || 0));
    elements.progressBar.style.width = `${percent}%`;

    // Actualizar etapas renderizadas
    renderStages(job.stages || []);

    // Actualizar logs en la consola
    if (job.logs && job.logs.length > 0) {
      renderLogs(job.logs);
    }
  }

  function renderStages(stages) {
    if (!stages || stages.length === 0) return;

    elements.stagesContainer.innerHTML = stages
      .map((st) => {
        let statusClass = st.status || "running";
        let iconHtml = "";

        if (statusClass === "running") {
          iconHtml = `<span class="status-dot warning pulse"></span>`;
        } else if (statusClass === "success") {
          iconHtml = `<span style="color:var(--accent-green)">✓</span>`;
        } else if (statusClass === "warning") {
          iconHtml = `<span style="color:var(--accent-amber)">⚠</span>`;
        } else {
          iconHtml = `<span style="color:var(--accent-red)">✕</span>`;
        }

        const duration = st.duration_sec ? ` (${st.duration_sec}s)` : "";

        return `
          <div class="stage-item ${statusClass}">
            <div class="stage-left">
              <span class="stage-number">${st.stage_number}</span>
              <div>
                <div class="stage-name">${escapeHtml(st.name)}</div>
                <div class="stage-message">${escapeHtml(st.message || "")}${duration}</div>
              </div>
            </div>
            <div class="stage-right">${iconHtml}</div>
          </div>
        `;
      })
      .join("");

    // Auto-scroll hacia abajo
    elements.stagesContainer.scrollTop = elements.stagesContainer.scrollHeight;
  }

  function renderLogs(logs) {
    elements.logsConsole.innerHTML = logs
      .map(
        (l) => `
        <div class="log-entry">
          <span class="log-time">[${l.timestamp}]</span>
          <span class="log-msg ${l.level}">${escapeHtml(l.message)}</span>
        </div>
      `
      )
      .join("");
    elements.logsConsole.scrollTop = elements.logsConsole.scrollHeight;
  }

  function addTerminalLog(level, message) {
    const timeStr = new Date().toTimeString().split(" ")[0];
    const logDiv = document.createElement("div");
    logDiv.className = "log-entry";
    logDiv.innerHTML = `
      <span class="log-time">[${timeStr}]</span>
      <span class="log-msg ${level}">${escapeHtml(message)}</span>
    `;
    elements.logsConsole.appendChild(logDiv);
    elements.logsConsole.scrollTop = elements.logsConsole.scrollHeight;
  }

  // ==========================================================================
  // FINALIZACIÓN Y PRESENTACIÓN DE RESULTADOS
  // ==========================================================================
  function finalizeJobUI(job) {
    elements.progressBar.style.width = "100%";

    // 1. Métricas
    renderMetrics(job);

    // 2. Tarjeta de Perfil
    if (job.profile) {
      renderProfileCard(job.profile, job.summary);
    }

    // 3. Galería de Publicaciones
    const posts = job.posts || [];
    state.lastPosts = posts;
    if (window.InstaFlowGallery) {
      window.InstaFlowGallery.renderPosts(posts);
    }

    // 4. Habilitar exportaciones
    if (elements.btnExportJson) elements.btnExportJson.disabled = false;
    if (elements.btnExportCsv) elements.btnExportCsv.disabled = posts.length === 0;

    // 5. Indicador de última ejecución
    const nowTime = new Date().toLocaleTimeString();
    elements.textLastRun.textContent = `Última: ${nowTime} (@${job.username})`;
  }

  /**
   * REGLA ESENCIAL: Nunca sustituir datos ausentes por cero.
   * Distingue rigurosamente entre 0 y desconocido/null.
   */
  function renderMetrics(job) {
    const p = job.profile || {};
    const sum = job.summary || {};

    // 1. Seguidores
    formatMetricCard(elements.valFollowers, p.followers_count);

    // 2. Seguidos
    formatMetricCard(elements.valFollowing, p.following_count);

    // 3. Publicaciones indicadas por Instagram en el perfil
    formatMetricCard(elements.valTotalPosts, p.posts_count);

    // 4. Publicaciones recopiladas
    const collected = sum.posts_collected !== undefined ? sum.posts_collected : (job.posts ? job.posts.length : null);
    formatMetricCard(elements.valCollectedPosts, collected);

    // 5. Imágenes disponibles / descargadas
    formatMetricCard(elements.valAvailableImages, sum.images_downloaded);

    // 6. Estado de extracción
    const statusMap = {
      completed: { text: "Completada", color: "var(--accent-green)" },
      partial: { text: "Parcial", color: "var(--accent-amber)" },
      failed: { text: "Fallida", color: "var(--accent-red)" },
      cancelled: { text: "Cancelada", color: "var(--text-muted)" },
    };
    const stInfo = statusMap[job.status] || { text: job.status || "Desconocido", color: "#fff" };
    elements.valExtractionStatus.textContent = stInfo.text;
    elements.valExtractionStatus.style.color = stInfo.color;
    elements.valExtractionStatus.classList.remove("unknown");
  }

  function formatMetricCard(element, val) {
    if (val === null || val === undefined) {
      element.textContent = "No disponible";
      element.classList.add("unknown");
      element.style.color = "";
    } else if (val === 0) {
      element.textContent = "0";
      element.classList.remove("unknown");
      element.style.color = "#fff";
    } else {
      element.textContent = Number(val).toLocaleString();
      element.classList.remove("unknown");
      element.style.color = "#fff";
    }
  }

  function renderProfileCard(profile, summary) {
    state.lastScrapedProfile = profile;

    // Foto de perfil: usar local si existe, luego remota, o placeholder
    if (profile.profile_image_path) {
      elements.profileAvatar.src = `/${profile.profile_image_path}`;
    } else if (profile.profile_image_url) {
      elements.profileAvatar.src = profile.profile_image_url;
    } else {
      elements.profileAvatar.src = "/static/img/placeholder.svg";
    }

    elements.profileUsername.textContent = `@${profile.username}`;
    elements.profileFullName.textContent = profile.full_name || "Nombre no disponible";

    // Biografía: conservar saltos de línea y emojis
    elements.profileBio.textContent = profile.biography || "";

    // Estado privado / público
    if (profile.is_private === true) {
      elements.profilePrivacyBadge.textContent = "Privada";
      elements.profilePrivacyBadge.className = "profile-privacy-tag privacy-private";
    } else if (profile.is_private === false) {
      elements.profilePrivacyBadge.textContent = "Pública";
      elements.profilePrivacyBadge.className = "profile-privacy-tag privacy-public";
    } else {
      elements.profilePrivacyBadge.textContent = "Privacidad Desconocida";
      elements.profilePrivacyBadge.className = "profile-privacy-tag";
    }

    // Verificación
    elements.profileVerifiedBadge.style.display = profile.is_verified ? "inline-flex" : "none";

    // Enlace a Instagram
    elements.profileLinkIg.href = profile.profile_url || `https://www.instagram.com/${profile.username}/`;

    // Captura de pantalla
    if (summary && summary.screenshot_path) {
      state.screenshotUrl = `/${summary.screenshot_path}`;
      if (elements.btnViewScreenshot) {
        elements.btnViewScreenshot.style.display = "inline-flex";
      }
    } else {
      state.screenshotUrl = null;
      if (elements.btnViewScreenshot) {
        elements.btnViewScreenshot.style.display = "none";
      }
    }
  }

  function resetDashboardViews() {
    elements.valFollowers.textContent = "—";
    elements.valFollowers.classList.add("unknown");
    elements.valFollowing.textContent = "—";
    elements.valFollowing.classList.add("unknown");
    elements.valTotalPosts.textContent = "—";
    elements.valTotalPosts.classList.add("unknown");
    elements.valCollectedPosts.textContent = "—";
    elements.valCollectedPosts.classList.add("unknown");
    elements.valAvailableImages.textContent = "—";
    elements.valAvailableImages.classList.add("unknown");
    elements.valExtractionStatus.textContent = "En curso...";
    elements.valExtractionStatus.classList.remove("unknown");
    elements.valExtractionStatus.style.color = "var(--accent-purple)";

    elements.stagesContainer.innerHTML = "";
    elements.logsConsole.innerHTML = "";
    elements.progressBar.style.width = "0%";

    if (elements.btnExportJson) elements.btnExportJson.disabled = true;
    if (elements.btnExportCsv) elements.btnExportCsv.disabled = true;
    if (elements.btnViewScreenshot) elements.btnViewScreenshot.style.display = "none";
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
