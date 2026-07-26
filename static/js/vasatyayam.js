(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var CRIMSON = "#dc143c";


  var map = null, routeLayer = null;
  try {
    map = L.map("map", { scrollWheelZoom: false }).setView([28.2, 84.0], 6.4);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors", maxZoom: 18,
    }).addTo(map);
    routeLayer = L.layerGroup().addTo(map);
  } catch (e) {
    var mapEl = document.getElementById("map");
    if (mapEl) mapEl.innerHTML = '<p class="meta" style="padding:1rem">Map unavailable, but planning still works.</p>';
  }

  var lastRoute = null;
  var customStops = [];       
  var fromPlace = null, toPlace = null; 

  function picks() {
    return [].slice.call(document.querySelectorAll(".pick:checked")).map(function (e) { return +e.value; });
  }
  function totalCount() {
    return picks().length + customStops.length + (fromPlace ? 1 : 0) + (toPlace ? 1 : 0);
  }
  function npr(n) { return "NPR " + Number(n).toLocaleString("en-IN"); }


  function runGeo(q, out, onPick) {
    q = (q || "").trim();
    if (q.length < 3) { out.innerHTML = '<span class="meta">Keep typing…</span>'; return; }
    out.innerHTML = '<span class="meta">Searching…</span>';
    fetch("/api/geocode?q=" + encodeURIComponent(q), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (rows) {
        out.innerHTML = "";
        if (!rows.length) { out.innerHTML = '<span class="meta">No match — try another spelling.</span>'; return; }
        var box = document.createElement("div");
        box.className = "glass geo-drop";
        rows.forEach(function (row) {
          var b = document.createElement("button");
          b.type = "button"; b.className = "chip-btn";
          b.textContent = "＋ " + row.full_name;
          b.addEventListener("click", function () { onPick(row); out.innerHTML = ""; });
          box.appendChild(b);
        });
        out.appendChild(box);
      })
      .catch(function (err) {
        out.innerHTML = '<span class="meta">Couldn’t search (' + err.message
          + '). Check your connection.</span>';
      });
  }


  function wireGeo(inputId, resId, btnId, onPick) {
    var input = document.getElementById(inputId);
    var out = document.getElementById(resId);
    var timer = null;
    function go() { runGeo(input.value, out, onPick); }
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(go, 450);   // debounce so Nominatim isn't hammered
    });
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); go(); } });
    if (btnId) document.getElementById(btnId).addEventListener("click", go);
  }


  wireGeo("from-q", "from-res", "from-find", function (row) {
    fromPlace = { name: row.name, lat: row.lat, lng: row.lng, cost: 0 };
    document.getElementById("from-q").value = row.name;
    document.getElementById("from-res").innerHTML = '<span class="meta">✓ From ' + row.name + "</span>";
  });
  wireGeo("to-q", "to-res", "to-find", function (row) {
    toPlace = { name: row.name, lat: row.lat, lng: row.lng, cost: 0 };
    document.getElementById("to-q").value = row.name;
    document.getElementById("to-res").innerHTML = '<span class="meta">✓ To ' + row.name + "</span>";
  });


  function renderChips() {
    var box = document.getElementById("custom-chips");
    box.innerHTML = "";
    customStops.forEach(function (s, i) {
      var chip = document.createElement("button");
      chip.type = "button"; chip.className = "chip-btn saved";
      chip.innerHTML = "📍 " + s.name + " ✕";
      chip.title = "Remove";
      chip.addEventListener("click", function () { customStops.splice(i, 1); renderChips(); });
      box.appendChild(chip);
    });
  }
  wireGeo("custom-q", "geo-results", "find-btn", function (row) {
    customStops.push({ name: row.name, lat: row.lat, lng: row.lng, cost: 0 });
    renderChips();
    document.getElementById("custom-q").value = "";
  });

  function api(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
      body: JSON.stringify(body),
    }).then(function (r) { return r.json().then(function (d) { if (!r.ok) throw d; return d; }); });
  }

  function draw(order) {
    if (!map || !routeLayer) return;   
    routeLayer.clearLayers();
    var pts = [];
    order.forEach(function (s, i) {
      var d = s.destination; pts.push([d.lat, d.lng]);
      L.marker([d.lat, d.lng]).bindPopup("<strong>" + (i + 1) + ". " + d.name + "</strong>").addTo(routeLayer);
    });
    if (pts.length) {
      L.polyline(pts, { color: CRIMSON, weight: 4, opacity: 0.85 }).addTo(routeLayer);
      map.fitBounds(pts, { padding: [40, 40], animate: !reduce });
    }
  }

  function card(d) {
    var img = d.image_url ? '<div class="ph"><img loading="lazy" src="' + d.image_url +
      '" alt="" onerror="this.closest(\'.ph\').remove()"></div>' : "";
    return '<article class="pcard">' + img + '<div class="scrim"></div><div class="body">' +
      '<h3>' + d.name + '</h3><div class="meta">' + d.province_name + " · " + npr(d.cost_npr) +
      '</div></div></article>';
  }

  document.getElementById("optimize-btn").addEventListener("click", function () {
    if (totalCount() < 2) { alert("Add at least two places (From/To, picks or stops)."); return; }
    api("/api/itineraries/optimize", {
      destination_ids: picks(),
      custom: customStops,
      from_place: fromPlace,
      to_place: toPlace,
      budget: parseInt(document.getElementById("trip-budget").value, 10) || null,
    }).then(function (r) {
      lastRoute = r;
      draw(r.order);
      document.getElementById("breakdown").style.display = "block";
      document.getElementById("s-days").textContent = r.days + " days";
      document.getElementById("s-dist").textContent = r.distance_km + " km";
      document.getElementById("s-travel").textContent = npr(r.travel_cost_npr);
      document.getElementById("s-visit").textContent = npr(r.visit_cost_npr);
      document.getElementById("s-stay").textContent = npr(r.lodging_food_npr);
      document.getElementById("s-total").textContent = npr(r.grand_total_npr);
      var flag = document.getElementById("budget-flag");
      flag.textContent = r.within_budget ? "within budget ✓" : "over budget — trim a stop";
      flag.style.color = r.within_budget ? "#7CFFB2" : "#ff9a9a";
      document.getElementById("route-list").innerHTML = r.order.map(function (s) {
        return s.order + ". " + s.destination.name + " — leg " + npr(s.leg_cost_npr);
      }).join("<br>")
        + "<br><em>Road transport estimated at NPR " + r.transport_rate_npr_per_km
        + "/km; stay + food NPR " + npr(r.per_diem_npr).replace("NPR ", "") + "/day.</em>"
        + (r.dropped.length ? "<br><em>Dropped " + r.dropped.length + " stop(s) to fit budget.</em>" : "");

      var sim = document.getElementById("similar");
      if (r.suggestions && r.suggestions.length) {
        sim.innerHTML = r.suggestions.map(card).join("");
        document.getElementById("similar-wrap").style.display = "block";
      }


      var tw = document.getElementById("transport-wrap");
      if (r.transport && r.transport.length) {
        document.getElementById("transport").innerHTML = r.transport.map(function (t, i) {
          return '<div class="glass" style="padding:0.7rem">' +
            '<div>' + t.emoji + " <strong>" + t.name + "</strong>" +
            (i === 0 ? ' <span class="tag on">best value</span>' : "") + "</div>" +
            '<div class="meta">' + npr(t.cost_npr) + " · " + t.hours + "h</div></div>";
        }).join("");
        tw.style.display = "block";
      }


      var sw = document.getElementById("stays-wrap");
      if (r.stays && r.stays.length) {
        document.getElementById("stays-sub").textContent =
          "best fits · budget ~" + npr(r.nightly_budget_npr) + "/night";
        document.getElementById("stays").innerHTML = r.stays.map(function (h, i) {
          var img = h.image_url ? '<div class="ph"><img loading="lazy" src="' + h.image_url +
            '" alt="" onerror="this.closest(\'.ph\').remove()"></div>' : "";
          var badge = i === 0 ? ' <span class="tag on">Best match</span>' : "";
          return '<article class="pcard" style="--grad:linear-gradient(135deg,#12324f,#2f7fb5)">' +
            img + '<div class="scrim"></div><div class="body"><h3>' + h.name + "</h3>" +
            '<div class="meta">' + h.city + " · " + npr(h.price_npr) + "/night · " + h.star_rating +
            "★</div>" + badge + "</div></article>";
        }).join("");
        sw.style.display = "block";
      }

      document.getElementById("save-btn").disabled = false;
    }).catch(function (e) { alert((e && e.detail) || "Could not generate the itinerary."); });
  });

  document.getElementById("save-btn").addEventListener("click", function () {
    api("/api/itineraries", {
      destination_ids: picks(),
      custom: customStops,
      from_place: fromPlace,
      to_place: toPlace,
      budget: parseInt(document.getElementById("trip-budget").value, 10) || null,
      name: document.getElementById("trip-name").value || "My trip",
    }).then(function (s) {
      document.getElementById("budget-flag").textContent = "saved “" + s.name + "” ✓";
    }).catch(function () { alert("Could not save the trip."); });
  });


  if (picks().length >= 2) document.getElementById("optimize-btn").click();
})();
