// ClinicPulse — homepage map
// Lightweight, no deps beyond Leaflet (already loaded on the page).
(function () {
  "use strict";

  var mapEl = document.getElementById("map");
  if (!mapEl || typeof L === "undefined") return;

  // Sekhukhune District, Limpopo — approximate centre.
  var DEFAULT_CENTRE = [-24.75, 29.95];
  var DEFAULT_ZOOM = 9;

  var map = L.map(mapEl, {
    scrollWheelZoom: false, // mobile-friendly default
    tap: true
  }).setView(DEFAULT_CENTRE, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  function statusColor(status) {
    var s = (status || "").toLowerCase();
    if (s === "open") return "#16A34A";
    if (s === "closed") return "#DC2626";
    if (s === "limited" || s === "limited services") return "#F59E0B";
    return "#64748b";
  }

  function makeIcon(color) {
    return L.divIcon({
      className: "cp-marker",
      html:
        '<span style="display:block;width:18px;height:18px;border-radius:50%;' +
        "background:" + color + ";border:3px solid #fff;" +
        'box-shadow:0 1px 3px rgba(0,0,0,.35);"></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
      popupAnchor: [0, -8]
    });
  }

  function popupHtml(c) {
    var detailUrl = "/clinics/" + c.id;
    return (
      '<div class="cp-popup"><strong>' + escapeHtml(c.name) + "</strong><br>" +
      '<span style="color:#4b5563;font-size:12px;">' +
        escapeHtml(c.village || "") +
      "</span><br>" +
      '<div style="margin:6px 0;font-size:12px;">' +
        "Status: <strong>" + escapeHtml(c.status || "—") + "</strong><br>" +
        "Queue: <strong>" + escapeHtml(c.queue_status || "—") + "</strong><br>" +
        "Meds: <strong>" + escapeHtml(c.medication_status || "—") + "</strong>" +
      "</div>" +
      '<a href="' + detailUrl + '">View details &rarr;</a></div>'
    );
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
                '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  var markers = [];

  fetch("/api/clinics.json")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      (data.clinics || []).forEach(function (c) {
        if (!c.latitude || !c.longitude) return;
        var m = L.marker([c.latitude, c.longitude], {
          icon: makeIcon(statusColor(c.status)),
          title: c.name
        }).addTo(map).bindPopup(popupHtml(c));
        m._clinic = c;
        markers.push(m);
      });
      if (markers.length) {
        var group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.15));
      }
    })
    .catch(function () { /* non-fatal */ });

  // "Find clinics near me"
  var btn = document.getElementById("near-me-btn");
  var msg = document.getElementById("near-me-msg");

  function setMsg(t) { if (msg) msg.textContent = t || ""; }

  if (btn) {
    btn.addEventListener("click", function () {
      if (!("geolocation" in navigator)) {
        setMsg("Location is not supported on this device.");
        return;
      }
      setMsg("Locating you…");
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          var here = [pos.coords.latitude, pos.coords.longitude];
          map.setView(here, 12);
          L.circleMarker(here, {
            radius: 8, color: "#0E7C7B", fillColor: "#0E7C7B",
            fillOpacity: 0.6, weight: 2
          }).addTo(map).bindPopup("You are here").openPopup();
          setMsg("Showing clinics around your location.");
          // Sort markers by distance and open closest popup
          if (markers.length) {
            markers.slice().sort(function (a, b) {
              return map.distance(here, a.getLatLng())
                   - map.distance(here, b.getLatLng());
            })[0].openPopup();
          }
        },
        function (err) {
          var human = "Could not get your location.";
          if (err && err.code === 1) human = "Location permission denied.";
          if (err && err.code === 3) human = "Location request timed out.";
          setMsg(human + " Showing all clinics instead.");
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
      );
    });
  }
})();
