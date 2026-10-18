// ClinicPulse — Premium Homepage Map
// Handles live updates, geolocation, and custom markers.
(function () {
  "use strict";

  var mapEl = document.getElementById("map");
  if (!mapEl || typeof L === "undefined") return;

  // Sekhukhune District, Limpopo
  var DEFAULT_CENTRE = [-24.75, 29.95];
  var DEFAULT_ZOOM = 9;

  var map = L.map(mapEl, {
    scrollWheelZoom: false,
    tap: true
  }).setView(DEFAULT_CENTRE, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  // Color mapping based on status
  function getMarkerColor(status) {
    var s = (status || "").toLowerCase();
    if (s === "open") return "#16A34A";     // Green
    if (s === "closed") return "#DC2626";   // Red
    if (s === "limited" || s === "limited services") return "#F59E0B"; // Orange
    return "#64748b"; // Grey
  }

  // Create a premium SVG map pin
  function makeIcon(color) {
    var svgIcon = '<svg width="30" height="42" viewBox="0 0 30 42" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 3px rgba(0,0,0,0.4));">' +
      '<path d="M15 0C6.71573 0 0 6.71573 0 15C0 26.25 15 42 15 42C15 42 30 26.25 30 15C30 6.71573 23.2843 0 15 0Z" fill="' + color + '"/>' +
      '<circle cx="15" cy="15" r="6" fill="white"/>' +
      '</svg>';

    return L.divIcon({
      className: "cp-marker",
      html: svgIcon,
      iconSize: [30, 42],
      iconAnchor: [15, 42],
      popupAnchor: [0, -38]
    });
  }

  // Safely escape text for the popup to prevent XSS
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  // Build the popup HTML
  function popupHtml(c) {
    var detailUrl = "/clinics/" + c.id;
    var statusClass = c.status ? c.status.toLowerCase() : "";
    
    return (
      '<div class="cp-popup" style="font-family: Inter, sans-serif; min-width: 180px;">' +
      '<strong style="font-size: 1.1rem; color: #12324F;">' + escapeHtml(c.name) + '</strong><br>' +
      '<span style="color:#4b5563; font-size:0.85rem;">📍 ' + escapeHtml(c.village || "") + '</span>' +
      '<div style="margin:12px 0; font-size:0.85rem; display:flex; flex-direction:column; gap:4px;">' +
        '<div style="display:flex; justify-content:space-between;"><span>Status:</span> <strong style="color:' + getMarkerColor(c.status) + '">' + escapeHtml(c.status || "—") + '</strong></div>' +
        '<div style="display:flex; justify-content:space-between;"><span>Queue:</span> <strong style="color:' + getMarkerColor(c.queue_status) + '">' + escapeHtml(c.queue_status || "—") + '</strong></div>' +
        '<div style="display:flex; justify-content:space-between;"><span>Meds:</span> <strong style="color:' + getMarkerColor(c.medication_status === 'Available' ? 'Open' : c.medication_status === 'Limited' ? 'Limited' : 'Closed') + '">' + escapeHtml(c.medication_status || "—") + '</strong></div>' +
      '</div>' +
      '<a href="' + detailUrl + '" style="display:block; text-align:center; background:#0E7C7B; color:white; padding:8px; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.9rem;">View Live Status</a>' +
      '</div>'
    );
  }

  var markersLayer = L.layerGroup().addTo(map);
  var markers = [];

  // Fetch and render clinics
  function loadClinics() {
    fetch("/api/clinics.json")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        markersLayer.clearLayers(); // Clear old markers for auto-refresh
        markers = [];

        (data.clinics || []).forEach(function (c) {
          if (!c.latitude || !c.longitude) return;
          
          var m = L.marker([c.latitude, c.longitude], {
            icon: makeIcon(getMarkerColor(c.status)),
            title: c.name
          }).bindPopup(popupHtml(c));
          
          m._clinic = c;
          markers.push(m);
          markersLayer.addLayer(m);
        });

        // Only fit bounds on the very first load
        if (markers.length && map._loadedCount === undefined) {
          var group = L.featureGroup(markers);
          map.fitBounds(group.getBounds().pad(0.15));
          map._loadedCount = 1;
        }
      })
      .catch(function (err) { console.error("Map data error", err); });
  }

  // Initial load
  loadClinics();

  // AUTO-REFRESH: Fetch new live statuses every 60 seconds
  setInterval(loadClinics, 60000);

  // --- "Find clinics near me" Logic ---
  var btn = document.getElementById("near-me-btn");
  var msg = document.getElementById("near-me-msg");

  function setMsg(t) { if (msg) msg.textContent = t || ""; }

  if (btn) {
    btn.addEventListener("click", function () {
      if (!("geolocation" in navigator)) {
        setMsg("Location is not supported on this device.");
        return;
      }
      setMsg("📍 Locating you...");
      btn.disabled = true;

      navigator.geolocation.getCurrentPosition(
        function (pos) {
          var here = [pos.coords.latitude, pos.coords.longitude];
          map.setView(here, 12);
          
          // Add a pulsing "You are here" blue dot
          L.circleMarker(here, {
            radius: 10, color: "#ffffff", fillColor: "#0E7C7B",
            fillOpacity: 1, weight: 3, className: "user-location-dot"
          }).addTo(map).bindPopup("You are here").openPopup();

          setMsg("Showing clinics around your location.");
          btn.disabled = false;

          // Find closest clinic and open its popup
          if (markers.length) {
            var closest = markers.slice().sort(function (a, b) {
              return map.distance(here, a.getLatLng()) - map.distance(here, b.getLatLng());
            })[0];
            closest.openPopup();
          }
        },
        function (err) {
          var human = "Could not get your location.";
          if (err && err.code === 1) human = "Location permission denied. Please allow location access in your browser.";
          if (err && err.code === 3) human = "Location request timed out. Try again.";
          setMsg(human);
          btn.disabled = false;
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  }
})();
