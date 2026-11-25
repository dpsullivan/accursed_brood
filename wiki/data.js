/* Accursed Brood — Companion Wiki Data Layer
 * Pure classic-script helpers for normalization, resistance decoding,
 * reverse cross-link indexing, global 10-category search, and Checklist derivation (ADR 0002).
 */
(function () {
  'use strict';

  var CATEGORIES = [
    { id: 'masters',    label: 'Masters',              short: 'Masters' },
    { id: 'characters', label: 'Characters & Classes', short: 'Party' },
    { id: 'genes',      label: 'Dragon Genes',         short: 'Genes' },
    { id: 'monsters',   label: 'Monsters',             short: 'Monsters' },
    { id: 'abilities',  label: 'Abilities',            short: 'Abilities' },
    { id: 'equipment',  label: 'Equipment & Items',    short: 'Gear' },
    { id: 'shops',      label: 'Shops',                short: 'Shops' },
    { id: 'manillos',   label: 'Manillos',             short: 'Manillos' },
    { id: 'chests',     label: 'Chests',               short: 'Chests' },
    { id: 'guardrails', label: 'Guardrails',           short: 'Guardrails' }
  ];

  var ELEMENTS = ['Fire', 'Frost', 'Thunder', 'Earth', 'Wind', 'Holy', 'Psionic', 'Status', 'Death'];

  var RES_TABLE = [
    { code: 0, short: '200%', label: 'Very Weak',     tone: 'vuln-2' },
    { code: 1, short: '150%', label: 'Weak',          tone: 'vuln-1' },
    { code: 2, short: '100%', label: 'Normal',        tone: 'neutral' },
    { code: 3, short: '50%',  label: 'Resist',        tone: 'res-1' },
    { code: 4, short: '25%',  label: 'Strong Resist', tone: 'res-2' },
    { code: 5, short: '0%',   label: 'Null',          tone: 'null' },
    { code: 6, short: 'ABS',  label: 'Absorb',        tone: 'absorb' },
    { code: 7, short: 'IMM',  label: 'Immune',        tone: 'immune' }
  ];

  function normalizeKey(str) {
    return String(str == null ? '' : str).toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  function decodeRes(val) {
    if (val && typeof val === 'object' && val.short && val.label) {
      return val;
    }
    var n = Math.max(0, Math.min(7, Number(val) || 0));
    return RES_TABLE[n] || RES_TABLE[2];
  }

  function ensureAbilityBucket(map, key) {
    if (!map[key]) {
      map[key] = { characters: [], masters: [], monsters: [] };
    }
    return map[key];
  }

  function ensureItemBucket(map, key) {
    if (!map[key]) {
      map[key] = { shops: [], manillos: [], chests: [], monsters: [] };
    }
    return map[key];
  }

  function buildCrossLinks(manifest) {
    var abilitySources = {};
    var itemSources = {};
    var abilityByKey = {};
    var equipmentByKey = {};
    var equipmentById = {};

    if (!manifest || !manifest.categories) {
      return {
        abilitySources: abilitySources,
        itemSources: itemSources,
        abilityByKey: abilityByKey,
        equipmentByKey: equipmentByKey,
        equipmentById: equipmentById
      };
    }

    var cats = manifest.categories;

    (cats.abilities || []).forEach(function (a) {
      var k = normalizeKey(a.name);
      abilityByKey[k] = a;
      ensureAbilityBucket(abilitySources, k);
    });

    (cats.equipment || []).forEach(function (e) {
      var k = normalizeKey(e.name);
      if (!equipmentByKey[k]) equipmentByKey[k] = e;
      equipmentById[e.id] = e;
      ensureItemBucket(itemSources, e.id);
      ensureItemBucket(itemSources, k);
    });

    // Ability reverse links: Characters (level-up)
    (cats.characters || []).forEach(function (c) {
      (c.spells || []).forEach(function (sp) {
        var k = normalizeKey(sp.name);
        ensureAbilityBucket(abilitySources, k).characters.push({
          id: c.id,
          name: c.name,
          class_name: c.class_name,
          level: sp.level
        });
      });
    });

    // Ability reverse links: Masters (apprenticeship)
    (cats.masters || []).forEach(function (m) {
      (m.skills || []).forEach(function (sk) {
        var k = normalizeKey(sk.name);
        ensureAbilityBucket(abilitySources, k).masters.push({
          id: m.id,
          name: m.name,
          kit_name: m.kit_name,
          level: sk.level
        });
      });
    });

    function addItemSource(itemId, itemName, bucketKey, rec) {
      var norm = normalizeKey(itemName);
      if (itemId) ensureItemBucket(itemSources, itemId)[bucketKey].push(rec);
      if (!itemId || norm !== itemId) ensureItemBucket(itemSources, norm)[bucketKey].push(rec);
    }

    // Ability reverse links (Monsters via Examine) & Equipment reverse links (Monster Steal/Drop)
    (cats.monsters || []).forEach(function (m) {
      (m.variants || []).forEach(function (v) {
        var areas = (v.areas && v.areas.length) ? v.areas : (m.areas || []);
        (v.abilities || []).forEach(function (ab) {
          if (!ab.learnable) return;
          var k = normalizeKey(ab.name);
          ensureAbilityBucket(abilitySources, k).monsters.push({
            id: m.id,
            name: m.name,
            slot: v.slot,
            tier: v.tier || m.tier,
            areas: areas
          });
        });

        if (v.steal && v.steal.item) {
          addItemSource(v.steal.item_id, v.steal.item, 'monsters', { id: m.id, name: m.name, slot: v.slot, tier: m.tier, method: 'Steal', rate: v.steal.rate });
        }
        if (v.drop && v.drop.item) {
          addItemSource(v.drop.item_id, v.drop.item, 'monsters', { id: m.id, name: m.name, slot: v.slot, tier: m.tier, method: 'Drop', rate: v.drop.rate });
        }
      });
    });

    // Equipment reverse links: Shops
    (cats.shops || []).forEach(function (s) {
      (s.stock || []).forEach(function (st) {
        addItemSource(st.item_id, st.item, 'shops', { id: s.id, name: s.name, tier: s.tier, price: st.price, guardrail: st.guardrail || null });
      });
    });

    // Equipment reverse links: Manillos
    (cats.manillos || []).forEach(function (tr) {
      (tr.trades || []).forEach(function (t) {
        addItemSource(t.item_id, t.item, 'manillos', { id: tr.id, name: tr.name, cost: t.cost });
      });
    });

    // Equipment reverse links: Chests
    (cats.chests || []).forEach(function (ch) {
      if (ch.is_zenny || !ch.item) return;
      addItemSource(ch.item_id, ch.item, 'chests', { id: ch.id, area: ch.area, tier: ch.tier });
    });

    return {
      abilitySources: abilitySources,
      itemSources: itemSources,
      abilityByKey: abilityByKey,
      equipmentByKey: equipmentByKey,
      equipmentById: equipmentById
    };
  }

  function getItemSources(crossLinks, item) {
    if (!crossLinks || !crossLinks.itemSources || !item) {
      return { shops: [], manillos: [], chests: [], monsters: [] };
    }
    return crossLinks.itemSources[item.id] || crossLinks.itemSources[normalizeKey(item.name)] || { shops: [], manillos: [], chests: [], monsters: [] };
  }

  function getAbilitySources(crossLinks, name) {
    if (!crossLinks || !crossLinks.abilitySources) {
      return { characters: [], masters: [], monsters: [] };
    }
    return crossLinks.abilitySources[normalizeKey(name)] || { characters: [], masters: [], monsters: [] };
  }

  function globalSearch(manifest, query) {
    if (!manifest || !manifest.categories) return [];
    var q = String(query || '').trim().toLowerCase();
    var cats = manifest.categories;
    var results = [];

    function pushIfMatch(scoreBase, catLabel, title, sub, route, drawerTarget, haystack) {
      var hay = String(haystack || (title + ' ' + sub)).toLowerCase();
      var score = scoreBase;
      if (q) {
        var idx = hay.indexOf(q);
        if (idx < 0) return;
        var titleLow = String(title).toLowerCase();
        if (titleLow === q) score += 100;
        else if (titleLow.indexOf(q) === 0) score += 60;
        else if (titleLow.indexOf(q) >= 0) score += 30;
        else score += 10;
      }
      results.push({
        score: score,
        cat: catLabel,
        title: title,
        sub: sub,
        route: route,
        drawerTarget: drawerTarget || null
      });
    }

    (cats.characters || []).forEach(function (c) {
      pushIfMatch(25, 'Party', c.name + ' → ' + c.class_name, (c.role || '') + ' · Join Lv' + c.join_level, '#/characters/' + encodeURIComponent(c.id), 'characters:' + c.id, c.name + ' ' + c.class_name + ' ' + (c.role || '') + ' ' + (c.weapons || []).join(' '));
    });

    (cats.masters || []).forEach(function (m) {
      var skText = (m.skills || []).map(function (s) { return s.name; }).join(', ');
      pushIfMatch(24, 'Master', m.name + ' — ' + m.kit_name, m.location + (skText ? ' · ' + skText : ''), '#/masters/' + encodeURIComponent(m.id), 'masters:' + m.id, m.name + ' ' + m.kit_name + ' ' + m.location + ' ' + skText);
    });

    (cats.genes || []).forEach(function (g) {
      pushIfMatch(22, 'Dragon Gene', g.gene + ' Gene', g.tier + ' Tier · ' + g.location, '#/genes', null, g.gene + ' ' + g.location + ' ' + g.tier + ' ' + (g.vanilla_gene || ''));
    });

    (cats.monsters || []).forEach(function (m) {
      var slotTxt = (m.variants || []).map(function (v) { return v.slot; }).join(', ');
      var areaTxt = (m.areas || []).slice(0, 2).join(', ');
      pushIfMatch(20, 'Monster', m.name, m.tier + (m.is_boss ? ' Boss' : '') + ' · ' + slotTxt + (areaTxt ? ' · ' + areaTxt : ''), '#/monsters/' + encodeURIComponent(m.id), 'monsters:' + m.id, m.name + ' ' + slotTxt + ' ' + (m.areas || []).join(' ') + ' ' + m.tier);
    });

    (cats.abilities || []).forEach(function (a) {
      pushIfMatch(19, 'Ability', a.name, a.ap + ' AP · ' + a.category + ' · ' + a.element, '#/abilities/' + encodeURIComponent(a.id), 'abilities:' + a.id, a.name + ' ' + a.category + ' ' + a.element + ' ' + (a.merged_slots || []).join(' '));
    });

    (cats.equipment || []).forEach(function (e) {
      pushIfMatch(18, 'Gear / Item', e.name, e.kind + (e.price ? ' · ' + e.price + 'Z' : ''), '#/equipment/' + encodeURIComponent(e.id), 'equipment:' + e.id, e.name + ' ' + e.kind + ' ' + (e.equip || []).join(' '));
    });

    (cats.shops || []).forEach(function (s) {
      var itemNames = (s.stock || []).map(function (st) { return st.item; }).join(', ');
      pushIfMatch(14, 'Shop', s.id + ' · ' + s.name, s.tier + ' Tier · ' + (s.stock || []).length + ' items', '#/shops', null, s.id + ' ' + s.name + ' ' + s.tier + ' ' + itemNames);
    });

    (cats.manillos || []).forEach(function (tr) {
      var tradeNames = (tr.trades || []).map(function (t) { return t.item + ' ' + t.cost; }).join(', ');
      pushIfMatch(13, 'Manillo', tr.name + ' Trader', (tr.trades || []).length + ' fish exchanges', '#/manillos', null, tr.name + ' ' + tradeNames);
    });

    (cats.chests || []).forEach(function (ch) {
      pushIfMatch(11, 'Chest', 'Chest ' + ch.id + ' — ' + ch.item, ch.tier + ' · ' + ch.area, '#/chests', null, ch.id + ' ' + ch.item + ' ' + ch.area + ' ' + ch.tier);
    });

    var g = cats.guardrails;
    if (g) {
      (g.crash_items || []).forEach(function (c) {
        pushIfMatch(10, 'Guardrail', c.subject, 'Crash Blacklist · ' + c.detail, '#/guardrails', null, 'guardrail crash ' + c.subject + ' ' + c.detail);
      });
      (g.weapon_items || []).forEach(function (w) {
        pushIfMatch(10, 'Guardrail', w.item || w.subject, w.shop_name + ' · ' + w.detail, '#/guardrails', null, 'guardrail weapon ' + w.subject + ' ' + w.detail);
      });
      (g.clamp_items || []).forEach(function (c) {
        pushIfMatch(9, 'Guardrail', c.subject, (c.tag || 'Clamped') + ' · ' + c.detail, '#/guardrails', null, 'guardrail clamp ' + c.subject + ' ' + c.detail);
      });
    }

    results.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.title.localeCompare(b.title);
    });
    return results.slice(0, 40);
  }

  function buildChecklist(manifest) {
    if (!manifest || !manifest.categories) {
      return [
        { id: 'genes',   label: 'Dragon Genes',            desc: 'All 17 pedestals grouped by tier', items: [] },
        { id: 'masters', label: 'Masters & Master Skills', desc: 'Apprenticeship skills across all Masters', items: [] },
        { id: 'skills',  label: 'Learnable Monster Skills', desc: 'Examinable skills with tier & spawn area', items: [] },
        { id: 'chests',  label: 'Chests',                  desc: 'Treasure chests grouped by area', items: [] }
      ];
    }

    var cats = manifest.categories;

    // 1. Dragon Genes (ordered Early -> Mid -> Late)
    var tierOrder = { Early: 0, Mid: 1, Late: 2 };
    var geneItems = (cats.genes || []).slice().sort(function (a, b) {
      var ta = tierOrder[a.tier] != null ? tierOrder[a.tier] : 9;
      var tb = tierOrder[b.tier] != null ? tierOrder[b.tier] : 9;
      if (ta !== tb) return ta - tb;
      return (a.index || 0) - (b.index || 0);
    }).map(function (g) {
      return {
        key: 'gene:' + g.id,
        label: g.gene + ' Gene',
        group: (g.tier || 'Early') + ' Tier',
        sub: g.location,
        route: '#/genes'
      };
    });

    // 2. Masters & Master Skills
    var masterItems = [];
    (cats.masters || []).forEach(function (m) {
      (m.skills || []).forEach(function (sk) {
        masterItems.push({
          key: 'master:' + m.id + ':' + normalizeKey(sk.name),
          label: sk.name,
          group: m.name + ' (+' + sk.level + 'Lv)',
          sub: (m.kit_name || 'Master') + ' · ' + (m.location || ''),
          route: '#/masters/' + encodeURIComponent(m.id)
        });
      });
    });

    // 3. Learnable Monster Skills (deduplicated per canonical skill name, listing sources/tiers/areas)
    var monsterSkillMap = {};
    var monsterTierRank = { Early: 0, Mid: 1, Late: 2, Protected: 3 };
    (cats.monsters || []).forEach(function (m) {
      (m.variants || []).forEach(function (v) {
        var areas = (v.areas && v.areas.length) ? v.areas : (m.areas || []);
        (v.abilities || []).forEach(function (ab) {
          if (!ab.learnable) return;
          var nk = normalizeKey(ab.name);
          if (!monsterSkillMap[nk]) {
            monsterSkillMap[nk] = {
              id: ab.id,
              name: ab.name,
              tier: v.tier || m.tier || 'Late',
              sources: []
            };
          }
          var entry = monsterSkillMap[nk];
          var curTier = v.tier || m.tier || 'Late';
          if ((monsterTierRank[curTier] != null ? monsterTierRank[curTier] : 9) < (monsterTierRank[entry.tier] != null ? monsterTierRank[entry.tier] : 9)) {
            entry.tier = curTier;
          }
          var srcTag = m.name + ' (' + v.slot + (areas[0] ? ', ' + areas[0] : '') + ')';
          if (entry.sources.indexOf(srcTag) < 0) {
            entry.sources.push(srcTag);
          }
        });
      });
    });

    var skillItems = Object.keys(monsterSkillMap).map(function (nk) {
      var entry = monsterSkillMap[nk];
      var preview = entry.sources.slice(0, 3).join(' · ') + (entry.sources.length > 3 ? ' +' + (entry.sources.length - 3) + ' more' : '');
      return {
        key: 'skill:' + nk,
        label: entry.name,
        group: entry.tier + ' Tier',
        sub: preview || 'Monster Examine',
        route: '#/abilities/' + encodeURIComponent(entry.id || nk),
        _tierRank: monsterTierRank[entry.tier] != null ? monsterTierRank[entry.tier] : 9
      };
    }).sort(function (a, b) {
      if (a._tierRank !== b._tierRank) return a._tierRank - b._tierRank;
      return a.label.localeCompare(b.label);
    });

    // 4. Chests (by area)
    var chestItems = (cats.chests || []).map(function (ch) {
      return {
        key: 'chest:' + ch.id,
        label: ch.item,
        group: ch.area,
        sub: 'Chest ' + ch.id + ' · ' + (ch.tier || 'Mid') + ' Tier',
        route: '#/chests'
      };
    });

    return [
      { id: 'genes',   label: 'Dragon Genes',             desc: 'All ' + geneItems.length + ' pedestals grouped by tier', items: geneItems },
      { id: 'masters', label: 'Masters & Master Skills',  desc: 'Apprenticeship skills across all Masters', items: masterItems },
      { id: 'skills',  label: 'Learnable Monster Skills', desc: 'Examinable skills with monster sources, tiers & areas', items: skillItems },
      { id: 'chests',  label: 'Chests',                   desc: 'Treasure chests grouped by area', items: chestItems }
    ];
  }

  function buildVanillaAbilitySignatures(baseline) {
    var sigs = {};
    if (!baseline || !baseline.categories) return sigs;
    var bcats = baseline.categories;
    function add(name, token) {
      var k = normalizeKey(name);
      if (!sigs[k]) sigs[k] = [];
      sigs[k].push(token);
    }
    Object.keys(bcats.characters || {}).forEach(function (cid) {
      var c = bcats.characters[cid];
      (c.spells || []).forEach(function (sp) { add(sp.name, 'c:' + cid + ':' + sp.level); });
    });
    Object.keys(bcats.masters || {}).forEach(function (mid) {
      var m = bcats.masters[mid];
      (m.skills || []).forEach(function (sk) { add(sk.name, 'm:' + mid + ':' + sk.level); });
    });
    Object.keys(bcats.monsters || {}).forEach(function (slot) {
      var mon = bcats.monsters[slot];
      (mon.abilities || []).forEach(function (ab) {
        if (ab.learnable) add(ab.name, 'e:' + slot);
      });
    });
    Object.keys(sigs).forEach(function (k) { sigs[k].sort(); });
    return sigs;
  }

  function abilitySourceSignature(src) {
    if (!src) return '';
    var parts = [];
    (src.characters || []).forEach(function (c) { parts.push('c:' + c.id + ':' + c.level); });
    (src.masters || []).forEach(function (m) { parts.push('m:' + m.id + ':' + m.level); });
    (src.monsters || []).forEach(function (m) { parts.push('e:' + m.slot); });
    parts.sort();
    return parts.join('|');
  }

  window.WikiData = {
    CATEGORIES: CATEGORIES,
    ELEMENTS: ELEMENTS,
    RES_TABLE: RES_TABLE,
    normalizeKey: normalizeKey,
    decodeRes: decodeRes,
    buildCrossLinks: buildCrossLinks,
    buildVanillaAbilitySignatures: buildVanillaAbilitySignatures,
    abilitySourceSignature: abilitySourceSignature,
    getItemSources: getItemSources,
    getAbilitySources: getAbilitySources,
    globalSearch: globalSearch,
    buildChecklist: buildChecklist
  };
})();
