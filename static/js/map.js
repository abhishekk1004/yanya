/* Home map: auto-cycles Nepal's 7 provinces 1→7, highlighting the active one
   in crimson and dropping its famous spots as markers. Clickable chips jump to
   a province; the tour is pausable. Fed live from /api/provinces?include=spots.
   Respects prefers-reduced-motion (no auto-tour, no animated pan). */
(function () {
  "use strict";

  var CRIMSON = "#dc143c", BLUE = "#003893", BLUE_BOLD = "#1e5bd6", MUTED = "#9aa6d4";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var map = L.map("map", { scrollWheelZoom: false, zoomControl: true })
    .setView([28.3, 84.0], 7);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18,
  }).addTo(map);

  // Type-specific emoji markers in a blue-outlined badge (temple, lake, …).
  var ICON_EMOJI = {
    lake: "🌊", temple: "🛕", mountain: "🏔️", wildlife: "🦏",
    monument: "🏛️", hill: "⛰️", star: "⭐",
  };
  function spotIcon(kind) {
    var emoji = ICON_EMOJI[kind] || ICON_EMOJI.star;
    return L.divIcon({
      className: "",
      html:
        '<div style="width:34px;height:34px;border-radius:50%;background:#0e1630;' +
        "border:3px solid " + BLUE + ";display:flex;align-items:center;" +
        'justify-content:center;font-size:17px;box-shadow:0 3px 8px rgba(0,0,0,.5)">' +
        emoji + "</div>",
      iconSize: [34, 34],
      iconAnchor: [17, 17],
      popupAnchor: [0, -18],
    });
  }

  var provinces = [];
  var provinceLayers = [];   // centroid circle OR boundary polygon per province
  var spotLayer = L.layerGroup().addTo(map);
  var current = 0, timer = null, playing = !reduceMotion;

  var chipsEl = document.getElementById("province-chips");
  var labelEl = document.getElementById("current-province");
  var toggleEl = document.getElementById("toggle-tour");

  function renderChips() {
    provinces.forEach(function (p, i) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = p.order + ". " + p.name;
      chip.addEventListener("click", function () { stopTour(); showProvince(i); });
      chipsEl.appendChild(chip);
    });
  }

  function showProvince(i) {
    current = i;
    var p = provinces[i];

    // Active province: bold blue boundary outline; others faint.
    provinceLayers.forEach(function (layer, j) {
      layer.setStyle({
        color: j === i ? BLUE_BOLD : MUTED,
        fillColor: j === i ? BLUE_BOLD : "transparent",
        fillOpacity: j === i ? 0.12 : 0,
        weight: j === i ? 5 : 1,
        opacity: j === i ? 1 : 0.5,
      });
      if (j === i && layer.bringToFront) layer.bringToFront();
    });

    // Drop this province's spots + fill the spot slider with image cards.
    spotLayer.clearLayers();
    var slider = document.getElementById("spot-slider");
    var title = document.getElementById("spot-title");
    if (title) title.textContent = "Famous spots in " + p.name;
    if (slider) slider.innerHTML = "";
    (p.spots || []).forEach(function (s) {
      L.marker([s.lat, s.lng], { icon: spotIcon(s.icon) })
        .bindPopup("<strong>" + s.name + "</strong><br>" + p.name)
        .addTo(spotLayer);
      if (slider) {
        var img = s.image_url
          ? '<img loading="lazy" src="' + s.image_url + '" alt="' + s.name +
            '" onerror="this.style.display=\'none\'">'
          : "";
        var el = document.createElement("div");
        el.className = "slide";
        el.innerHTML = img + '<div class="cap">' + s.name + "</div>";
        el.addEventListener("click", function () {
          map.setView([s.lat, s.lng], 10, { animate: !reduceMotion });
        });
        slider.appendChild(el);
      }
    });

    // Frame the province: fit its boundary if we have one, else centre on it.
    var active = provinceLayers[i];
    if (active && active.getBounds && active.getBounds().isValid()) {
      map.fitBounds(active.getBounds(), { padding: [30, 30], animate: !reduceMotion });
    } else {
      map.setView([p.center_lat, p.center_lng], 8, { animate: !reduceMotion });
    }

    // Update chips + live label.
    Array.prototype.forEach.call(chipsEl.children, function (c, j) {
      c.classList.toggle("active", j === i);
    });
    labelEl.textContent = "Now showing: " + p.name + " (province " + p.order + " of 7)";
  }

  function nextProvince() { showProvince((current + 1) % provinces.length); }

  function startTour() {
    if (timer || provinces.length === 0) return;
    playing = true;
    toggleEl.textContent = "Pause tour";
    toggleEl.setAttribute("aria-pressed", "true");
    timer = setInterval(nextProvince, 6000);  // 5–8s per province
  }
  function stopTour() {
    playing = false;
    toggleEl.textContent = "Play tour";
    toggleEl.setAttribute("aria-pressed", "false");
    if (timer) { clearInterval(timer); timer = null; }
  }
  toggleEl.addEventListener("click", function () { playing ? stopTour() : startTour(); });

  fetch("/api/provinces?include=spots")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      provinces = data.sort(function (a, b) { return a.order - b.order; });
      provinces.forEach(function (p) {
        // Real boundary polygon when loaded, else a centroid circle.
        var layer = p.boundary_geojson
          ? L.geoJSON(p.boundary_geojson, { style: { color: MUTED, weight: 1, fillOpacity: 0 } })
          : L.circleMarker([p.center_lat, p.center_lng], { radius: 12, color: MUTED, weight: 1, fillOpacity: 0 });
        layer.addTo(map).on("click", function () { stopTour(); showProvince(provinces.indexOf(p)); });
        provinceLayers.push(layer);
      });
      renderChips();
      showProvince(0);
      if (!reduceMotion) startTour();
    })
    .catch(function () {
      labelEl.textContent = "Could not load provinces. Is the API running?";
    });
})();
