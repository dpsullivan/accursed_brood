/* Accursed Brood — Companion Wiki Application Shell
 * Manages file:// classic-script discovery, drag-and-drop JSON loading,
 * Seed-Only Mode, #/ hash routing, Ryu/Teepo theme persistence, and Checklist storage.
 */
(function () {
  'use strict';

  var THEME_STORAGE_KEY = 'accursed_brood_wiki_theme_v1';
  var CHECKLIST_STORAGE_PREFIX = 'accursed_brood_wiki_checklist_v1:';

  var store = {
    registry: null,
    runsList: [],        // Ordered list of run metadata entries (local + external)
    manifestsById: {},   // run_id -> full Seed Manifest object
    baselinesByRom: {},  // rom_version -> Vanilla Baseline object
    failedScripts: {},   // script_path -> true
    loadingScripts: {},  // script_path -> Array<callback>
    externalRunIds: {}   // run_id -> true
  };

  var state = {
    runId: null,
    theme: loadSavedTheme(),
    route: parseHash(window.location.hash),
    loadingRun: false,
    loadNotice: '',
    isDragging: false,
    copiedShare: false,
    filters: {
      changedOnly: false,
      monsterTier: 'All',
      equipKind: 'All',
      charTab: 'party',
      hideCompleted: false,
      checklistPane: 'all',
      collapsedChecklist: {},
      drawerItem: null,
      fullPageMode: false,
      paletteOpen: false,
      searchQuery: '',
      expandedGuardrails: false,
      listQuery: ''
    }
  };

  function safeStorageGet(key) {
    try { return window.localStorage.getItem(key); } catch (_) { return null; }
  }
  function safeStorageSet(key, val) {
    try { window.localStorage.setItem(key, val); } catch (_) {}
  }

  function loadSavedTheme() {
    var saved = safeStorageGet(THEME_STORAGE_KEY);
    return saved === 'dark' ? 'dark' : 'light';
  }

  function applyThemeBodyClass() {
    document.body.classList.add('brood-chronicle');
    document.body.classList.toggle('theme-teepo', state.theme === 'dark');
  }

  function setTheme(theme) {
    state.theme = theme === 'dark' ? 'dark' : 'light';
    safeStorageSet(THEME_STORAGE_KEY, state.theme);
    applyThemeBodyClass();
    render();
  }

  function parseHash(raw) {
    var clean = String(raw || '').replace(/^#\/?/, '').trim();
    if (!clean) return { section: 'overview', id: null, full: false };
    var parts = clean.split('/').filter(Boolean);
    return {
      section: decodeURIComponent(parts[0] || 'overview'),
      id: parts[1] ? decodeURIComponent(parts[1]) : null,
      full: parts[2] === 'full'
    };
  }

  function syncRouteState(prevSection, nextRoute) {
    if (prevSection !== nextRoute.section) {
      state.filters.listQuery = '';
      state.filters.changedOnly = false;
    }
    state.route = nextRoute;
    state.filters.paletteOpen = false;
    state.filters.fullPageMode = !!(nextRoute.id && nextRoute.full);
    if (!nextRoute.id) {
      state.filters.drawerItem = null;
    } else if (!state.filters.fullPageMode && ['monsters', 'characters', 'masters', 'abilities', 'equipment'].indexOf(nextRoute.section) >= 0) {
      state.filters.drawerItem = nextRoute.section + ':' + nextRoute.id;
    } else {
      state.filters.drawerItem = null;
    }
  }

  function navigate(hash) {
    var normalized = hash.charAt(0) === '#' ? hash : '#/' + hash.replace(/^\/+/, '');
    syncRouteState(state.route.section, parseHash(normalized));
    if (window.location.hash !== normalized) {
      try {
        window.location.hash = normalized;
      } catch (_) {}
    }
    render();
    window.scrollTo(0, 0);
  }

  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatSigned(n) {
    var num = Number(n) || 0;
    return num > 0 ? '+' + num : String(num);
  }

  function loadClassicScript(scriptPath, callback) {
    if (!scriptPath) {
      callback(false);
      return;
    }
    if (store.failedScripts[scriptPath]) {
      callback(false);
      return;
    }
    if (store.loadingScripts[scriptPath]) {
      store.loadingScripts[scriptPath].push(callback);
      return;
    }
    store.loadingScripts[scriptPath] = [callback];
    var el = document.createElement('script');
    el.src = scriptPath;
    el.async = true;
    el.onload = function () {
      var cbs = store.loadingScripts[scriptPath] || [];
      delete store.loadingScripts[scriptPath];
      cbs.forEach(function (fn) { fn(true); });
    };
    el.onerror = function () {
      store.failedScripts[scriptPath] = true;
      var cbs = store.loadingScripts[scriptPath] || [];
      delete store.loadingScripts[scriptPath];
      cbs.forEach(function (fn) { fn(false); });
    };
    document.head.appendChild(el);
  }

  function baselineScriptPathFor(romVersion) {
    if (!romVersion) return null;
    if (store.registry && store.registry.baselines && store.registry.baselines[romVersion]) {
      return store.registry.baselines[romVersion];
    }
    var safe = String(romVersion).replace(/[^a-zA-Z0-9_.-]+/g, '_');
    return 'output/vanilla_baseline_' + safe + '.js';
  }

  function ensureBaselineLoaded(romVersion, done) {
    if (!romVersion || store.baselinesByRom[romVersion]) {
      done(!!store.baselinesByRom[romVersion]);
      return;
    }
    var path = baselineScriptPathFor(romVersion);
    loadClassicScript(path, function () {
      done(!!store.baselinesByRom[romVersion]);
    });
  }

  function selectRun(runId) {
    if (!runId) {
      state.runId = null;
      state.loadingRun = false;
      render();
      return;
    }
    state.runId = runId;
    state.filters.drawerItem = null;
    state.filters.fullPageMode = false;
    state.copiedShare = false;

    var existing = store.manifestsById[runId];
    if (existing) {
      state.loadingRun = false;
      ensureBaselineLoaded(existing.rom_version, function () {
        updateRunBaselineFlags();
        render();
      });
      render();
      return;
    }

    var meta = store.runsList.find(function (r) { return r.run_id === runId; });
    if (!meta || !meta.script_path) {
      handleMissingRun(runId);
      return;
    }

    state.loadingRun = true;
    render();
    loadClassicScript(meta.script_path, function (ok) {
      if (!ok || !store.manifestsById[runId]) {
        handleMissingRun(runId);
        return;
      }
      state.loadingRun = false;
      var loaded = store.manifestsById[runId];
      ensureBaselineLoaded(loaded.rom_version, function () {
        updateRunBaselineFlags();
        render();
      });
      render();
    });
  }

  function handleMissingRun(badRunId) {
    store.runsList = store.runsList.filter(function (r) { return r.run_id !== badRunId; });
    state.loadingRun = false;
    state.loadNotice = 'Skipped missing or unreadable Seed Manifest "' + badRunId + '".';
    if (store.runsList.length) {
      selectRun(store.runsList[0].run_id);
    } else {
      state.runId = null;
      render();
    }
  }

  function updateRunBaselineFlags() {
    store.runsList.forEach(function (entry) {
      if (!entry.rom_version) {
        entry.hasBaseline = false;
        return;
      }
      if (store.baselinesByRom[entry.rom_version]) {
        entry.hasBaseline = true;
      } else if (store.registry && store.registry.baselines && store.registry.baselines[entry.rom_version]) {
        entry.hasBaseline = true;
      } else {
        entry.hasBaseline = false;
      }
    });
  }

  function loadExternalManifestObject(data, filename) {
    if (!data || typeof data !== 'object' || !data.run_id || !data.categories) {
      state.loadNotice = 'Could not load "' + (filename || 'file') + '": not a valid Accursed Brood Seed Manifest JSON.';
      render();
      return;
    }
    var runId = String(data.run_id);
    store.manifestsById[runId] = data;
    store.externalRunIds[runId] = true;
    state.loadNotice = '';

    var existingIdx = store.runsList.findIndex(function (r) { return r.run_id === runId; });
    var meta = {
      run_id: runId,
      seed: String(data.seed || ''),
      preset: String(data.preset || 'Custom'),
      rom_version: String(data.rom_version || ''),
      version: String(data.version || ''),
      flags: String(data.flags || ''),
      generated_at: String(data.generated_at || ''),
      isExternal: true,
      hasBaseline: !!store.baselinesByRom[data.rom_version]
    };
    if (existingIdx >= 0) {
      store.runsList[existingIdx] = meta;
    } else {
      store.runsList.unshift(meta);
    }
    selectRun(runId);
  }

  function readManifestFile(file) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var parsed = JSON.parse(String(reader.result || ''));
        loadExternalManifestObject(parsed, file.name);
      } catch (err) {
        state.loadNotice = 'Failed to parse "' + file.name + '" as JSON.';
        render();
      }
    };
    reader.onerror = function () {
      state.loadNotice = 'Unable to read "' + file.name + '".';
      render();
    };
    reader.readAsText(file);
  }

  // Checklist storage per deterministic run_id
  function getChecklistMap(runId) {
    if (!runId) return {};
    var raw = safeStorageGet(CHECKLIST_STORAGE_PREFIX + runId);
    if (!raw) return {};
    try {
      var parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function saveChecklistMap(runId, map) {
    if (!runId) return;
    safeStorageSet(CHECKLIST_STORAGE_PREFIX + runId, JSON.stringify(map));
  }

  function isChecked(itemKey) {
    if (!state.runId) return false;
    var map = getChecklistMap(state.runId);
    return !!map[itemKey];
  }

  function toggleCheck(itemKey) {
    if (!state.runId) return;
    var map = getChecklistMap(state.runId);
    if (map[itemKey]) {
      delete map[itemKey];
    } else {
      map[itemKey] = true;
    }
    saveChecklistMap(state.runId, map);
    render();
  }

  function getChecklistStats(manifest) {
    if (!manifest) return { done: 0, total: 0, pct: 0, sections: [] };
    var map = getChecklistMap(manifest.run_id);
    var sections = window.WikiData.buildChecklist(manifest).map(function (sec) {
      var total = sec.items.length;
      var done = sec.items.filter(function (it) { return !!map[it.key]; }).length;
      return {
        id: sec.id,
        label: sec.label,
        desc: sec.desc,
        items: sec.items,
        done: done,
        total: total,
        pct: total ? Math.round((done / total) * 100) : 0
      };
    });
    var total = sections.reduce(function (acc, s) { return acc + s.total; }, 0);
    var done = sections.reduce(function (acc, s) { return acc + s.done; }, 0);
    return {
      done: done,
      total: total,
      pct: total ? Math.round((done / total) * 100) : 0,
      sections: sections
    };
  }

  function copyText(text, onSuccess) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(onSuccess, function () {
        fallbackCopy(text, onSuccess);
      });
    } else {
      fallbackCopy(text, onSuccess);
    }
  }

  function fallbackCopy(text, onSuccess) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(ta);
    if (onSuccess) onSuccess();
  }

  function getActiveManifest() {
    return state.runId ? (store.manifestsById[state.runId] || null) : null;
  }

  function getActiveBaseline(manifest) {
    if (!manifest || !manifest.rom_version) return null;
    return store.baselinesByRom[manifest.rom_version] || null;
  }

  function openBackupModal() {
    var run = getActiveManifest();
    if (!run) return;
    var checkedKeys = Object.keys(getChecklistMap(run.run_id)).sort();
    var payload = JSON.stringify({
      schema_version: 1,
      run_id: run.run_id,
      seed: run.seed,
      rom_version: run.rom_version,
      exported_at: new Date().toISOString(),
      checked: checkedKeys
    }, null, 2);

    var modalRoot = document.getElementById('wiki-modal-root');
    if (!modalRoot) return;

    modalRoot.innerHTML = (
      '<div class="bc-modal-backdrop" data-close-modal="1">' +
        '<div class="bc-modal" role="dialog" aria-modal="true" aria-label="Checklist JSON Backup">' +
          '<div class="bc-modal-hd">' +
            '<h3>Checklist JSON Backup — Seed ' + esc(run.seed) + '</h3>' +
            '<button type="button" class="bc-btn-xs" data-close-modal="1" aria-label="Close">✕</button>' +
          '</div>' +
          '<div class="bc-modal-body">' +
            '<p class="bc-muted-sm" style="margin-top:0">Saved automatically in <code>localStorage</code> under Run ID <code>' + esc(run.run_id) + '</code>. Copy or download this JSON to back up, or paste a backup below and click <strong>Import JSON</strong>.</p>' +
            '<textarea id="bc-backup-textarea" rows="12" spellcheck="false">' + esc(payload) + '</textarea>' +
            '<div id="bc-backup-msg" class="bc-modal-msg"></div>' +
            '<div class="bc-modal-actions">' +
              '<button type="button" class="bc-btn-sm" id="bc-backup-copy">Copy JSON</button>' +
              '<button type="button" class="bc-btn-sm" id="bc-backup-download">Download .json</button>' +
              '<button type="button" class="bc-btn-cerulean" id="bc-backup-import">Import JSON</button>' +
              '<button type="button" class="bc-btn-sm" data-close-modal="1">Close</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    );

    function closeModal() {
      modalRoot.innerHTML = '';
    }

    modalRoot.querySelectorAll('[data-close-modal]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (e.target === el) closeModal();
      });
    });

    var msgEl = document.getElementById('bc-backup-msg');
    var ta = document.getElementById('bc-backup-textarea');

    var copyBtn = document.getElementById('bc-backup-copy');
    if (copyBtn && ta) {
      copyBtn.addEventListener('click', function () {
        copyText(ta.value, function () {
          copyBtn.textContent = 'Copied!';
          if (msgEl) { msgEl.className = 'bc-modal-msg ok'; msgEl.textContent = 'Backup JSON copied to clipboard.'; }
        });
      });
    }

    var dlBtn = document.getElementById('bc-backup-download');
    if (dlBtn && ta) {
      dlBtn.addEventListener('click', function () {
        try {
          var blob = new Blob([ta.value], { type: 'application/json' });
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = 'checklist_' + run.run_id + '.json';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          if (msgEl) { msgEl.className = 'bc-modal-msg ok'; msgEl.textContent = 'Downloaded checklist_' + run.run_id + '.json.'; }
        } catch (_) {
          if (msgEl) { msgEl.className = 'bc-modal-msg err'; msgEl.textContent = 'Download blocked; use Copy JSON instead.'; }
        }
      });
    }

    var importBtn = document.getElementById('bc-backup-import');
    if (importBtn && ta) {
      importBtn.addEventListener('click', function () {
        var parsed;
        try {
          parsed = JSON.parse(ta.value);
        } catch (err) {
          if (msgEl) { msgEl.className = 'bc-modal-msg err'; msgEl.textContent = 'Invalid JSON syntax: ' + err.message; }
          return;
        }
        if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.checked)) {
          if (msgEl) { msgEl.className = 'bc-modal-msg err'; msgEl.textContent = 'Backup JSON must be an object containing a "checked" array of keys.'; }
          return;
        }
        var nextMap = {};
        parsed.checked.forEach(function (k) {
          if (typeof k === 'string' && k.trim()) {
            nextMap[k.trim()] = true;
          }
        });
        saveChecklistMap(run.run_id, nextMap);
        closeModal();
        render();
      });
    }
  }

  function buildContext() {
    var run = getActiveManifest();
    var baseline = getActiveBaseline(run);
    var crossLinks = run ? window.WikiData.buildCrossLinks(run) : { abilitySources: {}, itemSources: {} };
    var checklistStats = getChecklistStats(run);

    return {
      state: state,
      run: run,
      runs: store.runsList,
      baseline: baseline,
      hasBaseline: !!baseline,
      isExternal: !!(run && store.externalRunIds[run.run_id]),
      categories: window.WikiData.CATEGORIES,
      elements: window.WikiData.ELEMENTS,
      crossLinks: crossLinks,
      checklistStats: checklistStats,
      api: {
        esc: esc,
        formatSigned: formatSigned,
        navigate: navigate,
        setTheme: setTheme,
        selectRun: selectRun,
        isChecked: isChecked,
        toggleCheck: toggleCheck,
        setFilter: function (key, val) { state.filters[key] = val; render(); },
        toggleCollapseChecklist: function (secId) {
          state.filters.collapsedChecklist[secId] = !state.filters.collapsedChecklist[secId];
          render();
        },
        openBackupModal: openBackupModal,
        openFilePicker: function () {
          var input = document.getElementById('wiki-file-input');
          if (input) { input.value = ''; input.click(); }
        },
        copyShareString: function () {
          if (!run || !run.share_string) return;
          copyText(run.share_string, function () {
            state.copiedShare = true;
            render();
            window.setTimeout(function () {
              state.copiedShare = false;
              render();
            }, 1800);
          });
        }
      }
    };
  }

  function render() {
    applyThemeBodyClass();
    var root = document.getElementById('wiki-root');
    if (!root || !window.WikiRender) return;
    var ctx = buildContext();
    root.innerHTML = window.WikiRender.render(ctx);
    bindEvents(root, ctx);
  }

  function bindEvents(root, ctx) {
    root.querySelectorAll('[data-nav]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        ctx.api.navigate(el.getAttribute('data-nav'));
      });
    });

    var sel = root.querySelector('[data-run-select]');
    if (sel) {
      sel.addEventListener('change', function () {
        ctx.api.selectRun(sel.value);
      });
    }

    root.querySelectorAll('[data-set-theme]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        ctx.api.setTheme(btn.getAttribute('data-set-theme'));
      });
    });

    root.querySelectorAll('[data-pick-json]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        ctx.api.openFilePicker();
      });
    });

    root.querySelectorAll('[data-copy-share]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        ctx.api.copyShareString();
      });
    });

    if (typeof window.WikiRender.bind === 'function') {
      window.WikiRender.bind(root, ctx);
    }
  }

  // Global classic-script registration bridge (called by output/seeds/registry.js, *.js, vanilla_baseline_*.js)
  var bridge = window.__ACCURSED_BROOD_WIKI__ = window.__ACCURSED_BROOD_WIKI__ || {};
  var queued = Array.isArray(bridge._queue) ? bridge._queue.slice() : [];
  bridge._queue = [];

  bridge.registerRegistry = function (payload) {
    if (!payload || typeof payload !== 'object') return;
    store.registry = payload;
    var localRuns = Array.isArray(payload.runs) ? payload.runs.slice() : [];
    // Preserve any external manifests already dropped in this session
    var externals = store.runsList.filter(function (r) { return r.isExternal; });
    store.runsList = externals.concat(localRuns);
    updateRunBaselineFlags();
    if (!state.runId && store.runsList.length) {
      selectRun(store.runsList[0].run_id);
    } else {
      render();
    }
  };

  bridge.registerSeed = function (manifest) {
    if (!manifest || !manifest.run_id) return;
    store.manifestsById[manifest.run_id] = manifest;
  };

  bridge.registerBaseline = function (baseline) {
    if (!baseline || !baseline.rom_version) return;
    store.baselinesByRom[baseline.rom_version] = baseline;
    updateRunBaselineFlags();
  };

  bridge.onRegistryMissing = function () {
    // Expected before any local randomizer Run has been generated
    if (!store.runsList.length) {
      render();
    }
  };

  // Expose minimal hooks for future modules & inspection
  bridge.loadExternalManifestObject = loadExternalManifestObject;
  bridge.getState = function () { return state; };
  bridge.getStore = function () { return store; };

  // Global event listeners
  window.addEventListener('hashchange', function () {
    syncRouteState(state.route.section, parseHash(window.location.hash));
    render();
  });

  window.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (getActiveManifest()) {
        state.filters.paletteOpen = !state.filters.paletteOpen;
        render();
      }
    } else if (e.key === 'Escape') {
      var modalRoot = document.getElementById('wiki-modal-root');
      if (modalRoot && modalRoot.innerHTML) {
        modalRoot.innerHTML = '';
        return;
      }
      if (state.filters.paletteOpen) {
        state.filters.paletteOpen = false;
        render();
      } else if (state.filters.drawerItem) {
        state.filters.drawerItem = null;
        if (state.route.id) {
          state.route.id = null;
          try {
            window.location.hash = '#/' + state.route.section;
          } catch (_) {}
        }
        render();
      }
    }
  });

  var dragDepth = 0;
  window.addEventListener('dragenter', function (e) {
    e.preventDefault();
    dragDepth += 1;
    if (!state.isDragging) {
      state.isDragging = true;
      render();
    }
  });
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('dragleave', function (e) {
    e.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0 && state.isDragging) {
      state.isDragging = false;
      render();
    }
  });
  window.addEventListener('drop', function (e) {
    e.preventDefault();
    dragDepth = 0;
    state.isDragging = false;
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) {
      readManifestFile(files[0]);
    } else {
      render();
    }
  });

  var fileInput = document.getElementById('wiki-file-input');
  if (fileInput) {
    fileInput.addEventListener('change', function () {
      if (fileInput.files && fileInput.files.length) {
        readManifestFile(fileInput.files[0]);
      }
    });
  }

  // Drain any queued classic-script registrations before initial render
  queued.forEach(function (entry) {
    if (Array.isArray(entry) && typeof bridge[entry[0]] === 'function') {
      bridge[entry[0]](entry[1]);
    }
  });

  // Sync initial hash route (supports reloading directly on #/monsters/ammonite/full)
  syncRouteState(state.route.section, state.route);
  applyThemeBodyClass();
  render();
})();
