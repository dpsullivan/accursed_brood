/* Accursed Brood — Companion Wiki Renderer (Brood Chronicle)
 * Renders the approved Variant D shell, Ryu (Light) & Teepo (Dark) themes,
 * Empty State, Seed-Only Mode banner, Spoiler Overview, Inspector Drawer,
 * Full-Page editorial dossier, and all compendium views.
 */
(function () {
  'use strict';

  var STAT_KEYS = ['hp', 'ap', 'pwr', 'def', 'agl', 'int'];
  var MASTER_STAT_KEYS = ['hp', 'ap', 'pwr', 'dfn', 'agi', 'int'];

  function curveLabel(c) {
    if (c === 'frontloaded') return 'Front';
    if (c === 'late_bloomer') return 'Late';
    if (c === 'linear') return 'Linear';
    return 'Vanilla';
  }

  function weaponIcon(w) {
    var s = String(w || '').toLowerCase();
    if (s.indexOf('spear') >= 0) return '⟊';
    if (s.indexOf('sword') >= 0) return '⚔';
    if (s.indexOf('dagger') >= 0 || s.indexOf('knife') >= 0) return '🗡';
    if (s.indexOf('staff') >= 0 || s.indexOf('stave') >= 0 || s.indexOf('rod') >= 0) return '✶';
    if (s.indexOf('cannon') >= 0 || s.indexOf('shell') >= 0) return '◎';
    if (s.indexOf('claw') >= 0) return '⋔';
    return '◈';
  }

  function kindIcon(kind) {
    var k = String(kind || '').toLowerCase();
    if (k.indexOf('weapon') >= 0) return '⚔';
    if (k.indexOf('armor') >= 0 || k.indexOf('shield') >= 0 || k.indexOf('helm') >= 0) return '🛡';
    if (k.indexOf('consumable') >= 0) return '✦';
    return '◈';
  }

  function inlineDiff(val, van, hasBaseline, api) {
    if (!hasBaseline || van == null) {
      return '<span class="bc-val">' + api.esc(val) + '</span>';
    }
    var d = Number(val) - Number(van);
    if (d === 0) {
      return '<span class="bc-val">' + api.esc(val) + '</span>';
    }
    return (
      '<span class="bc-val">' + api.esc(val) + '</span>' +
      '<span class="bc-delta ' + (d > 0 ? 'up' : 'down') + '">' + api.formatSigned(d) + '</span>' +
      '<span class="bc-van">v' + api.esc(van) + '</span>'
    );
  }

  function renderWindowPlaque(titleHtml, rightHtml) {
    return (
      '<div class="bc-win-hd">' +
        '<div class="bc-win-title-wrap">' +
          '<span class="bc-filigree" aria-hidden="true">❖</span>' +
          '<h2>' + titleHtml + '</h2>' +
        '</div>' +
        (rightHtml ? '<div class="bc-win-hd-right">' + rightHtml + '</div>' : '') +
      '</div>'
    );
  }

  function renderRunSelect(ctx) {
    var api = ctx.api;
    if (!ctx.runs.length) {
      return '<option value="">No local Runs discovered</option>';
    }
    return ctx.runs.map(function (r) {
      var tag = r.isExternal ? ' [External]' : '';
      var mode = r.hasBaseline === false ? ' [Seed-Only]' : '';
      return (
        '<option value="' + api.esc(r.run_id) + '"' + (ctx.state.runId === r.run_id ? ' selected' : '') + '>' +
          'Seed ' + api.esc(r.seed) + ' — ' + api.esc(r.preset) + ' (' + api.esc(r.rom_version) + ')' + tag + mode +
        '</option>'
      );
    }).join('');
  }

  function renderSeedOnlyBanner(ctx) {
    var run = ctx.run;
    if (!run || ctx.hasBaseline) return '';
    return (
      '<div class="bc-banner-warn" role="status">' +
        '<span class="bc-banner-ico" aria-hidden="true">!</span>' +
        '<div>' +
          '<strong>Seed-Only Mode (' + ctx.api.esc(run.rom_version) + ')</strong> — No locally cached Vanilla Baseline exists for <code>' + ctx.api.esc(run.rom_version) + '</code>. ' +
          'Active Run values are displayed in full; run <code>randomizer.py</code> once with a local ' + ctx.api.esc(run.rom_version) + ' ROM to cache its Vanilla Baseline and unlock diffs.' +
        '</div>' +
      '</div>'
    );
  }

  function renderEmptyState(ctx) {
    var notice = ctx.state.loadNotice
      ? '<div class="bc-banner-warn"><span class="bc-banner-ico">!</span><div>' + ctx.api.esc(ctx.state.loadNotice) + '</div></div>'
      : '';
    return (
      notice +
      '<div class="bc-window bc-empty">' +
        '<div class="bc-win-plaque"><span class="bc-filigree">✦</span><h2>COMPANION WIKI</h2><span class="bc-filigree">✦</span></div>' +
        '<div class="bc-empty-body">' +
          '<div class="bc-empty-crest" aria-hidden="true">◈</div>' +
          '<h1>Accursed Brood</h1>' +
          '<p>No local <strong>Seed Manifests</strong> were found in <code>output/seeds/</code> yet. Run the randomizer to generate your first Run and cache your local <strong>Vanilla Baseline</strong>, or load a Seed Manifest JSON file below.</p>' +
          '<div class="bc-dropzone" data-pick-json="1" role="button" tabindex="0">' +
            '<div class="bc-drop-title">Drop a Seed Manifest (<code>.json</code>) here — or click to browse</div>' +
            '<div class="bc-drop-sub">Runs 100% offline over <code>file://</code> with zero local server or build step.</div>' +
            '<div class="bc-empty-acts">' +
              '<button type="button" class="bc-btn-cerulean" data-pick-json="1">Choose Seed Manifest JSON…</button>' +
            '</div>' +
          '</div>' +
          '<pre class="bc-cli">python randomizer.py "Breath of Fire III.bin" --preset standard --seed 424242 --open-wiki</pre>' +
        '</div>' +
      '</div>'
    );
  }

  function formatMult(val) {
    var n = Number(val);
    if (!isFinite(n)) return '1x';
    return (Math.round(n * 100) / 100) + 'x';
  }

  function getVanillaCat(ctx, key) {
    if (!ctx.hasBaseline || !ctx.baseline || !ctx.baseline.categories) return {};
    return ctx.baseline.categories[key] || {};
  }

  function renderOverview(ctx) {
    var run = ctx.run;
    var api = ctx.api;
    var opts = run.options || {};
    var guard = opts.guardrails || {};
    var cats = run.categories || {};
    var chars = cats.characters || [];
    var masters = (cats.masters || []).filter(function (m) { return !m.restricted; });
    var vanChars = getVanillaCat(ctx, 'characters');
    var share = run.share_string || '';

    var partyRows = chars.map(function (c, idx) {
      var van = vanChars[c.id] || null;
      var selected = ctx.state.filters.drawerItem === ('characters:' + c.id);
      var grades = c.grades_lv40 || {};
      return (
        '<tr class="bc-clickable' + (selected ? ' selected' : '') + '" data-open-drawer="characters:' + api.esc(c.id) + '">' +
          '<td class="bc-slot-cell"><span class="bc-slot-num">' + (idx + 1) + '</span></td>' +
          '<td>' +
            '<strong>' + api.esc(c.name) + '</strong> ' +
            '<span class="bc-muted-sm">Lv' + api.esc(c.join_level) + '</span>' +
            (c.weapons && c.weapons.length
              ? '<div class="bc-sub-weapons">' + c.weapons.map(function (w) { return weaponIcon(w) + ' ' + api.esc(w); }).join(' · ') + '</div>'
              : '') +
          '</td>' +
          '<td>' +
            '<span class="bc-cerulean"><strong>' + api.esc(c.class_name) + '</strong></span>' +
            '<div class="bc-muted-sm">' + api.esc(c.role || '') + ' · ' + curveLabel(c.curve) + '</div>' +
          '</td>' +
          '<td class="bc-mono">' + inlineDiff(c.lv40.hp, van ? van.lv40.hp : null, ctx.hasBaseline, api) + '</td>' +
          '<td class="bc-mono">' + inlineDiff(c.lv40.pwr, van ? van.lv40.pwr : null, ctx.hasBaseline, api) + '</td>' +
          '<td class="bc-mono">' + inlineDiff(c.lv40.def, van ? van.lv40.def : null, ctx.hasBaseline, api) + '</td>' +
          '<td class="bc-mono">' + inlineDiff(c.lv40.int, van ? van.lv40.int : null, ctx.hasBaseline, api) + '</td>' +
          '<td class="bc-mono" style="white-space:nowrap">' +
            STAT_KEYS.map(function (k) {
              var g = grades[k] || 'C';
              return '<span class="bc-rank r-' + api.esc(g) + '" title="' + k.toUpperCase() + ': ' + api.esc(g) + '">' + api.esc(g) + '</span>';
            }).join('') +
          '</td>' +
        '</tr>'
      );
    }).join('');

    var masterRows = masters.map(function (m) {
      var selected = ctx.state.filters.drawerItem === ('masters:' + m.id);
      var modHtml = MASTER_STAT_KEYS
        .filter(function (k) { return Number(m.stats[k]) !== 0; })
        .map(function (k) {
          var v = Number(m.stats[k]);
          return '<span class="bc-mod ' + (v > 0 ? 'up' : 'down') + '">' + k.toUpperCase().slice(0, 2) + api.formatSigned(v) + '</span>';
        }).join(' ') || '<span class="bc-muted-xs">Neutral</span>';
      var skillsHtml = (m.skills || []).map(function (sk) {
        var abRoute = abilityRouteFor(sk.name, ctx.crossLinks);
        return '<span class="bc-skill-inline">Lv' + sk.level + ' <a href="' + abRoute + '" data-nav="' + abRoute + '" class="bc-link">' + api.esc(sk.name) + '</a></span>';
      }).join(' · ');
      return (
        '<tr class="bc-clickable' + (selected ? ' selected' : '') + '" data-open-drawer="masters:' + api.esc(m.id) + '">' +
          '<td><strong>' + api.esc(m.name) + '</strong><div class="bc-muted-xs">' + api.esc(m.location) + '</div></td>' +
          '<td><span class="bc-crimson-txt"><strong>' + api.esc(m.kit_name) + '</strong></span></td>' +
          '<td class="bc-mono">' + modHtml + '</td>' +
          '<td class="bc-muted-sm">' + (skillsHtml || '—') + '</td>' +
        '</tr>'
      );
    }).join('');

    var genes = cats.genes || [];
    var vanGenes = getVanillaCat(ctx, 'genes');
    var guardData = cats.guardrails || { crash_count: 0, clamp_count: 0, weapon_count: 0, weapon_items: [], clamp_items: [], crash_items: [] };
    var clampLimit = ctx.state.filters.expandedGuardrails ? 14 : 4;
    var guardHtml = (
      '<div class="bc-kpi-row">' +
        '<div class="bc-kpi"><span>Crash Fixes</span><strong>' + api.esc(guardData.crash_count || 0) + '</strong></div>' +
        '<div class="bc-kpi brass"><span>Tier Clamps</span><strong>' + api.esc(guardData.clamp_count || 0) + '</strong></div>' +
        '<div class="bc-kpi cerulean"><span>Shop Injects</span><strong>' + api.esc(guardData.weapon_count || 0) + '</strong></div>' +
      '</div>' +
      '<div class="bc-mini-hd">Weapon Accessibility Shop Adjustments</div>' +
      ((guardData.weapon_items || []).length
        ? '<ul class="bc-feed-list">' +
            guardData.weapon_items.slice(0, 5).map(function (w) {
              return (
                '<li>' +
                  '<span class="bc-tier-tag t-' + api.esc((w.tier || 'early').toLowerCase()) + '">' + api.esc(w.tier || 'Early') + '</span>' +
                  '<strong>' + api.esc(w.item || w.subject) + '</strong>' +
                  '<span class="bc-muted-sm">@ ' + api.esc(w.shop_name || w.subject) + '</span>' +
                '</li>'
              );
            }).join('') +
          '</ul>'
        : '<div class="bc-muted-sm" style="margin-bottom:8px">No shop adjustments needed in this Run.</div>') +
      '<div class="bc-mini-hd">' +
        '<span>Protected &amp; Clamped Encounters</span>' +
        ((guardData.clamp_items || []).length > 4
          ? '<button type="button" class="bc-link-btn" data-toggle-guardrails="1">' + (ctx.state.filters.expandedGuardrails ? 'Show fewer ▲' : 'Show more ▼') + '</button>'
          : '') +
      '</div>' +
      ((guardData.clamp_items || []).length
        ? '<ul class="bc-feed-list">' +
            guardData.clamp_items.slice(0, clampLimit).map(function (h) {
              return (
                '<li>' +
                  '<span class="bc-badge-lavender sm">' + api.esc(h.tag || 'Clamped') + '</span>' +
                  '<strong>' + api.esc(h.subject) + '</strong>' +
                  '<span class="bc-muted-sm">' + api.esc(h.detail) + '</span>' +
                '</li>'
              );
            }).join('') +
          '</ul>'
        : '<div class="bc-muted-sm">No encounter tier clamps triggered.</div>')
    );

    var genesHtml = genes.length
      ? '<div class="bc-gene-tiers">' +
          ['Early', 'Mid', 'Late'].map(function (tier) {
            var tierGenes = genes.filter(function (g) { return g.tier === tier; });
            return (
              '<div class="bc-gene-col">' +
                '<div class="bc-tier-cap t-' + tier.toLowerCase() + '">' + tier + ' Tier (' + tierGenes.length + ')</div>' +
                tierGenes.map(function (g) {
                  var vanG = vanGenes[g.id];
                  var vanName = vanG ? vanG.gene : g.vanilla_gene;
                  var changed = ctx.hasBaseline && vanName && g.gene !== vanName;
                  return (
                    '<div class="bc-gene-entry' + (changed ? ' is-changed' : '') + '">' +
                      '<div class="bc-gene-top">' +
                        '<strong>✦ ' + api.esc(g.gene) + '</strong>' +
                        (changed ? '<span class="bc-was-tag">was ' + api.esc(vanName) + '</span>' : '') +
                      '</div>' +
                      '<div class="bc-gene-loc" title="' + api.esc(g.location) + '">' + api.esc(g.location) + '</div>' +
                    '</div>'
                  );
                }).join('') +
              '</div>'
            );
          }).join('') +
        '</div>'
      : '<div class="bc-placeholder">No Dragon Gene placements present in this Seed Manifest.</div>';

    return (
      renderSeedOnlyBanner(ctx) +
      '<section class="bc-run-strip">' +
        '<div class="bc-run-strip-left">' +
          '<div class="bc-seed-crest">' +
            '<span class="bc-seed-lbl">SEED</span>' +
            '<strong>' + api.esc(run.seed) + '</strong>' +
          '</div>' +
          '<div class="bc-run-details">' +
            '<div class="bc-run-badges">' +
              '<span class="bc-badge-scarf">' + api.esc(run.preset || 'Custom') + '</span>' +
              '<span class="bc-badge-steel">' + api.esc(run.rom_version) + '</span>' +
              '<span class="bc-badge-steel">' + api.esc(run.version) + '</span>' +
              '<span class="bc-badge-lavender">flags: <code>' + api.esc(run.flags || 'none') + '</code></span>' +
              (ctx.isExternal ? '<span class="bc-badge-brass">External JSON</span>' : '') +
            '</div>' +
            '<div class="bc-run-opts">' +
              '<span>Classes: <strong>' + api.esc(opts.class_mode || 'legacy') + '</strong></span>' +
              '<span>Masters: <strong>' + api.esc(opts.masters || 'legacy') + '</strong></span>' +
              '<span>Genes: <strong>' + api.esc(opts.genes || 'flat') + '</strong></span>' +
              '<span>EXP <strong>' + formatMult(opts.exp_mult) + '</strong> · Zenny <strong>' + formatMult(opts.zenny_mult) + '</strong> · Drop <strong>' + formatMult(opts.drop_mult) + '</strong></span>' +
              '<span>Guardrails: <strong>' + (guard.crash ? 'Crash' : 'No-Crash') + ' / ' + (guard.tiers ? 'Tiers' : 'No-Tiers') + ' / ' + (guard.weapons ? 'Weapons' : 'No-Weapons') + '</strong></span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="bc-run-share">' +
          '<code title="' + api.esc(share) + '">' + api.esc(share || 'No share string recorded') + '</code>' +
          '<button type="button" class="bc-btn-sm" data-copy-share="1">' + (ctx.state.copiedShare ? 'Copied!' : 'Copy Share String') + '</button>' +
        '</div>' +
      '</section>' +

      '<div class="bc-bento">' +
        '<section class="bc-window span-7">' +
          renderWindowPlaque('PARTY &amp; ASSIGNED CLASSES', '<a href="#/characters" data-nav="#/characters" class="bc-hd-link">Full Roster &amp; Classes →</a>') +
          (chars.length
            ? '<div class="bc-table-wrap"><table class="bc-table">' +
                '<thead><tr><th>#</th><th>Character</th><th>Rolled Class</th><th>Lv40 HP</th><th>PWR</th><th>DEF</th><th>INT</th><th>Lv40 Ranks</th></tr></thead>' +
                '<tbody>' + partyRows + '</tbody>' +
              '</table></div>' +
              '<div class="bc-panel-foot">Click any party member to inspect Join / Lv40 / Lv99 stats &amp; spell diffs in the side drawer.</div>'
            : '<div class="bc-placeholder">No character records present in this Seed Manifest.</div>') +
        '</section>' +

        '<section class="bc-window span-5">' +
          renderWindowPlaque('GUARDRAILS HIGHLIGHTS', '<a href="#/guardrails" data-nav="#/guardrails" class="bc-hd-link">Full Report →</a>') +
          guardHtml +
        '</section>' +

        '<section class="bc-window span-5">' +
          renderWindowPlaque('DRAGON GENES <span class="bc-hd-sub">(' + api.esc(opts.genes || 'flat') + ')</span>', '<a href="#/genes" data-nav="#/genes" class="bc-hd-link">All 17 Pedestals →</a>') +
          genesHtml +
        '</section>' +

        '<section class="bc-window span-7">' +
          renderWindowPlaque('CURATED MASTERS <span class="bc-hd-sub">(' + masters.length + ' active)</span>', '<a href="#/masters" data-nav="#/masters" class="bc-hd-link">All Masters →</a>') +
          (masters.length
            ? '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
                '<thead><tr><th>Master</th><th>Kit / Role</th><th>Stat Mods</th><th>Teachable Skills</th></tr></thead>' +
                '<tbody>' + masterRows + '</tbody>' +
              '</table></div>'
            : '<div class="bc-placeholder">No Master records present in this Seed Manifest.</div>') +
        '</section>' +
      '</div>'
    );
  }

  function renderCharactersView(ctx) {
    var run = ctx.run;
    var api = ctx.api;
    var cats = run.categories || {};
    var chars = cats.characters || [];
    var classes = cats.classes || [];
    var vanChars = getVanillaCat(ctx, 'characters');
    var isClasses = ctx.state.filters.charTab === 'classes';

    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-toolbar">' +
        '<div class="bc-pills">' +
          '<button type="button" class="bc-pill' + (!isClasses ? ' active' : '') + '" data-char-tab="party">Active Party (' + chars.length + ')</button>' +
          '<button type="button" class="bc-pill' + (isClasses ? ' active' : '') + '" data-char-tab="classes">Classes Catalog (' + classes.length + ')</button>' +
        '</div>' +
        '<span class="bc-muted-sm">Click any party member for Join / Lv40 / Lv99 comparisons &amp; spell diffs</span>' +
      '</div>' +
      '<section class="bc-window">' +
        (!isClasses
          ? renderWindowPlaque('ACTIVE PARTY ROSTER', '<span class="bc-badge-lavender">Mode: ' + api.esc((run.options || {}).class_mode || 'legacy') + '</span>') +
            '<div class="bc-table-wrap"><table class="bc-table">' +
              '<thead><tr><th>#</th><th>Character</th><th>Assigned Class</th><th>Weapons</th><th>Lv40 HP</th><th>AP</th><th>PWR</th><th>DEF</th><th>AGL</th><th>INT</th><th>Lv40 Ranks</th></tr></thead>' +
              '<tbody>' +
                chars.map(function (c, idx) {
                  var van = vanChars[c.id] || null;
                  var selected = ctx.state.filters.drawerItem === ('characters:' + c.id);
                  var grades = c.grades_lv40 || {};
                  return (
                    '<tr class="bc-clickable' + (selected ? ' selected' : '') + '" data-open-drawer="characters:' + api.esc(c.id) + '">' +
                      '<td class="bc-slot-cell"><span class="bc-slot-num">' + (idx + 1) + '</span></td>' +
                      '<td><strong>' + api.esc(c.name) + '</strong> <span class="bc-muted-sm">Lv' + api.esc(c.join_level) + '</span></td>' +
                      '<td><span class="bc-cerulean"><strong>' + api.esc(c.class_name) + '</strong></span> <span class="bc-muted-sm">· ' + curveLabel(c.curve) + '</span></td>' +
                      '<td class="bc-muted-sm">' + (c.weapons || []).map(function (w) { return weaponIcon(w) + ' ' + api.esc(w); }).join(', ') + '</td>' +
                      STAT_KEYS.map(function (k) {
                        return '<td class="bc-mono">' + inlineDiff(c.lv40[k], van ? van.lv40[k] : null, ctx.hasBaseline, api) + '</td>';
                      }).join('') +
                      '<td class="bc-mono" style="white-space:nowrap">' +
                        STAT_KEYS.map(function (k) {
                          var g = grades[k] || 'C';
                          return '<span class="bc-rank r-' + api.esc(g) + '">' + api.esc(g) + '</span>';
                        }).join('') +
                      '</td>' +
                    '</tr>'
                  );
                }).join('') +
              '</tbody>' +
            '</table></div>'
          : renderWindowPlaque('PREMADE CLASSES CATALOG', '<span class="bc-muted-sm">Archetypes rolled in the active Run are highlighted</span>') +
            '<div class="bc-table-wrap"><table class="bc-table">' +
              '<thead><tr><th>Archetype</th><th>Role &amp; Curve</th><th>Weapons</th><th>Lv40 Ranks</th><th>Lv40 / Lv99 HP</th><th>Lv40 / Lv99 PWR</th><th>Lv40 / Lv99 INT</th><th>Rolled In Run</th></tr></thead>' +
              '<tbody>' +
                classes.map(function (cl) {
                  var owner = chars.find(function (c) { return c.class_id === cl.id; });
                  var grades = cl.grades_lv40 || {};
                  var t40 = (cl.totals && cl.totals.lv40) || {};
                  var t99 = (cl.totals && cl.totals.lv99) || {};
                  return (
                    '<tr class="' + (owner ? 'row-rolled' : '') + '">' +
                      '<td><strong>' + api.esc(cl.name) + '</strong><div class="bc-muted-xs">' + api.esc(cl.description || '') + '</div></td>' +
                      '<td>' + api.esc(cl.role || '') + ' <span class="bc-badge-steel sm">' + curveLabel(cl.curve) + '</span></td>' +
                      '<td class="bc-muted-sm">' + (cl.weapons || []).map(function (w) { return weaponIcon(w) + ' ' + api.esc(w); }).join(', ') + '</td>' +
                      '<td class="bc-mono" style="white-space:nowrap">' +
                        STAT_KEYS.map(function (k) {
                          var g = grades[k] || 'C';
                          return '<span class="bc-rank r-' + api.esc(g) + '">' + api.esc(g) + '</span>';
                        }).join('') +
                      '</td>' +
                      '<td class="bc-mono">' + api.esc(t40.hp) + ' / ' + api.esc(t99.hp) + '</td>' +
                      '<td class="bc-mono">' + api.esc(t40.pwr) + ' / ' + api.esc(t99.pwr) + '</td>' +
                      '<td class="bc-mono">' + api.esc(t40.int) + ' / ' + api.esc(t99.int) + '</td>' +
                      '<td>' + (owner ? '<span class="bc-badge-cerulean">Rolled: ' + api.esc(owner.name) + '</span>' : '<span class="bc-muted-sm">Unrolled</span>') + '</td>' +
                    '</tr>'
                  );
                }).join('') +
              '</tbody>' +
            '</table></div>') +
      '</section>'
    );
  }

  function renderMastersView(ctx) {
    var run = ctx.run;
    var api = ctx.api;
    var masters = (run.categories && run.categories.masters) || [];
    var vanMasters = getVanillaCat(ctx, 'masters');

    return (
      renderSeedOnlyBanner(ctx) +
      '<section class="bc-window">' +
        renderWindowPlaque('MASTERS (' + masters.length + ')', '<span class="bc-muted-sm">Click any Master to inspect per-level modifier diffs &amp; skills</span>') +
        '<div class="bc-table-wrap"><table class="bc-table">' +
          '<thead><tr><th>Master</th><th>Location</th><th>Kit / Role</th><th>HP</th><th>AP</th><th>PWR</th><th>DFN</th><th>AGI</th><th>INT</th><th>Apprenticeship Skills</th></tr></thead>' +
          '<tbody>' +
            masters.map(function (m) {
              var van = vanMasters[m.id] || null;
              var selected = ctx.state.filters.drawerItem === ('masters:' + m.id);
              return (
                '<tr class="bc-clickable' + (selected ? ' selected' : '') + '" data-open-drawer="masters:' + api.esc(m.id) + '">' +
                  '<td><strong>' + api.esc(m.name) + '</strong>' + (m.restricted ? ' <span class="bc-badge-steel sm">Restricted</span>' : '') + '</td>' +
                  '<td class="bc-muted-sm">' + api.esc(m.location) + '</td>' +
                  '<td><span class="bc-crimson-txt"><strong>' + api.esc(m.kit_name) + '</strong></span><div class="bc-muted-xs">' + api.esc(m.role || '') + '</div></td>' +
                  MASTER_STAT_KEYS.map(function (k) {
                    var v = Number(m.stats[k]) || 0;
                    var vv = van && van.stats ? Number(van.stats[k]) : null;
                    var diffTag = (ctx.hasBaseline && vv != null && v !== vv) ? '<div class="bc-van">v' + api.formatSigned(vv) + '</div>' : '';
                    return '<td class="bc-mono"><span class="' + (v > 0 ? 'up' : (v < 0 ? 'down' : 'bc-muted-sm')) + '">' + api.formatSigned(v) + '</span>' + diffTag + '</td>';
                  }).join('') +
                  '<td class="bc-muted-sm">' + ((m.skills || []).map(function (sk) {
                    var abRoute = abilityRouteFor(sk.name, ctx.crossLinks);
                    return 'Lv' + sk.level + ' <a href="' + abRoute + '" data-nav="' + abRoute + '" class="bc-link">' + api.esc(sk.name) + '</a>';
                  }).join(' · ') || '—') + '</td>' +
                '</tr>'
              );
            }).join('') +
          '</tbody>' +
        '</table></div>' +
      '</section>'
    );
  }

  function renderMonstersView(ctx) {
    var api = ctx.api;
    var monsters = (ctx.run.categories && ctx.run.categories.monsters) || [];
    var vanMonsters = getVanillaCat(ctx, 'monsters');
    var tiers = ['All', 'Early', 'Mid', 'Late', 'Protected'];
    var q = String(ctx.state.filters.listQuery || '').trim().toLowerCase();

    var list = monsters.filter(function (m) {
      if (ctx.state.filters.changedOnly && ctx.hasBaseline && !m.changed) return false;
      if (ctx.state.filters.monsterTier !== 'All' && m.tier !== ctx.state.filters.monsterTier) return false;
      if (q) {
        var areaText = (m.areas || []).join(' ');
        var slotText = (m.variants || []).map(function (v) { return v.slot; }).join(' ');
        var hay = (m.name + ' ' + areaText + ' ' + slotText).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });

    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-toolbar">' +
        '<div class="bc-pills">' +
          tiers.map(function (t) {
            return '<button type="button" class="bc-pill' + (ctx.state.filters.monsterTier === t ? ' active' : '') + '" data-filter-tier="' + t + '">' + t + '</button>';
          }).join('') +
        '</div>' +
        '<input type="search" class="bc-filter-input" data-list-query="1" placeholder="Filter monsters, areas, slots…" value="' + api.esc(ctx.state.filters.listQuery || '') + '" />' +
        (ctx.hasBaseline
          ? '<label class="bc-check-toggle"><input type="checkbox" data-filter-changed="1"' + (ctx.state.filters.changedOnly ? ' checked' : '') + ' /> Changed only</label>'
          : '') +
      '</div>' +
      '<section class="bc-window">' +
        renderWindowPlaque('BESTIARY (' + list.length + ' LOGICAL MONSTERS)', '<span class="bc-muted-sm">Dummy slots removed · Multi-slot variants grouped</span>') +
        '<div class="bc-table-wrap"><table class="bc-table">' +
          '<thead><tr><th>Monster</th><th>Tier</th><th>Slots</th><th>HP (Primary)</th><th>EMI Spawn Areas</th><th>Steal / Drop</th><th>Learnable (★)</th></tr></thead>' +
          '<tbody>' +
            (list.map(function (m) {
              var v0 = (m.variants && m.variants[0]) || null;
              if (!v0) return '';
              var van0 = vanMonsters[v0.slot] || null;
              var learnSet = [];
              var seenLearn = {};
              (m.variants || []).forEach(function (v) {
                (v.abilities || []).forEach(function (a) {
                  if (a.learnable && !seenLearn[a.name]) {
                    seenLearn[a.name] = true;
                    learnSet.push(a);
                  }
                });
              });
              var selected = ctx.state.filters.drawerItem === ('monsters:' + m.id);
              var lootParts = [];
              if (v0.steal && v0.steal.item) lootParts.push('S: ' + renderItemLink(v0.steal.item, v0.steal.item_id, api, ctx.crossLinks));
              if (v0.drop && v0.drop.item) lootParts.push('D: ' + renderItemLink(v0.drop.item, v0.drop.item_id, api, ctx.crossLinks));
              return (
                '<tr class="bc-clickable' + (selected ? ' selected' : '') + '" data-open-drawer="monsters:' + api.esc(m.id) + '">' +
                  '<td>' +
                    '<strong>' + api.esc(m.name) + '</strong>' +
                    (m.is_boss ? ' <span class="bc-badge-scarf sm">BOSS</span>' : '') +
                    (m.guardrail_note ? ' <span class="bc-badge-brass sm">GUARD</span>' : '') +
                  '</td>' +
                  '<td><span class="bc-tier-tag t-' + api.esc((m.tier || 'late').toLowerCase()) + '">' + api.esc(m.tier) + '</span></td>' +
                  '<td class="bc-mono bc-muted-sm">' + (m.variants || []).map(function (v) { return api.esc(v.slot); }).join(', ') + '</td>' +
                  '<td class="bc-mono">' + inlineDiff(v0.stats.hp, van0 && van0.stats ? van0.stats.hp : null, ctx.hasBaseline, api) + '</td>' +
                  '<td class="bc-muted-sm">' + ((m.areas || []).slice(0, 3).map(api.esc).join(', ') + ((m.areas || []).length > 3 ? ' +' + ((m.areas || []).length - 3) : '') || '—') + '</td>' +
                  '<td class="bc-muted-sm">' + (lootParts.join(' · ') || '—') + '</td>' +
                  '<td>' +
                    (learnSet.length
                      ? learnSet.map(function (a) {
                          return '<a href="#/abilities/' + encodeURIComponent(a.id) + '" data-nav="#/abilities/' + encodeURIComponent(a.id) + '" class="bc-skill-pill learnable">' + api.esc(a.name) + ' ★</a>';
                        }).join(' ')
                      : '<span class="bc-muted-sm">—</span>') +
                  '</td>' +
                '</tr>'
              );
            }).join('') || '<tr><td colspan="7" class="bc-muted-sm">No monsters match the active filter.</td></tr>') +
          '</tbody>' +
        '</table></div>' +
      '</section>'
    );
  }

  function renderInspectorDrawer(ctx) {
    var target = ctx.state.filters.drawerItem;
    if (!target || !ctx.run) return '';
    var idx = target.indexOf(':');
    var kind = target.slice(0, idx);
    var id = target.slice(idx + 1);
    var api = ctx.api;
    var cats = ctx.run.categories || {};
    var body = '';
    var kicker = 'INSPECTOR';
    var title = '';
    var fullRoute = '#/' + kind + '/' + encodeURIComponent(id) + '/full';

    if (kind === 'monsters') {
      var mObj = (cats.monsters || []).find(function (x) { return x.id === id; });
      if (!mObj) return '';
      var vanMonsters = getVanillaCat(ctx, 'monsters');
      kicker = (mObj.tier || 'Late').toUpperCase() + (mObj.is_boss ? ' BOSS' : ' ENEMY') + ' · ' + mObj.variants.length + ' VARIANT' + (mObj.variants.length > 1 ? 'S' : '');
      title = mObj.name;
      body = (
        '<div class="bc-drawer-areas"><strong>EMI Areas:</strong> ' + ((mObj.areas || []).map(api.esc).join(' · ') || 'Unmapped / Event') + '</div>' +
        (mObj.guardrail_note ? '<div class="bc-guard-note"><strong>Guardrail:</strong> ' + api.esc(mObj.guardrail_note) + '</div>' : '') +
        (mObj.variants || []).map(function (v) {
          var vanV = vanMonsters[v.slot] || null;
          var vanStats = (vanV && vanV.stats) || null;
          var vanRes = (vanV && vanV.resistances) || null;
          return (
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd">' +
                '<span>SLOT <code>' + api.esc(v.slot) + '</code> — <strong>' + api.esc(v.label) + '</strong></span>' +
                '<span class="bc-lv-tag">LV ' + api.esc(v.lv) + '</span>' +
              '</div>' +
              '<div class="bc-stat-bars">' +
                MASTER_STAT_KEYS.map(function (k) {
                  var curVal = Number(v.stats[k]) || 0;
                  var oldVal = vanStats ? Number(vanStats[k]) : null;
                  var floorMax = k === 'hp' ? 500 : (k === 'ap' ? 100 : 240);
                  var maxVal = Math.max(curVal, oldVal != null ? oldVal : 0, floorMax);
                  var pct = Math.min(100, Math.round((curVal / maxVal) * 100));
                  var vanPct = oldVal != null ? Math.min(100, Math.round((oldVal / maxVal) * 100)) : 0;
                  return (
                    '<div class="bc-bar-row">' +
                      '<span class="bc-bar-lbl">' + k.toUpperCase() + '</span>' +
                      '<div class="bc-bar-track">' +
                        '<div class="bc-bar-fill" style="width:' + pct + '%"></div>' +
                        (ctx.hasBaseline && oldVal != null ? '<div class="bc-bar-ghost" style="left:' + vanPct + '%" title="Vanilla Baseline: ' + oldVal + '"></div>' : '') +
                      '</div>' +
                      '<span class="bc-bar-num bc-mono">' + inlineDiff(curVal, oldVal, ctx.hasBaseline, api) + '</span>' +
                    '</div>'
                  );
                }).join('') +
              '</div>' +
              '<div class="bc-loot-row" style="margin-top:6px;padding-top:6px">' +
                '<span><strong>EXP:</strong> <span class="bc-mono">' + inlineDiff(v.exp, vanV ? vanV.exp : null, ctx.hasBaseline, api) + '</span></span>' +
                '<span><strong>Zenny:</strong> <span class="bc-mono">' + inlineDiff(v.zenny, vanV ? vanV.zenny : null, ctx.hasBaseline, api) + '</span></span>' +
              '</div>' +
              '<div class="bc-res-grid">' +
                ctx.elements.map(function (el, i) {
                  var cur = window.WikiData.decodeRes(v.resistances && v.resistances[i]);
                  var old = vanRes && vanRes[i] ? window.WikiData.decodeRes(vanRes[i]) : null;
                  var ch = ctx.hasBaseline && old && cur.code !== old.code;
                  return (
                    '<div class="bc-res-cell tone-' + api.esc(cur.tone) + (ch ? ' is-diff' : '') + '" title="' + api.esc(el) + ': ' + api.esc(cur.label) + (ch ? ' (was ' + api.esc(old.label) + ')' : '') + '">' +
                      '<span>' + api.esc(el.slice(0, 4)) + '</span>' +
                      '<strong>' + api.esc(cur.short) + '</strong>' +
                      (ch ? '<em>v' + api.esc(old.short) + '</em>' : '') +
                    '</div>'
                  );
                }).join('') +
              '</div>' +
              '<div class="bc-loot-row">' +
                '<span><strong>Steal:</strong> ' + (v.steal && v.steal.item ? renderItemLink(v.steal.item, v.steal.item_id, api) + ' (' + v.steal.rate + '%)' : '<span class="bc-muted-sm">None</span>') + '</span>' +
                '<span><strong>Drop:</strong> ' + (v.drop && v.drop.item ? renderItemLink(v.drop.item, v.drop.item_id, api) + ' (' + v.drop.rate + '%)' : '<span class="bc-muted-sm">None</span>') + '</span>' +
              '</div>' +
              '<div class="bc-chip-row">' +
                ((v.abilities || []).length
                  ? v.abilities.map(function (a) {
                      var ck = 'skill:' + window.WikiData.normalizeKey(a.name);
                      var abRoute = '#/abilities/' + encodeURIComponent(a.id);
                      return (
                        '<span class="bc-skill-pill' + (a.learnable ? ' learnable' : '') + '">' +
                          (a.learnable ? '<input type="checkbox" data-check-key="' + api.esc(ck) + '"' + (api.isChecked(ck) ? ' checked' : '') + ' title="Track in Checklist" />' : '') +
                          '<a href="' + abRoute + '" data-nav="' + abRoute + '">' + api.esc(a.name) + (a.learnable ? ' ★' : '') + '</a>' +
                        '</span>'
                      );
                    }).join('')
                  : '<span class="bc-muted-sm">No active abilities.</span>') +
              '</div>' +
            '</div>'
          );
        }).join('')
      );
    } else if (kind === 'characters') {
      var c = (cats.characters || []).find(function (x) { return x.id === id; });
      if (!c) return '';
      var van = getVanillaCat(ctx, 'characters')[c.id] || null;
      var vanSpellSet = new Set(((van && van.spells) || []).map(function (s) { return window.WikiData.normalizeKey(s.name); }));
      kicker = 'PARTY MEMBER · JOIN LV ' + c.join_level + ' · ' + curveLabel(c.curve).toUpperCase();
      title = c.name + ' → ' + c.class_name;
      body = (
        '<div class="bc-drawer-areas"><strong>' + api.esc(c.role || '') + '</strong>' + (c.description ? ' — ' + api.esc(c.description) : '') + '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>JOIN / LV40 / LV99' + (ctx.hasBaseline ? ' VS VANILLA' : '') + '</span></div>' +
          '<table class="bc-table bc-table-tight">' +
            '<thead><tr><th>Stat</th><th>Rk</th><th>Join</th><th>Lv40</th><th>Lv99</th></tr></thead>' +
            '<tbody>' +
              STAT_KEYS.map(function (k) {
                var g = (c.grades_lv40 && c.grades_lv40[k]) || 'C';
                return (
                  '<tr>' +
                    '<td><strong>' + k.toUpperCase() + '</strong></td>' +
                    '<td><span class="bc-rank r-' + api.esc(g) + '">' + api.esc(g) + '</span></td>' +
                    '<td class="bc-mono">' + inlineDiff(c.join[k], van ? van.join[k] : null, ctx.hasBaseline, api) + '</td>' +
                    '<td class="bc-mono">' + inlineDiff(c.lv40[k], van ? van.lv40[k] : null, ctx.hasBaseline, api) + '</td>' +
                    '<td class="bc-mono">' + inlineDiff(c.lv99[k], van ? van.lv99[k] : null, ctx.hasBaseline, api) + '</td>' +
                  '</tr>'
                );
              }).join('') +
            '</tbody>' +
          '</table>' +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>ALLOWED WEAPONS &amp; GEAR CATEGORIES</span></div>' +
          '<div class="bc-chip-row">' +
            (c.weapons || []).map(function (w) { return '<span class="bc-badge-cerulean">' + weaponIcon(w) + ' ' + api.esc(w) + '</span>'; }).join('') +
            (c.gear || []).map(function (g) { return '<span class="bc-badge-steel">' + api.esc(g.replace(/_/g, ' ')) + '</span>'; }).join('') +
          '</div>' +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>LEVEL-UP SPELLS (' + (c.spells || []).length + ')</span></div>' +
          '<div class="bc-chip-row">' +
            ((c.spells || []).length
              ? c.spells.map(function (sp) {
                  var isAdded = ctx.hasBaseline && van && !vanSpellSet.has(window.WikiData.normalizeKey(sp.name));
                  var abRoute = abilityRouteFor(sp.name, ctx.crossLinks);
                  return '<a href="' + abRoute + '" data-nav="' + abRoute + '" class="bc-skill-pill' + (isAdded ? ' learnable' : '') + '"><code>Lv' + sp.level + '</code> ' + api.esc(sp.name) + '</a>';
                }).join('')
              : '<span class="bc-muted-sm">No level-up spells.</span>') +
          '</div>' +
          (function () {
            if (!ctx.hasBaseline || !van || !(van.spells || []).length) return '';
            var curSpellSet = new Set((c.spells || []).map(function (s) { return window.WikiData.normalizeKey(s.name); }));
            var removed = van.spells.filter(function (sp) { return !curSpellSet.has(window.WikiData.normalizeKey(sp.name)); });
            if (!removed.length) return '';
            return (
              '<div class="bc-mini-hd" style="margin-top:10px">Removed Vanilla Spells (' + removed.length + ')</div>' +
              '<div class="bc-chip-row">' +
                removed.map(function (sp) {
                  return '<span class="bc-skill-pill" style="text-decoration:line-through;opacity:0.7"><code>Lv' + sp.level + '</code> ' + api.esc(sp.name) + '</span>';
                }).join('') +
              '</div>'
            );
          })() +
        '</div>'
      );
    } else if (kind === 'masters') {
      var m = (cats.masters || []).find(function (x) { return x.id === id; });
      if (!m) return '';
      var vanM = getVanillaCat(ctx, 'masters')[m.id] || null;
      kicker = (m.restricted ? 'RESTRICTED MASTER' : 'MASTER') + ' · ' + m.location.toUpperCase();
      title = m.name + ' — ' + m.kit_name;
      body = (
        '<div class="bc-drawer-areas"><strong>' + api.esc(m.role || '') + '</strong>' + (m.description ? ' — ' + api.esc(m.description) : '') + '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>PER-LEVEL STAT MODIFIERS' + (ctx.hasBaseline ? ' VS VANILLA' : '') + '</span></div>' +
          '<div class="bc-mod-grid">' +
            MASTER_STAT_KEYS.map(function (k) {
              var v = Number(m.stats[k]) || 0;
              var vv = vanM && vanM.stats ? Number(vanM.stats[k]) : null;
              return (
                '<div class="bc-mod-tile">' +
                  '<span>' + k.toUpperCase() + '</span>' +
                  '<strong class="' + (v > 0 ? 'up' : (v < 0 ? 'down' : '')) + '">' + api.formatSigned(v) + '</strong>' +
                  (ctx.hasBaseline && vv != null ? '<em>van ' + api.formatSigned(vv) + '</em>' : '') +
                '</div>'
              );
            }).join('') +
          '</div>' +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>APPRENTICESHIP SKILLS (' + (m.skills || []).length + ')</span></div>' +
          ((m.skills || []).length
            ? '<ul class="bc-feed-list">' +
                m.skills.map(function (sk, idx) {
                  var ck = 'master:' + m.id + ':' + window.WikiData.normalizeKey(sk.name);
                  var vanSk = vanM && vanM.skills && vanM.skills[idx] ? vanM.skills[idx] : null;
                  return (
                    '<li>' +
                      '<input type="checkbox" data-check-key="' + api.esc(ck) + '"' + (api.isChecked(ck) ? ' checked' : '') + ' />' +
                      '<code>+' + sk.level + 'Lv</code> ' +
                      renderAbilityLink(sk.name, api, ctx.crossLinks) +
                      (ctx.hasBaseline && vanSk && vanSk.name !== sk.name ? '<span class="bc-feed-right">was ' + api.esc(vanSk.name) + '</span>' : '') +
                    '</li>'
                  );
                }).join('') +
              '</ul>'
            : '<div class="bc-muted-sm">This Master teaches no apprenticeship skills.</div>') +
        '</div>'
      );
    } else if (kind === 'abilities') {
      var ab = (cats.abilities || []).find(function (x) { return x.id === id; });
      if (!ab) return '';
      var abSrc = window.WikiData.getAbilitySources(ctx.crossLinks, ab.name);
      kicker = 'UNIFIED ABILITY · ' + (ab.category || 'Skill').toUpperCase();
      title = ab.name + ' (' + ab.ap + ' AP)';
      body = (
        '<div class="bc-drawer-areas"><strong>' + api.esc(ab.element) + '</strong> · Target: ' + api.esc(ab.target) + (ab.power ? ' · Power: ' + api.esc(ab.power) : '') + '</div>' +
        '<div class="bc-guard-note"><strong>Merged ROM Slots:</strong> ' + ((ab.merged_slots || []).map(api.esc).join(' + ') || 'Single slot') + '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>CHARACTERS BY LEVEL-UP (' + abSrc.characters.length + ')</span></div>' +
          (abSrc.characters.length
            ? '<ul class="bc-feed-list">' + abSrc.characters.map(function (c) {
                return '<li><a href="#/characters/' + encodeURIComponent(c.id) + '" data-nav="#/characters/' + encodeURIComponent(c.id) + '" class="bc-link"><strong>' + api.esc(c.name) + '</strong></a> <span class="bc-muted-sm">(' + api.esc(c.class_name) + ')</span> <span class="bc-feed-right">Lv' + c.level + '</span></li>';
              }).join('') + '</ul>'
            : '<div class="bc-muted-sm">No playable character learns this via level-up.</div>') +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>MASTERS APPRENTICESHIP (' + abSrc.masters.length + ')</span></div>' +
          (abSrc.masters.length
            ? '<ul class="bc-feed-list">' + abSrc.masters.map(function (m) {
                return '<li><a href="#/masters/' + encodeURIComponent(m.id) + '" data-nav="#/masters/' + encodeURIComponent(m.id) + '" class="bc-link"><strong>' + api.esc(m.name) + '</strong></a> <span class="bc-muted-sm">(' + api.esc(m.kit_name) + ')</span> <span class="bc-feed-right">+' + m.level + 'Lv</span></li>';
              }).join('') + '</ul>'
            : '<div class="bc-muted-sm">No Master teaches this skill.</div>') +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>MONSTERS VIA EXAMINE (' + abSrc.monsters.length + ')</span></div>' +
          (abSrc.monsters.length
            ? '<ul class="bc-feed-list">' + abSrc.monsters.map(function (m) {
                return '<li><a href="#/monsters/' + encodeURIComponent(m.id) + '" data-nav="#/monsters/' + encodeURIComponent(m.id) + '" class="bc-link"><strong>' + api.esc(m.name) + '</strong></a> <code class="bc-muted-xs">' + api.esc(m.slot) + '</code> <span class="bc-tier-tag t-' + api.esc((m.tier || 'late').toLowerCase()) + '">' + api.esc(m.tier) + '</span> <span class="bc-feed-right">' + api.esc((m.areas && m.areas[0]) || 'Unmapped') + '</span></li>';
              }).join('') + '</ul>'
            : '<div class="bc-muted-sm">Not examinable from any monster in this Run.</div>') +
        '</div>'
      );
    } else if (kind === 'equipment') {
      var eq = (cats.equipment || []).find(function (x) { return x.id === id; });
      if (!eq) return '';
      var vanEq = getVanillaCat(ctx, 'equipment')[eq.id] || null;
      var eqSrc = window.WikiData.getItemSources(ctx.crossLinks, eq);
      var eqStats = eq.stats || {};
      var equipStr = (eq.equip || []).join(', ') || 'None / Consumable';
      var vanEquipStr = vanEq && vanEq.equip ? (vanEq.equip.join(', ') || 'None') : null;
      var equipChanged = ctx.hasBaseline && vanEq && vanEquipStr !== ((eq.equip || []).join(', ') || 'None');
      var priceChanged = ctx.hasBaseline && vanEq && vanEq.price != null && vanEq.price !== eq.price;
      kicker = (eq.kind || 'ITEM').toUpperCase();
      title = kindIcon(eq.kind) + ' ' + eq.name;
      body = (
        (eqStats.elements && eqStats.elements.length ? '<div class="bc-drawer-areas"><strong>Elements:</strong> ' + eqStats.elements.map(api.esc).join(', ') + '</div>' : '') +
        '<div class="bc-kpi-row">' +
          '<div class="bc-kpi"><span>ATK</span><strong>' + api.esc(eqStats.atk || 0) + '</strong></div>' +
          '<div class="bc-kpi"><span>DEF</span><strong>' + api.esc(eqStats.def || 0) + '</strong></div>' +
          '<div class="bc-kpi"><span>WT</span><strong>' + api.esc(eqStats.wt || 0) + '</strong></div>' +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>MUTABLE FIELDS' + (ctx.hasBaseline ? ' (VANILLA VS RUN)' : '') + '</span></div>' +
          '<ul class="bc-feed-list">' +
            '<li><strong>Equipable By:</strong> ' + api.esc(equipStr) + (equipChanged ? ' <span class="bc-was-tag">was ' + api.esc(vanEquipStr) + '</span>' : '') + '</li>' +
            '<li><strong>Shop Price:</strong> ' + (eq.price ? api.esc(eq.price) + ' Z' : 'Not sold') + (priceChanged ? ' <span class="bc-was-tag">was ' + (vanEq.price ? api.esc(vanEq.price) + ' Z' : 'None') + '</span>' : '') + '</li>' +
          '</ul>' +
        '</div>' +
        '<div class="bc-drawer-card">' +
          '<div class="bc-drawer-card-hd"><span>ACQUISITION SOURCES (' + (eqSrc.shops.length + eqSrc.manillos.length + eqSrc.chests.length + eqSrc.monsters.length) + ')</span></div>' +
          ((eqSrc.shops.length + eqSrc.manillos.length + eqSrc.chests.length + eqSrc.monsters.length)
            ? '<ul class="bc-feed-list">' +
                eqSrc.shops.map(function (s) {
                  return '<li><span class="bc-badge-steel sm">Shop</span> <a href="#/shops" data-nav="#/shops" class="bc-link">' + api.esc(s.name) + '</a>' + (s.guardrail ? ' <span class="bc-badge-brass sm">' + api.esc(s.guardrail) + '</span>' : '') + ' <span class="bc-feed-right">' + api.esc(s.price) + 'Z</span></li>';
                }).join('') +
                eqSrc.manillos.map(function (m) {
                  return '<li><span class="bc-badge-lavender sm">Manillo</span> <a href="#/manillos" data-nav="#/manillos" class="bc-link">' + api.esc(m.name) + '</a> <span class="bc-feed-right">' + api.esc(m.cost) + '</span></li>';
                }).join('') +
                eqSrc.chests.map(function (ch) {
                  return '<li><span class="bc-badge-brass sm">Chest ' + api.esc(ch.id) + '</span> <a href="#/chests" data-nav="#/chests" class="bc-link">' + api.esc(ch.area) + '</a> <span class="bc-feed-right">' + api.esc(ch.tier) + '</span></li>';
                }).join('') +
                eqSrc.monsters.map(function (m) {
                  return '<li><span class="bc-badge-scarf sm">' + api.esc(m.method) + '</span> <a href="#/monsters/' + encodeURIComponent(m.id) + '" data-nav="#/monsters/' + encodeURIComponent(m.id) + '" class="bc-link">' + api.esc(m.name) + '</a> <code class="bc-muted-xs">' + api.esc(m.slot) + '</code> <span class="bc-feed-right">' + m.rate + '%</span></li>';
                }).join('') +
              '</ul>'
            : '<div class="bc-muted-sm">No Shop, Manillo, Chest, or Monster drop/steal source recorded.</div>') +
        '</div>'
      );
    } else {
      return '';
    }

    return (
      '<aside class="bc-drawer" aria-label="Inspector Drawer">' +
        '<div class="bc-drawer-hd">' +
          '<div>' +
            '<div class="bc-drawer-kicker">' + api.esc(kicker) + '</div>' +
            '<h3>' + api.esc(title) + '</h3>' +
          '</div>' +
          '<div class="bc-drawer-acts">' +
            '<button type="button" class="bc-btn-xs" data-expand-full="' + api.esc(fullRoute) + '">Full Page ↗</button>' +
            '<button type="button" class="bc-btn-xs" data-close-drawer="1" title="Close Inspector (Esc)">✕</button>' +
          '</div>' +
        '</div>' +
        '<div class="bc-drawer-body">' + body + '</div>' +
      '</aside>'
    );
  }

  function renderFullPageDetail(ctx, section, id) {
    var api = ctx.api;
    var cats = ctx.run.categories || {};

    if (section === 'monsters') {
      var m = (cats.monsters || []).find(function (x) { return x.id === id; });
      if (!m) return '';
      var vanMonsters = getVanillaCat(ctx, 'monsters');
      return (
        renderSeedOnlyBanner(ctx) +
        '<div class="bc-crumb"><a href="#/monsters" data-nav="#/monsters">← Back to Bestiary List</a> / <strong>' + api.esc(m.name) + '</strong></div>' +
        '<section class="bc-window">' +
          renderWindowPlaque(api.esc(m.name.toUpperCase()) + ' <span class="bc-tier-tag t-' + api.esc((m.tier || 'late').toLowerCase()) + '">' + api.esc(m.tier) + (m.is_boss ? ' Boss' : '') + '</span>', '<span class="bc-muted-sm">' + ((m.areas || []).map(api.esc).join(' · ') || 'Unmapped / Event') + '</span>') +
          (m.guardrail_note ? '<div class="bc-guard-note"><strong>Guardrail Intervention:</strong> ' + api.esc(m.guardrail_note) + '</div>' : '') +
          '<div class="bc-dossier-grid">' +
            (m.variants || []).map(function (v) {
              var vanV = vanMonsters[v.slot] || null;
              var vanStats = (vanV && vanV.stats) || null;
              var vanRes = (vanV && vanV.resistances) || null;
              var showDiff = ctx.hasBaseline && !!vanStats;
              return (
                '<article class="bc-drawer-card">' +
                  '<div class="bc-drawer-card-hd"><span>SLOT <code>' + api.esc(v.slot) + '</code> — <strong>' + api.esc(v.label) + '</strong></span><span class="bc-lv-tag">LV ' + api.esc(v.lv) + '</span></div>' +
                  '<table class="bc-table bc-table-tight">' +
                    '<thead><tr><th>Stat</th>' + (showDiff ? '<th>Vanilla</th>' : '') + '<th>Active Run</th>' + (showDiff ? '<th>Delta</th>' : '') + '</tr></thead>' +
                    '<tbody>' +
                      MASTER_STAT_KEYS.map(function (k) {
                        var cur = Number(v.stats[k]) || 0;
                        var old = vanStats ? Number(vanStats[k]) : 0;
                        var d = cur - old;
                        return (
                          '<tr class="' + (showDiff && d !== 0 ? 'row-diff' : '') + '">' +
                            '<td><strong>' + k.toUpperCase() + '</strong></td>' +
                            (showDiff ? '<td class="bc-mono bc-muted-sm">' + old + '</td>' : '') +
                            '<td class="bc-mono"><strong>' + cur + '</strong></td>' +
                            (showDiff ? '<td class="bc-mono"><span class="bc-delta ' + (d === 0 ? 'same' : (d > 0 ? 'up' : 'down')) + '">' + (d === 0 ? '—' : api.formatSigned(d)) + '</span></td>' : '') +
                          '</tr>'
                        );
                      }).join('') +
                      '<tr class="' + (showDiff && v.exp !== vanV.exp ? 'row-diff' : '') + '">' +
                        '<td><strong>EXP</strong></td>' +
                        (showDiff ? '<td class="bc-mono bc-muted-sm">' + vanV.exp + '</td>' : '') +
                        '<td class="bc-mono"><strong>' + v.exp + '</strong></td>' +
                        (showDiff ? '<td class="bc-mono"><span class="bc-delta ' + (v.exp === vanV.exp ? 'same' : (v.exp > vanV.exp ? 'up' : 'down')) + '">' + (v.exp === vanV.exp ? '—' : api.formatSigned(v.exp - vanV.exp)) + '</span></td>' : '') +
                      '</tr>' +
                      '<tr class="' + (showDiff && v.zenny !== vanV.zenny ? 'row-diff' : '') + '">' +
                        '<td><strong>ZENNY</strong></td>' +
                        (showDiff ? '<td class="bc-mono bc-muted-sm">' + vanV.zenny + '</td>' : '') +
                        '<td class="bc-mono"><strong>' + v.zenny + '</strong></td>' +
                        (showDiff ? '<td class="bc-mono"><span class="bc-delta ' + (v.zenny === vanV.zenny ? 'same' : (v.zenny > vanV.zenny ? 'up' : 'down')) + '">' + (v.zenny === vanV.zenny ? '—' : api.formatSigned(v.zenny - vanV.zenny)) + '</span></td>' : '') +
                      '</tr>' +
                    '</tbody>' +
                  '</table>' +
                  '<div class="bc-mini-hd" style="margin-top:10px">Elemental &amp; Status Resistances</div>' +
                  '<div class="bc-res-grid">' +
                    ctx.elements.map(function (el, i) {
                      var cur = window.WikiData.decodeRes(v.resistances && v.resistances[i]);
                      var old = vanRes && vanRes[i] ? window.WikiData.decodeRes(vanRes[i]) : null;
                      var ch = ctx.hasBaseline && old && cur.code !== old.code;
                      return (
                        '<div class="bc-res-cell tone-' + api.esc(cur.tone) + (ch ? ' is-diff' : '') + '">' +
                          '<span>' + api.esc(el) + '</span>' +
                          '<strong>' + api.esc(cur.label) + ' (' + api.esc(cur.short) + ')</strong>' +
                          (ch ? '<em>was ' + api.esc(old.short) + '</em>' : '') +
                        '</div>'
                      );
                    }).join('') +
                  '</div>' +
                  '<div class="bc-loot-row">' +
                    '<span><strong>Steal:</strong> ' + (v.steal && v.steal.item ? renderItemLink(v.steal.item, v.steal.item_id, api) + ' (' + v.steal.rate + '%)' : 'None') + '</span>' +
                    '<span><strong>Drop:</strong> ' + (v.drop && v.drop.item ? renderItemLink(v.drop.item, v.drop.item_id, api) + ' (' + v.drop.rate + '%)' : 'None') + '</span>' +
                  '</div>' +
                  '<div class="bc-chip-row">' +
                    ((v.abilities || []).map(function (a) {
                      var ck = 'skill:' + window.WikiData.normalizeKey(a.name);
                      var abRoute = '#/abilities/' + encodeURIComponent(a.id);
                      return (
                        '<span class="bc-skill-pill' + (a.learnable ? ' learnable' : '') + '">' +
                          (a.learnable ? '<input type="checkbox" data-check-key="' + api.esc(ck) + '"' + (api.isChecked(ck) ? ' checked' : '') + ' />' : '') +
                          '<a href="' + abRoute + '" data-nav="' + abRoute + '">' + api.esc(a.name) + (a.learnable ? ' ★' : '') + '</a>' +
                        '</span>'
                      );
                    }).join('') || '<span class="bc-muted-sm">No active abilities.</span>') +
                  '</div>' +
                '</article>'
              );
            }).join('') +
          '</div>' +
        '</section>'
      );
    }

    if (section === 'characters') {
      var c = (cats.characters || []).find(function (x) { return x.id === id; });
      if (!c) return '';
      var van = getVanillaCat(ctx, 'characters')[c.id] || null;
      var vanSpellSet = new Set(((van && van.spells) || []).map(function (s) { return window.WikiData.normalizeKey(s.name); }));
      var runSpellSet = new Set((c.spells || []).map(function (s) { return window.WikiData.normalizeKey(s.name); }));

      return (
        renderSeedOnlyBanner(ctx) +
        '<div class="bc-crumb"><a href="#/characters" data-nav="#/characters">← Back to Characters &amp; Classes</a> / <strong>' + api.esc(c.name) + '</strong></div>' +
        '<section class="bc-window">' +
          renderWindowPlaque(api.esc(c.name.toUpperCase()) + ' → ' + api.esc(c.class_name.toUpperCase()), '<span class="bc-badge-steel">Join Lv' + c.join_level + ' · ' + curveLabel(c.curve) + '</span>') +
          '<p class="bc-lead">' + api.esc(c.role || '') + (c.description ? ' — ' + api.esc(c.description) : '') + '</p>' +
          '<div class="bc-table-wrap"><table class="bc-table">' +
            '<thead><tr><th>Stat</th><th>Lv40 Rank</th><th>Join Lv' + c.join_level + '</th><th>Lv40 Estimate</th><th>Lv99 Estimate</th></tr></thead>' +
            '<tbody>' +
              STAT_KEYS.map(function (k) {
                var g = (c.grades_lv40 && c.grades_lv40[k]) || 'C';
                return (
                  '<tr>' +
                    '<td><strong>' + k.toUpperCase() + '</strong></td>' +
                    '<td><span class="bc-rank r-' + api.esc(g) + '">' + api.esc(g) + '</span></td>' +
                    '<td class="bc-mono">' + inlineDiff(c.join[k], van ? van.join[k] : null, ctx.hasBaseline, api) + '</td>' +
                    '<td class="bc-mono">' + inlineDiff(c.lv40[k], van ? van.lv40[k] : null, ctx.hasBaseline, api) + '</td>' +
                    '<td class="bc-mono">' + inlineDiff(c.lv99[k], van ? van.lv99[k] : null, ctx.hasBaseline, api) + '</td>' +
                  '</tr>'
                );
              }).join('') +
            '</tbody>' +
          '</table></div>' +
          '<div class="bc-drawer-card" style="margin-top:12px">' +
            '<div class="bc-drawer-card-hd"><span>ALLOWED WEAPONS &amp; GEAR CATEGORIES</span></div>' +
            '<div class="bc-chip-row">' +
              (c.weapons || []).map(function (w) { return '<span class="bc-badge-cerulean">' + weaponIcon(w) + ' ' + api.esc(w) + '</span>'; }).join('') +
              (c.gear || []).map(function (g) { return '<span class="bc-badge-steel">' + api.esc(g.replace(/_/g, ' ')) + '</span>'; }).join('') +
            '</div>' +
          '</div>' +
          '<div class="bc-dossier-grid" style="margin-top:12px">' +
            (ctx.hasBaseline && van
              ? '<div class="bc-drawer-card">' +
                  '<div class="bc-drawer-card-hd"><span>VANILLA SPELLS (' + (van.spells || []).length + ')</span></div>' +
                  '<ul class="bc-feed-list">' +
                    ((van.spells || []).map(function (sp) {
                      var removed = !runSpellSet.has(window.WikiData.normalizeKey(sp.name));
                      return '<li class="' + (removed ? 'spell-removed' : '') + '"><code>Lv' + sp.level + '</code> ' + api.esc(sp.name) + '</li>';
                    }).join('') || '<li class="bc-muted-sm">None</li>') +
                  '</ul>' +
                '</div>'
              : '') +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>ACTIVE RUN SPELLS — ' + api.esc(c.class_name.toUpperCase()) + ' (' + (c.spells || []).length + ')</span></div>' +
              '<ul class="bc-feed-list">' +
                ((c.spells || []).map(function (sp) {
                  var added = ctx.hasBaseline && van && !vanSpellSet.has(window.WikiData.normalizeKey(sp.name));
                  return '<li class="' + (added ? 'spell-added' : '') + '"><code>Lv' + sp.level + '</code> ' + renderAbilityLink(sp.name, api, ctx.crossLinks) + '</li>';
                }).join('') || '<li class="bc-muted-sm">None</li>') +
              '</ul>' +
            '</div>' +
          '</div>' +
        '</section>'
      );
    }

    if (section === 'masters') {
      var m = (cats.masters || []).find(function (x) { return x.id === id; });
      if (!m) return '';
      var vanM = getVanillaCat(ctx, 'masters')[m.id] || null;
      return (
        renderSeedOnlyBanner(ctx) +
        '<div class="bc-crumb"><a href="#/masters" data-nav="#/masters">← Back to Masters</a> / <strong>' + api.esc(m.name) + '</strong></div>' +
        '<section class="bc-window">' +
          renderWindowPlaque(api.esc(m.name.toUpperCase()) + ' — ' + api.esc(m.kit_name.toUpperCase()), '<span class="bc-badge-steel">' + api.esc(m.location) + '</span>') +
          '<p class="bc-lead">' + api.esc(m.role || '') + (m.description ? ' — ' + api.esc(m.description) : '') + '</p>' +
          '<div class="bc-dossier-grid">' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>PER-LEVEL STAT MODIFIERS</span></div>' +
              '<table class="bc-table bc-table-tight">' +
                '<thead><tr><th>Stat</th>' + (ctx.hasBaseline && vanM ? '<th>Vanilla</th>' : '') + '<th>Active Run</th>' + (ctx.hasBaseline && vanM ? '<th>Delta</th>' : '') + '</tr></thead>' +
                '<tbody>' +
                  MASTER_STAT_KEYS.map(function (k) {
                    var cur = Number(m.stats[k]) || 0;
                    var old = vanM && vanM.stats ? Number(vanM.stats[k]) : 0;
                    var diff = cur - old;
                    return (
                      '<tr class="' + (ctx.hasBaseline && vanM && diff !== 0 ? 'row-diff' : '') + '">' +
                        '<td><strong>' + k.toUpperCase() + '</strong></td>' +
                        (ctx.hasBaseline && vanM ? '<td class="bc-mono bc-muted-sm">' + api.formatSigned(old) + '</td>' : '') +
                        '<td class="bc-mono"><strong class="' + (cur > 0 ? 'up' : (cur < 0 ? 'down' : '')) + '">' + api.formatSigned(cur) + '</strong></td>' +
                        (ctx.hasBaseline && vanM ? '<td class="bc-mono"><span class="bc-delta ' + (diff === 0 ? 'same' : (diff > 0 ? 'up' : 'down')) + '">' + (diff === 0 ? '—' : api.formatSigned(diff)) + '</span></td>' : '') +
                      '</tr>'
                    );
                  }).join('') +
                '</tbody>' +
              '</table>' +
            '</div>' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>APPRENTICESHIP SKILLS (' + (m.skills || []).length + ')</span></div>' +
              '<ul class="bc-feed-list">' +
                ((m.skills || []).map(function (sk, idx) {
                  var ck = 'master:' + m.id + ':' + window.WikiData.normalizeKey(sk.name);
                  var vanSk = vanM && vanM.skills && vanM.skills[idx] ? vanM.skills[idx] : null;
                  return (
                    '<li>' +
                      '<input type="checkbox" data-check-key="' + api.esc(ck) + '"' + (api.isChecked(ck) ? ' checked' : '') + ' />' +
                      '<code>+' + sk.level + 'Lv</code> ' + renderAbilityLink(sk.name, api, ctx.crossLinks) +
                      (ctx.hasBaseline && vanSk && vanSk.name !== sk.name ? '<span class="bc-feed-right">was ' + api.esc(vanSk.name) + '</span>' : '') +
                    '</li>'
                  );
                }).join('') || '<li class="bc-muted-sm">No apprenticeship skills.</li>') +
              '</ul>' +
            '</div>' +
          '</div>' +
        '</section>'
      );
    }

    if (section === 'abilities') {
      var ab = (cats.abilities || []).find(function (x) { return x.id === id; });
      if (!ab) return '';
      var abSrc = window.WikiData.getAbilitySources(ctx.crossLinks, ab.name);
      return (
        renderSeedOnlyBanner(ctx) +
        '<div class="bc-crumb"><a href="#/abilities" data-nav="#/abilities">← Back to Abilities</a> / <strong>' + api.esc(ab.name) + '</strong></div>' +
        '<section class="bc-window">' +
          renderWindowPlaque(api.esc(ab.name.toUpperCase()) + ' <span class="bc-badge-cerulean">' + ab.ap + ' AP</span>', '<span class="bc-badge-lavender">' + api.esc(ab.category) + ' · ' + api.esc(ab.element) + '</span>') +
          '<p class="bc-lead">Target: <strong>' + api.esc(ab.target) + '</strong>' + (ab.power ? ' · Power: <strong>' + api.esc(ab.power) + '</strong>' : '') + ' · <span class="bc-muted-sm">Merged ROM slots: ' + ((ab.merged_slots || []).map(api.esc).join(' + ') || 'Single slot') + '</span></p>' +
          '<div class="bc-three-col">' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>CHARACTERS (' + abSrc.characters.length + ')</span></div>' +
              (abSrc.characters.length
                ? '<ul class="bc-feed-list">' + abSrc.characters.map(function (c) {
                    return '<li><a href="#/characters/' + encodeURIComponent(c.id) + '" data-nav="#/characters/' + encodeURIComponent(c.id) + '" class="bc-link"><strong>' + api.esc(c.name) + '</strong></a> (' + api.esc(c.class_name) + ') <span class="bc-feed-right">Lv' + c.level + '</span></li>';
                  }).join('') + '</ul>'
                : '<span class="bc-muted-sm">None</span>') +
            '</div>' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>MASTERS (' + abSrc.masters.length + ')</span></div>' +
              (abSrc.masters.length
                ? '<ul class="bc-feed-list">' + abSrc.masters.map(function (m) {
                    return '<li><a href="#/masters/' + encodeURIComponent(m.id) + '" data-nav="#/masters/' + encodeURIComponent(m.id) + '" class="bc-link"><strong>' + api.esc(m.name) + '</strong></a> (' + api.esc(m.kit_name) + ') <span class="bc-feed-right">+' + m.level + 'Lv</span></li>';
                  }).join('') + '</ul>'
                : '<span class="bc-muted-sm">None</span>') +
            '</div>' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>MONSTERS VIA EXAMINE (' + abSrc.monsters.length + ')</span></div>' +
              (abSrc.monsters.length
                ? '<ul class="bc-feed-list">' + abSrc.monsters.map(function (m) {
                    return '<li><a href="#/monsters/' + encodeURIComponent(m.id) + '" data-nav="#/monsters/' + encodeURIComponent(m.id) + '" class="bc-link"><strong>' + api.esc(m.name) + '</strong></a> <code class="bc-muted-xs">' + api.esc(m.slot) + '</code> <span class="bc-tier-tag t-' + api.esc((m.tier || 'late').toLowerCase()) + '">' + api.esc(m.tier) + '</span> <span class="bc-feed-right">' + api.esc((m.areas && m.areas[0]) || '') + '</span></li>';
                  }).join('') + '</ul>'
                : '<span class="bc-muted-sm">None</span>') +
            '</div>' +
          '</div>' +
        '</section>'
      );
    }

    if (section === 'equipment') {
      var eq = (cats.equipment || []).find(function (x) { return x.id === id; });
      if (!eq) return '';
      var vanEq = getVanillaCat(ctx, 'equipment')[eq.id] || null;
      var eqSrc = window.WikiData.getItemSources(ctx.crossLinks, eq);
      var eqStats = eq.stats || {};
      var equipStr = (eq.equip || []).join(', ') || 'None';
      var vanEquipStr = vanEq && vanEq.equip ? (vanEq.equip.join(', ') || 'None') : null;
      return (
        renderSeedOnlyBanner(ctx) +
        '<div class="bc-crumb"><a href="#/equipment" data-nav="#/equipment">← Back to Equipment &amp; Items</a> / <strong>' + api.esc(eq.name) + '</strong></div>' +
        '<section class="bc-window">' +
          renderWindowPlaque(kindIcon(eq.kind) + ' ' + api.esc(eq.name.toUpperCase()), '<span class="bc-badge-steel">' + api.esc(eq.kind) + '</span>') +
          '<div class="bc-kpi-row">' +
            '<div class="bc-kpi"><span>ATK (Static)</span><strong>' + api.esc(eqStats.atk || 0) + '</strong></div>' +
            '<div class="bc-kpi"><span>DEF (Static)</span><strong>' + api.esc(eqStats.def || 0) + '</strong></div>' +
            '<div class="bc-kpi"><span>Weight (Static)</span><strong>' + api.esc(eqStats.wt || 0) + '</strong></div>' +
          '</div>' +
          '<div class="bc-dossier-grid">' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>MUTABLE PROPERTIES</span></div>' +
              '<table class="bc-table bc-table-tight">' +
                '<thead><tr><th>Field</th>' + (ctx.hasBaseline && vanEq ? '<th>Vanilla</th>' : '') + '<th>Active Run</th></tr></thead>' +
                '<tbody>' +
                  '<tr class="' + (ctx.hasBaseline && vanEq && vanEquipStr !== equipStr ? 'row-diff' : '') + '"><td><strong>Equipable By</strong></td>' + (ctx.hasBaseline && vanEq ? '<td class="bc-muted-sm">' + api.esc(vanEquipStr) + '</td>' : '') + '<td><strong>' + api.esc(equipStr) + '</strong></td></tr>' +
                  '<tr class="' + (ctx.hasBaseline && vanEq && vanEq.price !== eq.price ? 'row-diff' : '') + '"><td><strong>Price</strong></td>' + (ctx.hasBaseline && vanEq ? '<td class="bc-mono bc-muted-sm">' + (vanEq.price ? vanEq.price + ' Z' : '—') + '</td>' : '') + '<td class="bc-mono"><strong>' + (eq.price ? eq.price + ' Z' : '—') + '</strong></td></tr>' +
                '</tbody>' +
              '</table>' +
            '</div>' +
            '<div class="bc-drawer-card">' +
              '<div class="bc-drawer-card-hd"><span>ACQUISITION SOURCES</span></div>' +
              ((eqSrc.shops.length + eqSrc.manillos.length + eqSrc.chests.length + eqSrc.monsters.length)
                ? '<ul class="bc-feed-list">' +
                    eqSrc.shops.map(function (s) { return '<li><span class="bc-badge-steel sm">Shop</span> <a href="#/shops" data-nav="#/shops" class="bc-link">' + api.esc(s.name) + '</a>' + (s.guardrail ? ' <span class="bc-badge-brass sm">' + api.esc(s.guardrail) + '</span>' : '') + ' <span class="bc-feed-right">' + s.price + 'Z</span></li>'; }).join('') +
                    eqSrc.manillos.map(function (m) { return '<li><span class="bc-badge-lavender sm">Manillo</span> <a href="#/manillos" data-nav="#/manillos" class="bc-link">' + api.esc(m.name) + '</a> <span class="bc-feed-right">' + api.esc(m.cost) + '</span></li>'; }).join('') +
                    eqSrc.chests.map(function (ch) { return '<li><span class="bc-badge-brass sm">Chest ' + api.esc(ch.id) + '</span> <a href="#/chests" data-nav="#/chests" class="bc-link">' + api.esc(ch.area) + '</a></li>'; }).join('') +
                    eqSrc.monsters.map(function (m) { return '<li><span class="bc-badge-scarf sm">' + api.esc(m.method) + '</span> <a href="#/monsters/' + encodeURIComponent(m.id) + '" data-nav="#/monsters/' + encodeURIComponent(m.id) + '" class="bc-link">' + api.esc(m.name) + '</a> <span class="bc-feed-right">' + m.rate + '%</span></li>'; }).join('') +
                  '</ul>'
                : '<span class="bc-muted-sm">No acquisition sources recorded.</span>') +
            '</div>' +
          '</div>' +
        '</section>'
      );
    }

    return '';
  }

  function renderGenesView(ctx) {
    var api = ctx.api;
    var genes = (ctx.run.categories && ctx.run.categories.genes) || [];
    var vanGenes = getVanillaCat(ctx, 'genes');
    var list = genes.filter(function (g) {
      if (!ctx.state.filters.changedOnly || !ctx.hasBaseline) return true;
      var van = vanGenes[g.id];
      var vanName = van ? van.gene : g.vanilla_gene;
      return vanName && g.gene !== vanName;
    });
    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-toolbar">' +
        (ctx.hasBaseline
          ? '<label class="bc-check-toggle"><input type="checkbox" data-filter-changed="1"' + (ctx.state.filters.changedOnly ? ' checked' : '') + ' /> Changed only</label>'
          : '') +
        '<span class="bc-muted-sm">Check boxes sync directly with your per-Run Checklist</span>' +
      '</div>' +
      '<section class="bc-window">' +
        renderWindowPlaque('DRAGON GENES (' + list.length + ' / ' + genes.length + ')', '<span class="bc-badge-lavender">Mode: ' + api.esc((ctx.run.options || {}).genes || 'flat') + '</span>') +
        '<div class="bc-table-wrap"><table class="bc-table">' +
          '<thead><tr><th style="width:32px"></th><th>Tier</th><th>Pedestal Location</th>' + (ctx.hasBaseline ? '<th>Vanilla Baseline</th>' : '') + '<th>Active Run Gene</th><th>Notes</th></tr></thead>' +
          '<tbody>' +
            list.map(function (g) {
              var van = vanGenes[g.id];
              var vanName = van ? van.gene : g.vanilla_gene;
              var changed = ctx.hasBaseline && vanName && g.gene !== vanName;
              var ck = 'gene:' + g.id;
              return (
                '<tr class="' + (changed ? 'row-diff' : '') + (api.isChecked(ck) ? ' is-done' : '') + '">' +
                  '<td><input type="checkbox" data-check-key="' + api.esc(ck) + '"' + (api.isChecked(ck) ? ' checked' : '') + ' /></td>' +
                  '<td><span class="bc-tier-tag t-' + api.esc((g.tier || 'early').toLowerCase()) + '">' + api.esc(g.tier) + '</span></td>' +
                  '<td>' + api.esc(g.location) + '</td>' +
                  (ctx.hasBaseline ? '<td class="bc-muted-sm">' + api.esc(vanName || '—') + '</td>' : '') +
                  '<td><strong>✦ ' + api.esc(g.gene) + '</strong>' + (g.is_cross_tier ? ' <span class="bc-badge-brass sm">Bled from ' + api.esc(g.gene_tier) + '</span>' : '') + '</td>' +
                  '<td class="bc-muted-xs">' + api.esc(g.description || '') + '</td>' +
                '</tr>'
              );
            }).join('') +
          '</tbody>' +
        '</table></div>' +
      '</section>'
    );
  }

  function renderItemLink(name, itemId, api, crossLinks) {
    var resolvedId = itemId;
    if (!resolvedId && crossLinks && crossLinks.equipmentByKey) {
      var found = crossLinks.equipmentByKey[window.WikiData.normalizeKey(name)];
      if (found) resolvedId = found.id;
    }
    if (!resolvedId) return '<strong>' + api.esc(name) + '</strong>';
    var route = '#/equipment/' + encodeURIComponent(resolvedId);
    return '<a href="' + route + '" data-nav="' + route + '" class="bc-link"><strong>' + api.esc(name) + '</strong></a>';
  }

  function abilityRouteFor(name, crossLinks) {
    if (crossLinks && crossLinks.abilityByKey) {
      var found = crossLinks.abilityByKey[window.WikiData.normalizeKey(name)];
      if (found) return '#/abilities/' + encodeURIComponent(found.id);
    }
    return '#/abilities';
  }

  function renderAbilityLink(name, api, crossLinks) {
    var route = abilityRouteFor(name, crossLinks);
    return '<a href="' + route + '" data-nav="' + route + '" class="bc-link"><strong>' + api.esc(name) + '</strong></a>';
  }

  function renderShopsView(ctx) {
    var api = ctx.api;
    var shops = (ctx.run.categories && ctx.run.categories.shops) || [];
    var vanShops = getVanillaCat(ctx, 'shops');
    var vanEquip = getVanillaCat(ctx, 'equipment');
    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-bento">' +
        shops.map(function (s) {
          var vanS = vanShops[s.id];
          var vanStockNames = new Set(((vanS && vanS.stock) || []).map(function (it) { return it.item; }));
          return (
            '<section class="bc-window span-6">' +
              renderWindowPlaque(api.esc(s.id) + ' · ' + api.esc(s.name.toUpperCase()), '<span class="bc-tier-tag t-' + api.esc((s.tier || 'late').toLowerCase()) + '">' + api.esc(s.tier) + '</span>') +
              '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
                '<thead><tr><th>Item</th><th>Price</th><th>Notes</th></tr></thead>' +
                '<tbody>' +
                  ((s.stock || []).map(function (st) {
                    var vanItem = st.item_id ? vanEquip[st.item_id] : null;
                    var priceHtml = ctx.hasBaseline && vanItem && vanItem.price != null && vanItem.price !== st.price
                      ? inlineDiff(st.price, vanItem.price, true, api) + ' Z'
                      : '<span class="bc-val">' + api.esc(st.price) + ' Z</span>';
                    var isNew = ctx.hasBaseline && vanS && !vanStockNames.has(st.item);
                    var notes = [];
                    if (st.guardrail) notes.push('<span class="bc-badge-brass sm">' + api.esc(st.guardrail) + '</span>');
                    if (isNew) notes.push('<span class="bc-badge-lavender sm">Randomized</span>');
                    return (
                      '<tr class="' + (st.guardrail ? 'row-diff' : '') + '">' +
                        '<td>' + renderItemLink(st.item, st.item_id, api) + '</td>' +
                        '<td class="bc-mono">' + priceHtml + '</td>' +
                        '<td>' + (notes.join(' ') || '<span class="bc-muted-sm">—</span>') + '</td>' +
                      '</tr>'
                    );
                  }).join('') || '<tr><td colspan="3" class="bc-muted-sm">No items stocked.</td></tr>') +
                '</tbody>' +
              '</table></div>' +
            '</section>'
          );
        }).join('') +
      '</div>'
    );
  }

  function renderManillosView(ctx) {
    var api = ctx.api;
    var traders = (ctx.run.categories && ctx.run.categories.manillos) || [];
    var vanManillos = getVanillaCat(ctx, 'manillos');
    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-bento">' +
        traders.map(function (tr) {
          var vanTr = vanManillos[tr.id];
          return (
            '<section class="bc-window span-6">' +
              renderWindowPlaque(api.esc(tr.id) + ' · ' + api.esc(tr.name.toUpperCase()), '<span class="bc-muted-sm">' + (tr.trades || []).length + ' exchanges</span>') +
              '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
                '<thead><tr><th>Reward</th><th>Fish Cost</th>' + (ctx.hasBaseline && vanTr ? '<th>Vanilla</th>' : '') + '</tr></thead>' +
                '<tbody>' +
                  (tr.trades || []).map(function (t, idx) {
                    var vanT = vanTr && vanTr.trades ? vanTr.trades[idx] : null;
                    var changed = ctx.hasBaseline && vanT && (vanT.item !== t.item || vanT.cost !== t.cost);
                    return (
                      '<tr class="' + (changed ? 'row-diff' : '') + '">' +
                        '<td>' + renderItemLink(t.item, t.item_id, api) + '</td>' +
                        '<td class="bc-muted-sm">' + api.esc(t.cost) + '</td>' +
                        (ctx.hasBaseline && vanTr ? '<td class="bc-muted-xs">' + (vanT ? api.esc(vanT.item) : '—') + '</td>' : '') +
                      '</tr>'
                    );
                  }).join('') +
                '</tbody>' +
              '</table></div>' +
            '</section>'
          );
        }).join('') +
      '</div>'
    );
  }

  function renderChestsView(ctx) {
    var api = ctx.api;
    var chests = (ctx.run.categories && ctx.run.categories.chests) || [];
    var vanChests = getVanillaCat(ctx, 'chests');
    var q = String(ctx.state.filters.listQuery || '').trim().toLowerCase();

    var list = chests.filter(function (c) {
      if (ctx.state.filters.changedOnly && ctx.hasBaseline) {
        var van = vanChests[c.id];
        if (!van || van.item === c.item) return false;
      }
      if (q) {
        var hay = (c.area + ' ' + c.item + ' ' + c.id).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });

    var areaOrder = [];
    var byArea = {};
    list.forEach(function (c) {
      var key = c.area || 'Unknown Area';
      if (!byArea[key]) {
        byArea[key] = { area: key, tier: c.tier || 'Mid', items: [] };
        areaOrder.push(key);
      }
      byArea[key].items.push(c);
    });

    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-toolbar">' +
        '<input type="search" class="bc-filter-input" data-list-query="1" placeholder="Filter chests by area or item…" value="' + api.esc(ctx.state.filters.listQuery || '') + '" />' +
        (ctx.hasBaseline
          ? '<label class="bc-check-toggle"><input type="checkbox" data-filter-changed="1"' + (ctx.state.filters.changedOnly ? ' checked' : '') + ' /> Changed only</label>'
          : '') +
        '<span class="bc-muted-sm">Showing ' + list.length + ' chests across ' + areaOrder.length + ' areas</span>' +
      '</div>' +
      '<section class="bc-window">' +
        renderWindowPlaque('TREASURE CHESTS BY AREA (' + list.length + ')') +
        '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
          '<thead><tr><th style="width:32px"></th><th>ID</th><th>Tier</th>' + (ctx.hasBaseline ? '<th>Vanilla</th>' : '') + '<th>Active Run Contents</th></tr></thead>' +
          '<tbody>' +
            (areaOrder.length
              ? areaOrder.map(function (areaKey) {
                  var grp = byArea[areaKey];
                  var colSpan = ctx.hasBaseline ? 5 : 4;
                  var hdr = (
                    '<tr><td colspan="' + colSpan + '" style="background:rgba(143,139,112,0.14);font-weight:800;padding:6px 8px">' +
                      '<span class="bc-tier-tag t-' + api.esc(grp.tier.toLowerCase()) + '" style="margin-right:8px">' + api.esc(grp.tier) + '</span>' +
                      api.esc(grp.area) + ' <span class="bc-muted-xs">(' + grp.items.length + ')</span>' +
                    '</td></tr>'
                  );
                  var rows = grp.items.map(function (c) {
                    var van = vanChests[c.id];
                    var changed = ctx.hasBaseline && van && van.item !== c.item;
                    var ck = 'chest:' + c.id;
                    return (
                      '<tr class="' + (changed ? 'row-diff' : '') + (api.isChecked(ck) ? ' is-done' : '') + '">' +
                        '<td><input type="checkbox" data-check-key="' + api.esc(ck) + '"' + (api.isChecked(ck) ? ' checked' : '') + ' /></td>' +
                        '<td class="bc-mono">' + api.esc(c.id) + '</td>' +
                        '<td><span class="bc-tier-tag t-' + api.esc((c.tier || 'mid').toLowerCase()) + '">' + api.esc(c.tier) + '</span></td>' +
                        (ctx.hasBaseline ? '<td class="bc-muted-sm">' + api.esc(van ? van.item : '—') + '</td>' : '') +
                        '<td>' + renderItemLink(c.item, c.item_id, api, ctx.crossLinks) + '</td>' +
                      '</tr>'
                    );
                  }).join('');
                  return hdr + rows;
                }).join('')
              : '<tr><td colspan="' + (ctx.hasBaseline ? 5 : 4) + '" class="bc-muted-sm">No chests match the active filter.</td></tr>') +
          '</tbody>' +
        '</table></div>' +
      '</section>'
    );
  }

  function renderGuardrailsView(ctx) {
    var api = ctx.api;
    var g = (ctx.run.categories && ctx.run.categories.guardrails) || { enabled: {}, crash_count: 0, clamp_count: 0, weapon_count: 0, crash_items: [], clamp_items: [], weapon_items: [] };
    var en = g.enabled || {};
    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-bento">' +
        '<section class="bc-window span-12">' +
          renderWindowPlaque('GUARDRAILS TELEMETRY', '<span class="bc-muted-sm">Crash: ' + (en.crash ? 'ON' : 'OFF') + ' · Tiers: ' + (en.tiers ? 'ON' : 'OFF') + ' · Weapons: ' + (en.weapons ? 'ON' : 'OFF') + '</span>') +
          '<div class="bc-kpi-row">' +
            '<div class="bc-kpi"><span>Crash Blacklist Fixes</span><strong>' + api.esc(g.crash_count || 0) + '</strong></div>' +
            '<div class="bc-kpi brass"><span>Encounter Tier Clamps</span><strong>' + api.esc(g.clamp_count || 0) + '</strong></div>' +
            '<div class="bc-kpi cerulean"><span>Weapon Shop Adjustments</span><strong>' + api.esc(g.weapon_count || 0) + '</strong></div>' +
          '</div>' +
        '</section>' +

        '<section class="bc-window span-6">' +
          renderWindowPlaque('WEAPON ACCESSIBILITY (' + (g.weapon_items || []).length + ')') +
          '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
            '<thead><tr><th>Tier</th><th>Shop / Subject</th><th>Adjustment</th></tr></thead>' +
            '<tbody>' +
              ((g.weapon_items || []).map(function (w) {
                return (
                  '<tr>' +
                    '<td><span class="bc-tier-tag t-' + api.esc((w.tier || 'early').toLowerCase()) + '">' + api.esc(w.tier || 'Early') + '</span></td>' +
                    '<td><strong>' + api.esc(w.shop_name || w.subject) + '</strong></td>' +
                    '<td class="bc-muted-sm">' + api.esc(w.detail) + '</td>' +
                  '</tr>'
                );
              }).join('') || '<tr><td colspan="3" class="bc-muted-sm">No weapon accessibility adjustments needed.</td></tr>') +
            '</tbody>' +
          '</table></div>' +
        '</section>' +

        '<section class="bc-window span-6">' +
          renderWindowPlaque('CRASH BLACKLIST (' + (g.crash_items || []).length + ')') +
          '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
            '<thead><tr><th>Monster</th><th>Sanitized Skill</th></tr></thead>' +
            '<tbody>' +
              ((g.crash_items || []).map(function (c) {
                return '<tr><td><strong>' + api.esc(c.subject) + '</strong></td><td class="bc-muted-sm">' + api.esc(c.detail) + '</td></tr>';
              }).join('') || '<tr><td colspan="2" class="bc-muted-sm">Zero unsafe enemy skills needed replacement.</td></tr>') +
            '</tbody>' +
          '</table></div>' +
        '</section>' +

        '<section class="bc-window span-12">' +
          renderWindowPlaque('ENCOUNTER TIER CLAMPS &amp; PROTECTED ENCOUNTERS (' + (g.clamp_items || []).length + ')') +
          '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
            '<thead><tr><th>Monster</th><th>Tier / Rule</th><th>Adjustment</th></tr></thead>' +
            '<tbody>' +
              ((g.clamp_items || []).map(function (h) {
                return (
                  '<tr>' +
                    '<td><strong>' + api.esc(h.subject) + '</strong></td>' +
                    '<td><span class="bc-badge-lavender sm">' + api.esc(h.tag || 'Clamped') + '</span></td>' +
                    '<td class="bc-muted-sm">' + api.esc(h.detail) + '</td>' +
                  '</tr>'
                );
              }).join('') || '<tr><td colspan="3" class="bc-muted-sm">No encounter tier clamps recorded.</td></tr>') +
            '</tbody>' +
          '</table></div>' +
        '</section>' +
      '</div>'
    );
  }

  function renderAbilitiesView(ctx) {
    var api = ctx.api;
    var abilities = (ctx.run.categories && ctx.run.categories.abilities) || [];
    var q = String(ctx.state.filters.listQuery || '').trim().toLowerCase();
    var vanAbilitySigs = ctx.hasBaseline ? window.WikiData.buildVanillaAbilitySignatures(ctx.baseline) : null;

    var list = abilities.filter(function (a) {
      if (ctx.state.filters.changedOnly && ctx.hasBaseline) {
        var src = window.WikiData.getAbilitySources(ctx.crossLinks, a.name);
        var curSig = window.WikiData.abilitySourceSignature(src);
        var vanSig = (vanAbilitySigs && vanAbilitySigs[window.WikiData.normalizeKey(a.name)])
          ? vanAbilitySigs[window.WikiData.normalizeKey(a.name)].join('|')
          : '';
        if (!a.changed && curSig === vanSig) return false;
      }
      if (q) {
        var hay = (a.name + ' ' + a.category + ' ' + a.element + ' ' + (a.merged_slots || []).join(' ')).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });

    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-toolbar">' +
        '<input type="search" class="bc-filter-input" data-list-query="1" placeholder="Filter abilities by name, element, slot…" value="' + api.esc(ctx.state.filters.listQuery || '') + '" />' +
        (ctx.hasBaseline
          ? '<label class="bc-check-toggle"><input type="checkbox" data-filter-changed="1"' + (ctx.state.filters.changedOnly ? ' checked' : '') + ' /> Changed only</label>'
          : '') +
        '<span class="bc-muted-sm">Click any ability to trace every Character, Master, and Monster teaching it</span>' +
      '</div>' +
      '<section class="bc-window">' +
        renderWindowPlaque('CANONICAL ABILITIES (' + list.length + ')', '<span class="bc-muted-sm">Duplicate examine &amp; level-up ROM slots merged</span>') +
        '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
          '<thead><tr><th>Ability</th><th>AP</th><th>Element</th><th>Category</th><th>Merged ROM Slots</th><th>Sources in Active Run</th></tr></thead>' +
          '<tbody>' +
            (list.map(function (a) {
              var src = window.WikiData.getAbilitySources(ctx.crossLinks, a.name);
              var selected = ctx.state.filters.drawerItem === ('abilities:' + a.id);
              return (
                '<tr class="bc-clickable' + (selected ? ' selected' : '') + '" data-open-drawer="abilities:' + api.esc(a.id) + '">' +
                  '<td><strong>' + api.esc(a.name) + '</strong>' + (a.examinable ? ' <span class="bc-skill-pill learnable" style="padding:0 5px">★</span>' : '') + '</td>' +
                  '<td class="bc-mono">' + api.esc(a.ap) + '</td>' +
                  '<td>' + api.esc(a.element) + '</td>' +
                  '<td><span class="bc-badge-lavender sm">' + api.esc(a.category) + '</span></td>' +
                  '<td class="bc-mono bc-muted-xs">' + (a.merged_slots || []).map(api.esc).join(' + ') + '</td>' +
                  '<td class="bc-cerulean"><strong>' + src.characters.length + ' Char · ' + src.masters.length + ' Master · ' + src.monsters.length + ' Monster</strong></td>' +
                '</tr>'
              );
            }).join('') || '<tr><td colspan="6" class="bc-muted-sm">No abilities match the active filter.</td></tr>') +
          '</tbody>' +
        '</table></div>' +
      '</section>'
    );
  }

  function renderEquipmentView(ctx) {
    var api = ctx.api;
    var items = (ctx.run.categories && ctx.run.categories.equipment) || [];
    var vanEquip = getVanillaCat(ctx, 'equipment');
    var q = String(ctx.state.filters.listQuery || '').trim().toLowerCase();
    var kindFilter = ctx.state.filters.equipKind || 'All';
    var kindTabs = ['All', 'Weapon', 'Armor', 'Accessory', 'Consumable'];

    var list = items.filter(function (e) {
      if (ctx.state.filters.changedOnly && ctx.hasBaseline && !e.changed) return false;
      if (kindFilter !== 'All') {
        var kLow = String(e.kind || '').toLowerCase();
        if (kindFilter === 'Armor') {
          if (kLow.indexOf('armor') < 0 && kLow.indexOf('shield') < 0 && kLow.indexOf('helmet') < 0) return false;
        } else if (kLow.indexOf(kindFilter.toLowerCase()) < 0) {
          return false;
        }
      }
      if (q) {
        var hay = (e.name + ' ' + e.kind + ' ' + (e.equip || []).join(' ')).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });

    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-toolbar">' +
        '<div class="bc-pills">' +
          kindTabs.map(function (kt) {
            return '<button type="button" class="bc-pill' + (kindFilter === kt ? ' active' : '') + '" data-equip-kind="' + kt + '">' + kt + '</button>';
          }).join('') +
        '</div>' +
        '<input type="search" class="bc-filter-input" data-list-query="1" placeholder="Filter gear, items, character…" value="' + api.esc(ctx.state.filters.listQuery || '') + '" />' +
        (ctx.hasBaseline
          ? '<label class="bc-check-toggle"><input type="checkbox" data-filter-changed="1"' + (ctx.state.filters.changedOnly ? ' checked' : '') + ' /> Changed equip / price only</label>'
          : '') +
      '</div>' +
      '<section class="bc-window">' +
        renderWindowPlaque('EQUIPMENT &amp; ITEMS (' + list.length + ')', '<span class="bc-muted-sm">Static combat stats clean · Mutable fields diffed</span>') +
        '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
          '<thead><tr><th>Item</th><th>Kind</th><th>ATK / DEF / WT</th><th>Price</th><th>Equipable By</th><th>Sources</th></tr></thead>' +
          '<tbody>' +
            (list.map(function (e) {
              var van = vanEquip[e.id] || null;
              var src = window.WikiData.getItemSources(ctx.crossLinks, e);
              var totalSrc = src.shops.length + src.manillos.length + src.chests.length + src.monsters.length;
              var st = e.stats || {};
              var eqStr = (e.equip || []).join(', ');
              var vanEqStr = van && van.equip ? van.equip.join(', ') : null;
              var eqChanged = ctx.hasBaseline && van && vanEqStr !== eqStr;
              var priceHtml = ctx.hasBaseline && van && van.price != null && van.price !== e.price
                ? inlineDiff(e.price, van.price, true, api) + ' Z'
                : (e.price ? e.price + ' Z' : '—');
              var selected = ctx.state.filters.drawerItem === ('equipment:' + e.id);
              return (
                '<tr class="bc-clickable' + (selected ? ' selected' : '') + (ctx.hasBaseline && e.changed ? ' row-diff' : '') + '" data-open-drawer="equipment:' + api.esc(e.id) + '">' +
                  '<td><strong>' + kindIcon(e.kind) + ' ' + api.esc(e.name) + '</strong></td>' +
                  '<td class="bc-muted-sm">' + api.esc(e.kind) + '</td>' +
                  '<td class="bc-mono">' + (st.atk || '—') + ' / ' + (st.def || '—') + ' / ' + (st.wt || '—') + '</td>' +
                  '<td class="bc-mono">' + priceHtml + '</td>' +
                  '<td>' + (eqStr ? api.esc(eqStr) : '<span class="bc-muted-xs">—</span>') + (eqChanged ? ' <span class="bc-was-tag">was ' + api.esc(vanEqStr || 'None') + '</span>' : '') + '</td>' +
                  '<td class="bc-cerulean"><strong>' + totalSrc + ' source' + (totalSrc === 1 ? '' : 's') + '</strong></td>' +
                '</tr>'
              );
            }).join('') || '<tr><td colspan="6" class="bc-muted-sm">No equipment or items match the active filter.</td></tr>') +
          '</tbody>' +
        '</table></div>' +
      '</section>'
    );
  }

  function renderCommandPalette(ctx) {
    if (!ctx.state.filters.paletteOpen || !ctx.run) return '';
    var api = ctx.api;
    var q = ctx.state.filters.searchQuery || '';
    var hits = window.WikiData.globalSearch(ctx.run, q);
    return (
      '<div class="bc-palette-backdrop" data-close-palette="1">' +
        '<div class="bc-palette" role="dialog" aria-modal="true" aria-label="Global Command Palette">' +
          '<div class="bc-palette-hd">' +
            '<span class="bc-filigree" aria-hidden="true">❖</span>' +
            '<input type="search" id="bc-palette-input" class="bc-palette-input" placeholder="Search Masters, Party, Genes, Monsters, Abilities, Gear, Shops, Manillos, Chests…" value="' + api.esc(q) + '" autocomplete="off" />' +
            '<kbd>ESC</kbd>' +
          '</div>' +
          '<div id="bc-palette-list" class="bc-palette-list">' +
            renderPaletteHitsHtml(hits, api) +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function renderPaletteHitsHtml(hits, api) {
    if (!hits.length) {
      return '<div class="bc-palette-empty">No matching entries across all 10 compendium categories.</div>';
    }
    return hits.map(function (h, idx) {
      return (
        '<a href="' + api.esc(h.route) + '" class="bc-palette-hit' + (idx === 0 ? ' is-active' : '') + '" data-palette-hit="' + api.esc(h.route) + '" data-palette-drawer="' + api.esc(h.drawerTarget || '') + '">' +
          '<span class="bc-badge-lavender sm">' + api.esc(h.cat) + '</span>' +
          '<strong>' + api.esc(h.title) + '</strong>' +
          '<span class="bc-muted-sm">' + api.esc(h.sub) + '</span>' +
        '</a>'
      );
    }).join('');
  }

  function renderChecklistView(ctx) {
    var api = ctx.api;
    var cs = ctx.checklistStats;
    var activePane = ctx.state.filters.checklistPane || 'all';
    var q = String(ctx.state.filters.listQuery || '').trim().toLowerCase();
    var sections = activePane === 'all'
      ? cs.sections
      : cs.sections.filter(function (s) { return s.id === activePane; });

    return (
      renderSeedOnlyBanner(ctx) +
      '<div class="bc-check-split">' +
        '<aside class="bc-window bc-check-rail">' +
          renderWindowPlaque('PROGRESS LEDGER') +
          '<div class="bc-total-box">' +
            '<div class="bc-total-pct">' + cs.pct + '%</div>' +
            '<div class="bc-muted-sm">' + cs.done + ' / ' + cs.total + ' items completed</div>' +
            '<div class="bc-gauge"><div style="width:' + cs.pct + '%"></div></div>' +
          '</div>' +
          '<button type="button" class="bc-pane-btn' + (activePane === 'all' ? ' active' : '') + '" data-check-pane="all">' +
            '<span>All Categories</span><strong class="bc-mono">' + cs.done + '/' + cs.total + '</strong>' +
          '</button>' +
          cs.sections.map(function (s) {
            return (
              '<button type="button" class="bc-pane-btn' + (activePane === s.id ? ' active' : '') + '" data-check-pane="' + api.esc(s.id) + '">' +
                '<div>' +
                  '<span>' + api.esc(s.label) + '</span>' +
                  '<div class="bc-gauge sm"><div style="width:' + s.pct + '%"></div></div>' +
                '</div>' +
                '<strong class="bc-mono">' + s.done + '/' + s.total + '</strong>' +
              '</button>'
            );
          }).join('') +
          '<div class="bc-rail-tools">' +
            '<input type="search" class="bc-filter-input" style="min-width:0;width:100%" data-list-query="1" placeholder="Filter checklist items…" value="' + api.esc(ctx.state.filters.listQuery || '') + '" />' +
            '<label class="bc-check-toggle"><input type="checkbox" data-filter-hide-done="1"' + (ctx.state.filters.hideCompleted ? ' checked' : '') + ' /> Hide completed</label>' +
            '<button type="button" class="bc-btn-cerulean full" data-open-backup="1">Export / Import JSON Backup</button>' +
          '</div>' +
        '</aside>' +

        '<div class="bc-check-main">' +
          sections.map(function (sec) {
            var collapsed = !!(ctx.state.filters.collapsedChecklist && ctx.state.filters.collapsedChecklist[sec.id]);
            var items = sec.items.filter(function (it) {
              if (ctx.state.filters.hideCompleted && api.isChecked(it.key)) return false;
              if (q) {
                var hay = (it.label + ' ' + it.group + ' ' + it.sub).toLowerCase();
                if (hay.indexOf(q) < 0) return false;
              }
              return true;
            });
            return (
              '<section class="bc-window">' +
                '<div class="bc-win-hd">' +
                  '<button type="button" class="bc-acc-title" data-collapse-sec="' + api.esc(sec.id) + '">' +
                    '<span>' + (collapsed ? '▸' : '▾') + '</span>' +
                    '<h2>' + api.esc(sec.label.toUpperCase()) + '</h2>' +
                    '<span class="bc-badge-steel">' + sec.done + '/' + sec.total + ' (' + sec.pct + '%)</span>' +
                  '</button>' +
                  '<span class="bc-muted-sm">' + api.esc(sec.desc) + '</span>' +
                '</div>' +
                (!collapsed
                  ? '<div class="bc-table-wrap"><table class="bc-table bc-table-tight">' +
                      '<thead><tr><th style="width:32px"></th><th>Item / Skill</th><th>Group / Area</th><th>Location / Sources</th><th style="width:74px"></th></tr></thead>' +
                      '<tbody>' +
                        (items.length
                          ? items.map(function (it) {
                              var ck = api.isChecked(it.key);
                              return (
                                '<tr class="' + (ck ? 'is-done' : '') + '">' +
                                  '<td><input type="checkbox" data-check-key="' + api.esc(it.key) + '"' + (ck ? ' checked' : '') + ' /></td>' +
                                  '<td><strong>' + api.esc(it.label) + '</strong></td>' +
                                  '<td><span class="bc-badge-lavender sm">' + api.esc(it.group) + '</span></td>' +
                                  '<td class="bc-muted-sm">' + api.esc(it.sub) + '</td>' +
                                  '<td><a href="' + api.esc(it.route) + '" data-nav="' + api.esc(it.route) + '" class="bc-link">Inspect →</a></td>' +
                                '</tr>'
                              );
                            }).join('')
                          : '<tr><td colspan="5" class="bc-muted-sm">' + (sec.total === 0 ? 'No items in this category.' : 'All matching items are completed!') + '</td></tr>') +
                      '</tbody>' +
                    '</table></div>'
                  : '') +
              '</section>'
            );
          }).join('') +
        '</div>' +
      '</div>'
    );
  }

  function renderSection(ctx) {
    if (!ctx.run) {
      if (ctx.state.loadingRun) {
        return (
          '<section class="bc-window bc-empty">' +
            '<div class="bc-win-plaque"><span class="bc-filigree">✦</span><h2>LOADING RUN</h2><span class="bc-filigree">✦</span></div>' +
            '<div class="bc-placeholder">Loading Seed Manifest…</div>' +
          '</section>'
        );
      }
      return renderEmptyState(ctx);
    }

    var sec = ctx.state.route.section;
    var id = ctx.state.route.id;

    if (id && ctx.state.filters.fullPageMode) {
      var dossier = renderFullPageDetail(ctx, sec, id);
      if (dossier) return dossier;
    }

    if (sec === 'overview') return renderOverview(ctx);
    if (sec === 'checklist') return renderChecklistView(ctx);
    if (sec === 'characters') return renderCharactersView(ctx);
    if (sec === 'masters') return renderMastersView(ctx);
    if (sec === 'genes') return renderGenesView(ctx);
    if (sec === 'monsters') return renderMonstersView(ctx);
    if (sec === 'abilities') return renderAbilitiesView(ctx);
    if (sec === 'equipment') return renderEquipmentView(ctx);
    if (sec === 'shops') return renderShopsView(ctx);
    if (sec === 'manillos') return renderManillosView(ctx);
    if (sec === 'chests') return renderChestsView(ctx);
    if (sec === 'guardrails') return renderGuardrailsView(ctx);

    return renderOverview(ctx);
  }

  function render(ctx) {
    var api = ctx.api;
    var sec = ctx.state.route.section;
    var cs = ctx.checklistStats;

    if (ctx.run && ctx.state.route.id && !ctx.state.filters.fullPageMode &&
        ['monsters', 'characters', 'masters', 'abilities', 'equipment'].indexOf(sec) >= 0 &&
        !ctx.state.filters.drawerItem) {
      ctx.state.filters.drawerItem = sec + ':' + ctx.state.route.id;
    }

    var drawerHtml = (!ctx.state.filters.fullPageMode && ctx.run) ? renderInspectorDrawer(ctx) : '';

    return (
      '<div class="bc-shell' + (ctx.state.isDragging ? ' is-dragging' : '') + (drawerHtml ? ' has-drawer' : '') + '">' +
        '<header class="bc-header">' +
          '<div class="bc-head-top">' +
            '<div class="bc-brand-group">' +
              '<a href="#/overview" data-nav="#/overview" class="bc-brand">' +
                '<span class="bc-brand-gem" aria-hidden="true">◆</span>' +
                '<div>' +
                  '<div class="bc-brand-title">ACCURSED BROOD</div>' +
                  '<div class="bc-brand-sub">Companion Wiki</div>' +
                '</div>' +
              '</a>' +
              '<select class="bc-run-select" data-run-select="1" aria-label="Select Run">' + renderRunSelect(ctx) + '</select>' +
              '<button type="button" class="bc-btn-sm" data-pick-json="1" title="Load external Seed Manifest JSON">Load JSON</button>' +
            '</div>' +

            '<button type="button" class="bc-cmd-trigger" data-open-palette="1" title="Search across all 10 categories (Ctrl+K)">' +
              '<span>Search masters, monsters, skills, gear, genes…</span>' +
              '<kbd>Ctrl K</kbd>' +
            '</button>' +

            '<div class="bc-head-right">' +
              '<div class="bc-theme-switch" role="group" aria-label="Color Theme">' +
                '<button type="button" class="bc-theme-btn' + (ctx.state.theme !== 'dark' ? ' active' : '') + '" data-set-theme="light" title="Ryu (Light Theme)">☀ Ryu</button>' +
                '<button type="button" class="bc-theme-btn' + (ctx.state.theme === 'dark' ? ' active' : '') + '" data-set-theme="dark" title="Teepo / Dragon Lord (Dark Theme)">☾ Teepo</button>' +
              '</div>' +
              '<a href="#/checklist" data-nav="#/checklist" class="bc-check-pill' + (sec === 'checklist' ? ' active' : '') + '">' +
                '<div class="bc-check-pill-top">' +
                  '<span>Checklist</span>' +
                  '<strong class="bc-mono">' + (ctx.run ? cs.done + '/' + cs.total : '—') + '</strong>' +
                '</div>' +
                (ctx.run ? '<div class="bc-pill-gauge"><div style="width:' + cs.pct + '%"></div></div>' : '') +
              '</a>' +
            '</div>' +
          '</div>' +

          '<nav class="bc-cmd-tabs" aria-label="Compendium Categories">' +
            '<a href="#/overview" data-nav="#/overview" class="bc-cmd-tab' + (sec === 'overview' ? ' active' : '') + '">Overview</a>' +
            ctx.categories.map(function (c) {
              return '<a href="#/' + c.id + '" data-nav="#/' + c.id + '" class="bc-cmd-tab' + (sec === c.id ? ' active' : '') + '">' + api.esc(c.short) + '</a>';
            }).join('') +
          '</nav>' +
        '</header>' +

        '<div class="bc-workspace">' +
          '<main class="bc-main">' + renderSection(ctx) + '</main>' +
          drawerHtml +
        '</div>' +
        renderCommandPalette(ctx) +
      '</div>'
    );
  }

  function bind(root, ctx) {
    root.querySelectorAll('[data-open-drawer]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (e.target && (e.target.closest('a') || e.target.closest('input') || e.target.closest('button'))) {
          return;
        }
        ctx.state.filters.fullPageMode = false;
        ctx.api.setFilter('drawerItem', el.getAttribute('data-open-drawer'));
      });
    });

    root.querySelectorAll('[data-close-drawer]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.state.filters.drawerItem = null;
        if (ctx.state.route.id) {
          ctx.api.navigate('#/' + ctx.state.route.section);
        } else {
          ctx.api.setFilter('drawerItem', null);
        }
      });
    });

    root.querySelectorAll('[data-expand-full]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.navigate(el.getAttribute('data-expand-full'));
      });
    });

    root.querySelectorAll('[data-char-tab]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.setFilter('charTab', el.getAttribute('data-char-tab'));
      });
    });

    root.querySelectorAll('[data-filter-tier]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.setFilter('monsterTier', el.getAttribute('data-filter-tier'));
      });
    });

    root.querySelectorAll('[data-equip-kind]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.setFilter('equipKind', el.getAttribute('data-equip-kind'));
      });
    });

    root.querySelectorAll('[data-open-palette]').forEach(function (el) {
      el.addEventListener('click', function () {
        if (!ctx.run) return;
        ctx.api.setFilter('paletteOpen', true);
      });
    });

    root.querySelectorAll('[data-close-palette]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (e.target === el) {
          ctx.api.setFilter('paletteOpen', false);
        }
      });
    });

    var palInput = root.querySelector('#bc-palette-input');
    var palList = root.querySelector('#bc-palette-list');
    if (palInput && palList && ctx.run) {
      palInput.focus();
      try { palInput.setSelectionRange(palInput.value.length, palInput.value.length); } catch (_) {}

      var bindPaletteHits = function () {
        palList.querySelectorAll('[data-palette-hit]').forEach(function (a) {
          a.addEventListener('click', function (e) {
            e.preventDefault();
            var route = a.getAttribute('data-palette-hit');
            var drawer = a.getAttribute('data-palette-drawer');
            ctx.state.filters.paletteOpen = false;
            ctx.state.filters.fullPageMode = false;
            ctx.state.filters.drawerItem = drawer || null;
            ctx.api.navigate(route);
          });
        });
      };
      bindPaletteHits();

      palInput.addEventListener('input', function () {
        ctx.state.filters.searchQuery = palInput.value;
        var hits = window.WikiData.globalSearch(ctx.run, palInput.value);
        palList.innerHTML = renderPaletteHitsHtml(hits, ctx.api);
        bindPaletteHits();
      });

      palInput.addEventListener('keydown', function (e) {
        var links = Array.prototype.slice.call(palList.querySelectorAll('[data-palette-hit]'));
        if (!links.length) return;
        var activeIdx = links.findIndex(function (l) { return l.classList.contains('is-active'); });
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          var nextIdx = (activeIdx + 1) % links.length;
          links.forEach(function (l, i) { l.classList.toggle('is-active', i === nextIdx); });
          links[nextIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          var prevIdx = (activeIdx - 1 + links.length) % links.length;
          links.forEach(function (l, i) { l.classList.toggle('is-active', i === prevIdx); });
          links[prevIdx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter') {
          e.preventDefault();
          var pick = links[activeIdx >= 0 ? activeIdx : 0];
          if (pick) pick.click();
        }
      });
    }

    root.querySelectorAll('[data-check-key]').forEach(function (el) {
      el.addEventListener('change', function () {
        ctx.api.toggleCheck(el.getAttribute('data-check-key'));
      });
    });

    root.querySelectorAll('[data-filter-changed]').forEach(function (el) {
      el.addEventListener('change', function () {
        ctx.api.setFilter('changedOnly', !!el.checked);
      });
    });

    root.querySelectorAll('[data-toggle-guardrails]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.setFilter('expandedGuardrails', !ctx.state.filters.expandedGuardrails);
      });
    });

    root.querySelectorAll('[data-check-pane]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.setFilter('checklistPane', el.getAttribute('data-check-pane'));
      });
    });

    root.querySelectorAll('[data-collapse-sec]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.toggleCollapseChecklist(el.getAttribute('data-collapse-sec'));
      });
    });

    root.querySelectorAll('[data-filter-hide-done]').forEach(function (el) {
      el.addEventListener('change', function () {
        ctx.api.setFilter('hideCompleted', !!el.checked);
      });
    });

    root.querySelectorAll('[data-open-backup]').forEach(function (el) {
      el.addEventListener('click', function () {
        ctx.api.openBackupModal();
      });
    });

    var listQueryEl = root.querySelector('[data-list-query]');
    if (listQueryEl) {
      listQueryEl.addEventListener('input', function () {
        var pos = listQueryEl.selectionStart;
        ctx.api.setFilter('listQuery', listQueryEl.value);
        var next = document.querySelector('[data-list-query]');
        if (next) {
          next.focus();
          try { next.setSelectionRange(pos, pos); } catch (_) {}
        }
      });
    }
  }

  window.WikiRender = {
    render: render,
    bind: bind,
    renderWindowPlaque: renderWindowPlaque,
    renderSeedOnlyBanner: renderSeedOnlyBanner,
    inlineDiff: inlineDiff
  };
})();
