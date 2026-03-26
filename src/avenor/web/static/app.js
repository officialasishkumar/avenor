/* ==========================================================================
   Avenor — Client-side application logic
   ========================================================================== */

(function () {
  'use strict';

  // -----------------------------------------------------------------------
  // Sidebar toggle (desktop: collapse, mobile: show/hide)
  // -----------------------------------------------------------------------

  function toggleSidebar() {
    const isMobile = window.innerWidth <= 900;
    if (isMobile) {
      document.body.classList.toggle('sidebar-open');
    } else {
      document.body.classList.toggle('sidebar-collapsed');
    }
  }

  window.toggleSidebar = toggleSidebar;

  // -----------------------------------------------------------------------
  // Toast notification system
  // -----------------------------------------------------------------------

  const TOAST_DURATION = 4000;

  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
      success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>',
      error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
      warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
    };

    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span class="toast-message">${message}</span>
      <button class="toast-close" onclick="this.parentElement.remove()" aria-label="Close">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-visible'));

    setTimeout(() => {
      toast.classList.remove('toast-visible');
      setTimeout(() => toast.remove(), 300);
    }, TOAST_DURATION);
  }

  window.showToast = showToast;

  // -----------------------------------------------------------------------
  // Async repo operations
  // -----------------------------------------------------------------------

  // Add repository via JSON API
  async function addRepo(url, autoSync = true) {
    const btn = document.getElementById('add-repo-btn');
    const input = document.getElementById('add-repo-input');
    if (btn) btn.disabled = true;
    if (btn) btn.innerHTML = '<span class="spinner"></span> Adding...';

    try {
      const resp = await fetch('/api/repos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, auto_sync: autoSync }),
      });
      const data = await resp.json();

      if (!resp.ok) {
        showToast(data.error || 'Failed to add repository', 'error');
        return null;
      }

      showToast(`Added ${data.full_name}`, 'success');
      if (input) input.value = '';

      if (autoSync && data.sync_status !== 'ready') {
        showToast('Sync started in background...', 'info');
        startSyncPolling(data.id);
      }

      // Reload to show new repo in sidebar
      setTimeout(() => window.location.href = `/repos/${data.id}/overview`, 600);
      return data;
    } catch (err) {
      showToast('Network error — check your connection', 'error');
      return null;
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg> Add &amp; Track';
      }
    }
  }

  // Sync repository
  async function syncRepo(repoId) {
    const btn = document.querySelector(`[data-sync-id="${repoId}"]`);
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Syncing...';
    }

    try {
      const resp = await fetch(`/api/repos/${repoId}/sync`, { method: 'POST' });
      const data = await resp.json();

      if (data.status === 'already_running') {
        showToast('Sync already in progress', 'warning');
      } else {
        showToast('Sync started...', 'info');
        startSyncPolling(repoId);
      }
    } catch (err) {
      showToast('Failed to start sync', 'error');
    }
  }

  // Delete repository
  async function deleteRepo(repoId, repoName) {
    if (!confirm(`Delete "${repoName}" and all its collected data?\n\nThis cannot be undone.`)) {
      return;
    }

    try {
      const resp = await fetch(`/api/repos/${repoId}`, { method: 'DELETE' });
      const data = await resp.json();

      if (!resp.ok) {
        showToast(data.error || 'Failed to delete', 'error');
        return;
      }

      showToast(`Deleted ${repoName}`, 'success');
      setTimeout(() => window.location.href = '/', 600);
    } catch (err) {
      showToast('Network error', 'error');
    }
  }

  // Expose to global scope for onclick handlers
  window.addRepo = addRepo;
  window.syncRepo = syncRepo;
  window.deleteRepo = deleteRepo;

  // -----------------------------------------------------------------------
  // Sync status polling
  // -----------------------------------------------------------------------

  let pollIntervals = {};

  function startSyncPolling(repoId) {
    if (pollIntervals[repoId]) return;

    pollIntervals[repoId] = setInterval(async () => {
      try {
        const resp = await fetch(`/api/repos/${repoId}/status`);
        const data = await resp.json();

        if (data.sync_status === 'ready') {
          clearInterval(pollIntervals[repoId]);
          delete pollIntervals[repoId];
          showToast(`${data.full_name} sync complete!`, 'success');
          // Reload the page to show fresh data
          setTimeout(() => window.location.reload(), 800);
        } else if (data.sync_status === 'failed') {
          clearInterval(pollIntervals[repoId]);
          delete pollIntervals[repoId];
          showToast(`Sync failed: ${data.sync_error || 'Unknown error'}`, 'error');
          updateSyncButton(repoId, false);
        }

        // Update status badge in sidebar
        updateSidebarStatus(repoId, data.sync_status);
      } catch (err) {
        // ignore polling errors
      }
    }, 3000);
  }

  function updateSidebarStatus(repoId, status) {
    document.querySelectorAll(`[data-repo-id="${repoId}"] .status`).forEach(el => {
      el.className = `status status-${status}`;
      el.textContent = status;
      if (status === 'running') {
        el.classList.add('status-pulse');
      }
    });
  }

  function updateSyncButton(repoId, disabled) {
    const btn = document.querySelector(`[data-sync-id="${repoId}"]`);
    if (btn) {
      btn.disabled = disabled;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/></svg> Sync';
    }
  }

  // Global status polling (check all repos)
  function globalStatusPoll() {
    setInterval(async () => {
      try {
        const resp = await fetch('/api/repos');
        const repos = await resp.json();
        repos.forEach(r => {
          updateSidebarStatus(r.id, r.sync_status);
          if (r.sync_status === 'running') {
            startSyncPolling(r.id);
          }
        });
      } catch (err) {
        // ignore
      }
    }, 5000);
  }

  // -----------------------------------------------------------------------
  // Sidebar search / filter
  // -----------------------------------------------------------------------

  function initSidebarSearch() {
    const input = document.getElementById('sidebar-search');
    if (!input) return;

    input.addEventListener('input', () => {
      const q = input.value.toLowerCase().trim();
      document.querySelectorAll('.repo-list .repo-item').forEach(item => {
        const name = item.querySelector('.repo-item-name');
        const text = name ? name.textContent.toLowerCase() : '';
        const li = item.closest('li');
        if (li) li.style.display = text.includes(q) ? '' : 'none';
      });
    });
  }

  // -----------------------------------------------------------------------
  // Add repo form interception
  // -----------------------------------------------------------------------

  function initAddRepoForm() {
    // Sidebar form
    const form = document.getElementById('add-repo-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('add-repo-input');
        const autoSync = document.getElementById('auto-sync-toggle');
        if (input && input.value.trim()) {
          addRepo(input.value.trim(), autoSync ? autoSync.checked : true);
        }
      });
    }

    // Hero form (home page)
    const heroForm = document.getElementById('hero-add-repo-form');
    if (heroForm) {
      heroForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('hero-add-repo-input');
        if (input && input.value.trim()) {
          addRepo(input.value.trim(), true);
        }
      });
    }
  }

  // -----------------------------------------------------------------------
  // Period selector
  // -----------------------------------------------------------------------

  function initPeriodSelector() {
    document.querySelectorAll('.period-selector [data-period]').forEach(btn => {
      btn.addEventListener('click', () => {
        const period = btn.dataset.period;
        const url = new URL(window.location);
        url.searchParams.set('period', period);
        window.location.href = url.toString();
      });
    });
  }

  // -----------------------------------------------------------------------
  // Mobile navigation
  // -----------------------------------------------------------------------

  function initMobileNav() {
    const toggle = document.getElementById('mobile-nav-toggle');
    const menu = document.getElementById('mobile-nav-menu');
    if (!toggle || !menu) return;

    toggle.addEventListener('click', () => {
      menu.classList.toggle('mobile-nav-open');
      toggle.setAttribute('aria-expanded', menu.classList.contains('mobile-nav-open'));
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!toggle.contains(e.target) && !menu.contains(e.target)) {
        menu.classList.remove('mobile-nav-open');
      }
    });
  }

  // -----------------------------------------------------------------------
  // Settings page
  // -----------------------------------------------------------------------

  function initSettingsForm() {
    const form = document.getElementById('github-token-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = document.getElementById('github-token-input');
      const token = input ? input.value.trim() : '';
      if (!token) {
        showToast('Please enter a token', 'warning');
        return;
      }

      const btn = document.getElementById('save-token-btn');
      if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Saving...'; }

      try {
        const resp = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ github_token: token }),
        });
        if (resp.ok) {
          showToast('GitHub token saved!', 'success');
          setTimeout(() => window.location.reload(), 800);
        } else {
          showToast('Failed to save settings', 'error');
        }
      } catch (err) {
        showToast('Network error', 'error');
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = 'Save Token'; }
      }
    });
  }

  async function clearGithubToken() {
    if (!confirm('Remove the GitHub token from UI settings?')) return;
    try {
      const resp = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_token: '' }),
      });
      if (resp.ok) {
        showToast('Token cleared', 'success');
        setTimeout(() => window.location.reload(), 800);
      }
    } catch (err) {
      showToast('Network error', 'error');
    }
  }

  window.clearGithubToken = clearGithubToken;

  // -----------------------------------------------------------------------
  // Sync All
  // -----------------------------------------------------------------------

  async function syncAll() {
    const btn = document.getElementById('sync-all-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Syncing All...'; }

    try {
      const resp = await fetch('/api/repos/sync-all', { method: 'POST' });
      const data = await resp.json();

      if (data.status === 'no_repos') {
        showToast('No repositories to sync', 'warning');
      } else {
        showToast('Sync started for all repositories', 'info');
        // Start polling for each repo
        if (data.results) {
          data.results.forEach(r => {
            if (r.status === 'queued') startSyncPolling(r.id);
          });
        }
      }
    } catch (err) {
      showToast('Failed to sync all repositories', 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/></svg> Sync All';
      }
    }
  }

  window.syncAll = syncAll;

  // -----------------------------------------------------------------------
  // Initialize everything on DOM ready
  // -----------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', () => {
    initSidebarSearch();
    initAddRepoForm();
    initPeriodSelector();
    initMobileNav();
    initSettingsForm();
    globalStatusPoll();

    // Start polling for any currently-running repos
    document.querySelectorAll('.status-running').forEach(el => {
      el.classList.add('status-pulse');
      const repoItem = el.closest('[data-repo-id]');
      if (repoItem) {
        startSyncPolling(parseInt(repoItem.dataset.repoId, 10));
      }
    });
  });
})();
