/**
 * InstaFlow Gallery Controller
 * ============================
 * Gestión de la cuadrícula interactiva de publicaciones:
 * - Filtrado por tipo de contenido (fotos, carruseles, reels, descargadas)
 * - Búsqueda por texto en el pie de foto
 * - Paginación / carga progresiva
 * - Lightbox modal para zoom de imagen
 */

(function () {
  const Gallery = {
    allPosts: [],
    filteredPosts: [],
    currentFilter: "all",
    searchQuery: "",
    pageSize: 12,
    currentPage: 1,

    // Elementos del DOM
    gridEl: null,
    searchEl: null,
    filterPills: [],
    countBadge: null,
    modalLightbox: null,
    modalLightboxImg: null,
    modalLightboxCaption: null,
    btnCloseLightbox: null,

    init() {
      this.gridEl = document.getElementById("posts-grid-container");
      this.searchEl = document.getElementById("gallery-search-input");
      this.filterPills = document.querySelectorAll(".filter-pill");
      this.countBadge = document.getElementById("gallery-posts-count");

      // Modal Lightbox
      this.modalLightbox = document.getElementById("modal-lightbox");
      this.modalLightboxImg = document.getElementById("modal-lightbox-img");
      this.modalLightboxCaption = document.getElementById("modal-lightbox-caption");
      this.btnCloseLightbox = document.getElementById("btn-close-lightbox");

      this.bindEvents();
    },

    bindEvents() {
      // Búsqueda en vivo
      if (this.searchEl) {
        this.searchEl.addEventListener("input", (e) => {
          this.searchQuery = e.target.value.toLowerCase().trim();
          this.currentPage = 1;
          this.applyFilters();
        });
      }

      // Filtros por píldora
      this.filterPills.forEach((pill) => {
        pill.addEventListener("click", () => {
          this.filterPills.forEach((p) => p.classList.remove("active"));
          pill.classList.add("active");
          this.currentFilter = pill.getAttribute("data-filter") || "all";
          this.currentPage = 1;
          this.applyFilters();
        });
      });

      // Cerrar Lightbox
      if (this.btnCloseLightbox) {
        this.btnCloseLightbox.addEventListener("click", () => {
          this.modalLightbox.classList.remove("active");
        });
      }

      if (this.modalLightbox) {
        this.modalLightbox.addEventListener("click", (e) => {
          if (e.target === this.modalLightbox) {
            this.modalLightbox.classList.remove("active");
          }
        });
      }
    },

    renderPosts(posts) {
      this.allPosts = posts || [];
      this.currentPage = 1;
      this.applyFilters();
    },

    applyFilters() {
      let filtered = [...this.allPosts];

      // Filtro por tipo
      if (this.currentFilter === "photo") {
        filtered = filtered.filter((p) => p.media_type === "photo");
      } else if (this.currentFilter === "carousel") {
        filtered = filtered.filter((p) => p.media_type === "carousel");
      } else if (this.currentFilter === "reel") {
        filtered = filtered.filter((p) => ["reel", "video"].includes(p.media_type));
      } else if (this.currentFilter === "downloaded") {
        filtered = filtered.filter((p) => p.download_status === "downloaded");
      }

      // Filtro por texto de búsqueda
      if (this.searchQuery) {
        filtered = filtered.filter((p) => {
          const cap = (p.caption || "").toLowerCase();
          const code = (p.shortcode || "").toLowerCase();
          return cap.includes(this.searchQuery) || code.includes(this.searchQuery);
        });
      }

      this.filteredPosts = filtered;

      if (this.countBadge) {
        this.countBadge.textContent = `${filtered.length} publicaciones`;
      }

      this.renderGrid();
    },

    renderGrid() {
      if (!this.gridEl) return;

      if (this.filteredPosts.length === 0) {
        this.gridEl.innerHTML = `
          <div class="empty-gallery">
            <div class="empty-gallery-icon">🖼️</div>
            <div class="empty-gallery-title">No hay publicaciones para mostrar</div>
            <div class="empty-gallery-desc">
              ${this.allPosts.length === 0 
                ? "Inicie una extracción introduciendo un nombre de usuario de Instagram para ver sus publicaciones."
                : "No se encontraron publicaciones que coincidan con los filtros seleccionados."}
            </div>
          </div>
        `;
        return;
      }

      // Paginación progresiva para mantener fluidez
      const visibleCount = this.pageSize * this.currentPage;
      const visiblePosts = this.filteredPosts.slice(0, visibleCount);

      const cardsHtml = visiblePosts
        .map((post, index) => this.createPostCardHtml(post, index))
        .join("");

      let paginationHtml = "";
      if (visibleCount < this.filteredPosts.length) {
        paginationHtml = `
          <div style="grid-column: 1 / -1; text-align: center; margin-top: 16px;">
            <button id="btn-load-more" class="btn btn-secondary">
              Cargar más publicaciones (${this.filteredPosts.length - visibleCount} restantes)
            </button>
          </div>
        `;
      }

      this.gridEl.innerHTML = cardsHtml + paginationHtml;

      // Evento de cargar más
      const btnMore = document.getElementById("btn-load-more");
      if (btnMore) {
        btnMore.addEventListener("click", () => {
          this.currentPage++;
          this.renderGrid();
        });
      }

      // Eventos de clic en tarjetas para zoom
      this.gridEl.querySelectorAll(".post-media-container").forEach((el) => {
        el.addEventListener("click", () => {
          const idx = parseInt(el.getAttribute("data-index"), 10);
          this.openLightbox(visiblePosts[idx]);
        });
      });
    },

    createPostCardHtml(post, index) {
      // Fuente de imagen: local primero si fue descargada, luego URL remota, luego placeholder
      let imgSrc = "/static/img/placeholder.svg";
      if (post.thumbnail_path) {
        imgSrc = `/${post.thumbnail_path}`;
      } else if (post.thumbnail_url) {
        imgSrc = post.thumbnail_url;
      }

      // Insignia de tipo
      let badgeHtml = "";
      if (post.media_type === "carousel") {
        const countStr = post.media_items && post.media_items.length > 1 ? ` ${post.media_items.length}` : "";
        badgeHtml = `<span class="media-type-badge badge-carousel">⧉ Carrusel${countStr}</span>`;
      } else if (post.media_type === "reel") {
        badgeHtml = `<span class="media-type-badge badge-reel">▶ Reel</span>`;
      } else if (post.media_type === "video") {
        badgeHtml = `<span class="media-type-badge badge-video">🎥 Vídeo</span>`;
      }

      // Insignia de descarga
      let dlClass = "dl-pending";
      let dlText = "En espera";
      if (post.download_status === "downloaded") {
        dlClass = "dl-downloaded";
        dlText = "Descargada";
      } else if (post.download_status === "failed") {
        dlClass = "dl-failed";
        dlText = "Fallo descarga";
      } else if (post.download_status === "not_available") {
        dlClass = "dl-failed";
        dlText = "No disponible";
      }

      const dlBadgeHtml = `<span class="download-status-indicator ${dlClass}">${dlText}</span>`;

      // Formateo de contadores (distingue entre null y 0)
      const likesStr = post.like_count !== null ? Number(post.like_count).toLocaleString() : "—";
      const commentsStr = post.comment_count !== null ? Number(post.comment_count).toLocaleString() : "—";
      const captionText = post.caption || "Sin pie de foto disponible.";

      return `
        <div class="post-card">
          <div class="post-media-container" data-index="${index}" title="Clic para ampliar">
            ${badgeHtml}
            ${dlBadgeHtml}
            <img class="post-img" src="${imgSrc}" alt="${this.escapeHtml(captionText)}" loading="lazy" onerror="this.src='/static/img/placeholder.svg';">
          </div>
          <div class="post-body">
            <p class="post-caption" title="${this.escapeHtml(captionText)}">
              ${this.escapeHtml(captionText)}
            </p>
            <div class="post-stats-row">
              <div class="post-counters">
                <span class="post-counter-item" title="Me gusta">❤️ ${likesStr}</span>
                <span class="post-counter-item" title="Comentarios">💬 ${commentsStr}</span>
              </div>
              <a href="${post.url}" target="_blank" rel="noopener noreferrer" class="btn-link-ig">
                Instagram ↗
              </a>
            </div>
          </div>
        </div>
      `;
    },

    openLightbox(post) {
      if (!this.modalLightbox || !post) return;

      let imgSrc = "/static/img/placeholder.svg";
      if (post.thumbnail_path) {
        imgSrc = `/${post.thumbnail_path}`;
      } else if (post.thumbnail_url) {
        imgSrc = post.thumbnail_url;
      }

      this.modalLightboxImg.src = imgSrc;
      this.modalLightboxCaption.textContent = post.caption || `@${post.shortcode}`;
      this.modalLightbox.classList.add("active");
    },

    escapeHtml(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    },
  };

  // Exponer al objeto global window para comunicación con dashboard.js
  window.InstaFlowGallery = Gallery;
  document.addEventListener("DOMContentLoaded", () => Gallery.init());
})();
