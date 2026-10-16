/**
 * InstaFlow API Client
 * ====================
 * Cliente HTTP para comunicación asíncrona con los endpoints REST del backend.
 */

const InstaFlowAPI = {
  /**
   * Comprueba el estado general del sistema (Chrome, cookies, BD).
   */
  async checkHealth() {
    try {
      const res = await fetch("/api/health");
      return await res.json();
    } catch (err) {
      console.error("Error al consultar /api/health:", err);
      return { status: "unreachable", error: err.message };
    }
  },

  /**
   * Inicia un trabajo de extracción en segundo plano.
   */
  async startScrape(payload) {
    try {
      const res = await fetch("/api/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Error HTTP ${res.status}`);
      }
      return data;
    } catch (err) {
      throw err;
    }
  },

  /**
   * Consulta el progreso y estado de un trabajo en ejecución o finalizado.
   */
  async getJobStatus(jobId) {
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Error HTTP ${res.status}`);
      }
      return data;
    } catch (err) {
      throw err;
    }
  },

  /**
   * Solicita la cancelación segura de un trabajo activo.
   */
  async cancelJob(jobId) {
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
        method: "POST",
      });
      return await res.json();
    } catch (err) {
      console.error("Error al cancelar trabajo:", err);
      throw err;
    }
  },

  /**
   * Consulta los datos de perfil guardados.
   */
  async getProfile(username) {
    try {
      const res = await fetch(`/api/profile/${encodeURIComponent(username)}`);
      return await res.json();
    } catch (err) {
      throw err;
    }
  },

  /**
   * Consulta las publicaciones guardadas para un usuario.
   */
  async getProfilePosts(username, limit = 50) {
    try {
      const res = await fetch(`/api/profile/${encodeURIComponent(username)}/posts?limit=${limit}`);
      return await res.json();
    } catch (err) {
      throw err;
    }
  },

  /**
   * Consulta la configuración pública del servidor.
   */
  async getSettings() {
    try {
      const res = await fetch("/api/settings");
      return await res.json();
    } catch (err) {
      console.error("Error al obtener settings:", err);
      return {};
    }
  },

  /**
   * Solicita la eliminación de datos y archivos locales.
   */
  async clearData() {
    try {
      const res = await fetch("/api/clear-data", { method: "POST" });
      return await res.json();
    } catch (err) {
      throw err;
    }
  },

  /**
   * Retorna la URL para descargar el archivo JSON del trabajo.
   */
  getExportJsonUrl(jobId) {
    return `/api/exports/${encodeURIComponent(jobId)}/json`;
  },

  /**
   * Retorna la URL para descargar el archivo CSV del trabajo.
   */
  getExportCsvUrl(jobId) {
    return `/api/exports/${encodeURIComponent(jobId)}/csv`;
  },
};
