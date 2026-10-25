/*
 * Search for self-hosted Mintlify docs.
 *
 * Mintlify's own search asks its cloud service and an export that never signed
 * in only says so in the bar. This takes the search bar and ctrl-k before that
 * handler runs, and answers from the index mintsearch writes beside the pages.
 */
(function () {
  "use strict";

  var INDEX = (document.currentScript && document.currentScript.getAttribute("data-index")) || "/mintsearch.json";
  var RESULTS = 8;
  var SNIPPET = 90;

  var pages = null;
  var loading = null;
  var overlay = null;
  var field = null;
  var list = null;
  var chosen = 0;
  var showing = [];

  function load() {
    if (pages) return Promise.resolve(pages);
    if (!loading) {
      loading = fetch(INDEX)
        .then(function (response) {
          return response.ok ? response.json() : { pages: [] };
        })
        .then(function (data) {
          pages = data.pages || [];
          return pages;
        })
        .catch(function () {
          pages = [];
          return pages;
        });
    }
    return loading;
  }

  function terms(query) {
    return query
      .toLowerCase()
      .split(/[^a-z0-9#,._/@-]+/)
      .filter(function (word) {
        return word.length > 1;
      });
  }

  function hits(text, word) {
    if (!text) return 0;
    var found = 0;
    var at = text.toLowerCase().indexOf(word);
    while (at !== -1 && found < 12) {
      found += 1;
      at = text.toLowerCase().indexOf(word, at + word.length);
    }
    return found;
  }

  // a page's title counts most, then a heading, then the words on it
  function score(page, words, phrase) {
    var total = 0;
    var best = null;
    words.forEach(function (word) {
      total += hits(page.title, word) * 8;
      total += hits(page.description, word) * 3;
      total += hits(page.group, word) * 2;
    });
    page.sections.forEach(function (section) {
      var here = 0;
      words.forEach(function (word) {
        here += hits(section.heading, word) * 4;
        here += hits(section.text, word);
      });
      if (phrase.length > 2) {
        if (section.text.toLowerCase().indexOf(phrase) !== -1) here += 6;
        if (section.heading.toLowerCase().indexOf(phrase) !== -1) here += 10;
      }
      if (here > 0) total += here;
      if (here > 0 && (best === null || here > best.score)) best = { section: section, score: here };
    });
    if (phrase.length > 2 && page.title.toLowerCase().indexOf(phrase) !== -1) total += 12;
    return { score: total, best: best };
  }

  function search(query) {
    var words = terms(query);
    if (!words.length) return [];
    var phrase = query.toLowerCase().trim();
    var found = [];
    (pages || []).forEach(function (page) {
      var rated = score(page, words, phrase);
      if (rated.score > 0) found.push({ page: page, score: rated.score, best: rated.best });
    });
    found.sort(function (a, b) {
      return b.score - a.score;
    });
    return found.slice(0, RESULTS);
  }

  function escaped(text) {
    return String(text).replace(/[&<>"]/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[character];
    });
  }

  function marked(text, words) {
    var safe = escaped(text);
    words.forEach(function (word) {
      var pattern = new RegExp("(" + word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
      safe = safe.replace(pattern, "<mark>$1</mark>");
    });
    return safe;
  }

  function snippet(section, words) {
    if (!section || !section.text) return "";
    var text = section.text;
    var at = -1;
    words.some(function (word) {
      at = text.toLowerCase().indexOf(word);
      return at !== -1;
    });
    if (at === -1) at = 0;
    var from = Math.max(0, at - SNIPPET / 2);
    var cut = text.slice(from, from + SNIPPET * 2);
    return (from > 0 ? "…" : "") + cut + (from + SNIPPET * 2 < text.length ? "…" : "");
  }

  function render(query) {
    var words = terms(query);
    showing = search(query);
    if (!query.trim()) {
      list.innerHTML = '<li class="mintsearch-note">type to search the docs</li>';
      return;
    }
    if (!showing.length) {
      list.innerHTML = '<li class="mintsearch-note">nothing matched ' + escaped(query) + "</li>";
      return;
    }
    chosen = 0;
    list.innerHTML = showing
      .map(function (found, index) {
        var page = found.page;
        var heading = found.best && found.best.section.heading ? found.best.section.heading : "";
        return (
          '<li class="mintsearch-result' +
          (index === 0 ? " chosen" : "") +
          '" data-index="' +
          index +
          '"><a href="' +
          escaped(page.url) +
          '"><span class="mintsearch-title">' +
          marked(page.title, words) +
          (heading ? ' <span class="mintsearch-heading">' + marked(heading, words) + "</span>" : "") +
          '</span><span class="mintsearch-where">' +
          escaped(page.group || "docs") +
          '</span><span class="mintsearch-text">' +
          marked(snippet(found.best && found.best.section, words), words) +
          "</span></a></li>"
        );
      })
      .join("");
  }

  function build() {
    overlay = document.createElement("div");
    overlay.className = "mintsearch";
    overlay.hidden = true;
    overlay.innerHTML =
      '<div class="mintsearch-back"></div><div class="mintsearch-panel" role="dialog" aria-modal="true" aria-label="search the docs">' +
      '<input class="mintsearch-field" type="text" placeholder="search the docs" autocomplete="off" spellcheck="false" aria-label="search the docs">' +
      '<ul class="mintsearch-list"></ul>' +
      '<div class="mintsearch-foot"><span>↑↓ move</span><span>↵ open</span><span>esc close</span></div></div>';
    document.body.appendChild(overlay);
    field = overlay.querySelector(".mintsearch-field");
    list = overlay.querySelector(".mintsearch-list");
    overlay.querySelector(".mintsearch-back").addEventListener("click", close);
    field.addEventListener("input", function () {
      render(field.value);
    });
    list.addEventListener("mousemove", function (event) {
      var item = event.target.closest(".mintsearch-result");
      if (item) pick(Number(item.dataset.index));
    });
  }

  function pick(index) {
    if (!showing.length) return;
    chosen = (index + showing.length) % showing.length;
    Array.prototype.forEach.call(list.children, function (item, at) {
      item.classList.toggle("chosen", at === chosen);
    });
    var item = list.children[chosen];
    if (item && item.scrollIntoView) item.scrollIntoView({ block: "nearest" });
  }

  function open() {
    if (!overlay) build();
    load().then(function () {
      render(field.value);
    });
    overlay.hidden = false;
    document.documentElement.classList.add("mintsearch-open");
    field.focus();
    field.select();
  }

  function close() {
    if (!overlay) return;
    overlay.hidden = true;
    document.documentElement.classList.remove("mintsearch-open");
  }

  function opened() {
    return overlay && !overlay.hidden;
  }

  // the search bar is mintlify's own button: take the click in the capture
  // phase, before react's handler on the page root ever sees it
  document.addEventListener(
    "click",
    function (event) {
      var trigger = event.target.closest && event.target.closest("#search-bar-entry, #search-bar-entry-mobile");
      if (!trigger) return;
      event.preventDefault();
      event.stopPropagation();
      open();
    },
    true
  );

  // a key arrives named, or as its code, or as neither: some senders leave
  // `key` empty and only set `keyCode`, and enter has to work either way
  function pressed(event, name, code) {
    var named = String(event.key || "").toLowerCase();
    var coded = String(event.code || "").toLowerCase();
    return named === name || coded === name || event.keyCode === code;
  }

  window.addEventListener(
    "keydown",
    function (event) {
      if ((event.ctrlKey || event.metaKey) && pressed(event, "k", 75)) {
        event.preventDefault();
        event.stopPropagation();
        opened() ? close() : open();
        return;
      }
      if (!opened()) return;
      if (pressed(event, "escape", 27)) {
        event.preventDefault();
        event.stopPropagation();
        close();
        return;
      }
      if (pressed(event, "arrowdown", 40) || pressed(event, "arrowup", 38)) {
        event.preventDefault();
        pick(chosen + (pressed(event, "arrowdown", 40) ? 1 : -1));
        return;
      }
      if (pressed(event, "enter", 13) && showing.length) {
        event.preventDefault();
        window.location.href = showing[chosen].page.url;
      }
    },
    true
  );
})();
