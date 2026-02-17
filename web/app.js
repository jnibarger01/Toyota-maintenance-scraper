/**
 * Toyota Maintenance Dashboard - Client-side Application
 *
 * Loads JSONL data from the API (or sample_data/ fallback),
 * renders vehicle cards with maintenance schedules, specs, and service info.
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  maintenance: [],
  vehicleSpecs: [],
  serviceSpecs: [],
  filteredMaintenance: [],
  compareMode: false,
};

// All Toyota models from the scraper config (mirrors config/models.py)
const ALL_MODELS = [
  "4Runner", "Avalon", "bZ4X", "Camry", "Corolla", "Corolla Cross", "Crown",
  "Crown Signia", "GR Corolla", "GR Supra", "GR86", "Grand Highlander",
  "Highlander", "Land Cruiser", "Mirai", "Prius", "RAV4", "Sequoia",
  "Sienna", "Tacoma", "Tundra", "Venza",
];

const YEARS = [];
for (let y = 2025; y >= 2018; y--) YEARS.push(y);

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

/** Parse a JSONL string into an array of objects. */
function parseJSONL(text) {
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

/**
 * Attempt to load data from the API first, then fall back to sample_data/.
 */
async function loadData() {
  showLoading(true);

  // Try API endpoints first, then fall back to static JSONL files
  const endpoints = {
    maintenance: ["/api/maintenance", "sample_data/maintenance.jsonl"],
    vehicleSpecs: ["/api/specs", "sample_data/vehicle_specs.jsonl"],
    serviceSpecs: ["/api/service-specs", "sample_data/service_specs.jsonl"],
  };

  for (const [key, [apiUrl, fallbackUrl]] of Object.entries(endpoints)) {
    try {
      // Try API first
      const apiResp = await fetch(apiUrl);
      if (apiResp.ok) {
        const contentType = apiResp.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          state[key] = await apiResp.json();
        } else {
          state[key] = parseJSONL(await apiResp.text());
        }
        continue;
      }
    } catch {
      // API not available, fall through
    }

    // Fallback to static JSONL
    try {
      const resp = await fetch(fallbackUrl);
      if (resp.ok) {
        state[key] = parseJSONL(await resp.text());
      }
    } catch {
      console.warn(`Failed to load ${key} from both API and fallback`);
    }
  }

  state.filteredMaintenance = [...state.maintenance];
  showLoading(false);
}

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function showLoading(show) {
  $("#loading").classList.toggle("hidden", !show);
}

// ---------------------------------------------------------------------------
// Populate selectors
// ---------------------------------------------------------------------------

function populateSelectors() {
  const yearSelect = $("#select-year");
  const modelSelect = $("#select-model");

  // Years
  YEARS.forEach((y) => {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    yearSelect.appendChild(opt);
  });

  // Models
  ALL_MODELS.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    modelSelect.appendChild(opt);
  });

  // Compare dropdowns
  populateCompareDropdowns();
}

function populateCompareDropdowns() {
  const selA = $("#compare-a");
  const selB = $("#compare-b");
  [selA, selB].forEach((sel) => {
    // Clear existing options beyond the placeholder
    while (sel.options.length > 1) sel.remove(1);
    state.maintenance.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = `${v.model}|${v.year}`;
      opt.textContent = `${v.year} ${v.model}`;
      sel.appendChild(opt);
    });
  });
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

function applyFilters() {
  const year = $("#select-year").value;
  const model = $("#select-model").value;
  const search = $("#search-service").value.toLowerCase().trim();
  const category = $("#filter-category").value;

  state.filteredMaintenance = state.maintenance.filter((vehicle) => {
    if (year && vehicle.year !== parseInt(year)) return false;
    if (model && vehicle.model !== model) return false;

    if (search || category) {
      // Check if any interval has matching items
      const hasMatch = vehicle.maintenance_schedule.some((interval) =>
        interval.items.some((item) => {
          const matchSearch = !search || item.service.toLowerCase().includes(search);
          const matchCat = !category || item.category === category;
          return matchSearch && matchCat;
        })
      );
      if (!hasMatch) return false;
    }

    return true;
  });

  renderVehicleCards();
}

// ---------------------------------------------------------------------------
// Rendering - Vehicle Cards
// ---------------------------------------------------------------------------

function renderVehicleCards() {
  const container = $("#vehicle-cards");
  const noResults = $("#no-results");
  container.innerHTML = "";

  if (state.filteredMaintenance.length === 0) {
    noResults.classList.remove("hidden");
    return;
  }
  noResults.classList.add("hidden");

  state.filteredMaintenance.forEach((vehicle) => {
    const card = createVehicleCard(vehicle);
    container.appendChild(card);
  });
}

function createVehicleCard(vehicle) {
  const template = $("#tmpl-vehicle-card");
  const clone = template.content.cloneNode(true);
  const article = clone.querySelector("article");

  // Header
  article.querySelector(".card-title").textContent =
    `${vehicle.year} Toyota ${vehicle.model}`;
  article.querySelector(".card-subtitle").textContent =
    `${vehicle.maintenance_schedule.length} maintenance intervals`;
  article.querySelector(".card-badge").textContent = vehicle.year;

  // Schedule tab
  const tbody = article.querySelector(".schedule-body");
  renderScheduleRows(tbody, vehicle);

  // Specs tab
  const specsContent = article.querySelector(".specs-content");
  renderSpecsPanel(specsContent, vehicle);

  // Service tab
  const serviceContent = article.querySelector(".service-content");
  renderServicePanel(serviceContent, vehicle);

  // Tab switching
  const tabBtns = article.querySelectorAll(".tab-btn");
  const tabPanels = article.querySelectorAll(".tab-panel");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => {
        b.classList.remove("active", "border-toyota-red", "text-toyota-red");
        b.classList.add("border-transparent", "text-gray-500");
      });
      btn.classList.add("active", "border-toyota-red", "text-toyota-red");
      btn.classList.remove("border-transparent", "text-gray-500");

      const target = btn.dataset.tab;
      tabPanels.forEach((p) => {
        p.classList.toggle("hidden", p.dataset.panel !== target);
      });
    });
  });

  return clone;
}

// ---------------------------------------------------------------------------
// Rendering - Schedule Table
// ---------------------------------------------------------------------------

function renderScheduleRows(tbody, vehicle) {
  const search = $("#search-service").value.toLowerCase().trim();
  const category = $("#filter-category").value;

  // Sort intervals by mileage
  const sorted = [...vehicle.maintenance_schedule].sort(
    (a, b) => a.interval_miles - b.interval_miles
  );

  sorted.forEach((interval) => {
    let items = interval.items;

    // Apply item-level filters
    if (search) {
      items = items.filter((i) => i.service.toLowerCase().includes(search));
    }
    if (category) {
      items = items.filter((i) => i.category === category);
    }
    if (items.length === 0) return;

    // Group items by category
    const standard = items.filter((i) => i.category === "standard");
    const inspections = items.filter((i) => i.category === "inspection");
    const special = items.filter((i) => i.category === "special_condition");

    const allGroups = [
      ...standard.map((i) => ({ ...i, group: "standard" })),
      ...inspections.map((i) => ({ ...i, group: "inspection" })),
      ...special.map((i) => ({ ...i, group: "special_condition" })),
    ];

    allGroups.forEach((item, idx) => {
      const tr = document.createElement("tr");
      tr.className = "border-b border-gray-100 hover:bg-gray-50 transition-colors";

      // Interval cell (only first row per interval)
      const tdInterval = document.createElement("td");
      tdInterval.className = "py-2 pr-4 align-top whitespace-nowrap";
      if (idx === 0) {
        tdInterval.innerHTML = `
          <div class="font-semibold text-gray-900">${formatMiles(interval.interval_miles)}</div>
          <div class="text-xs text-gray-400">${interval.interval_months} months</div>
        `;
        tdInterval.rowSpan = allGroups.length;
      } else {
        tdInterval.classList.add("hidden");
      }
      // Only append if first row
      if (idx === 0) tr.appendChild(tdInterval);

      // Service cell
      const tdService = document.createElement("td");
      tdService.className = "py-2 pr-4";
      let serviceHTML = item.service;
      if (item.condition) {
        serviceHTML += ` <span class="condition-badge">${formatCondition(item.condition)}</span>`;
      }
      tdService.innerHTML = serviceHTML;
      tr.appendChild(tdService);

      // Category cell
      const tdCat = document.createElement("td");
      tdCat.className = "py-2 whitespace-nowrap";
      tdCat.innerHTML = `<span class="category-badge category-${item.group}">${formatCategory(item.group)}</span>`;
      tr.appendChild(tdCat);

      tbody.appendChild(tr);
    });
  });
}

// ---------------------------------------------------------------------------
// Rendering - Specs Panel
// ---------------------------------------------------------------------------

function renderSpecsPanel(container, vehicle) {
  // Find matching specs from vehicle_specs data
  const specs = state.vehicleSpecs.filter(
    (s) =>
      s.year === vehicle.year &&
      (s.model === vehicle.model ||
        s.model === `${vehicle.model} Hybrid` ||
        s.model === vehicle.model.replace(" ", ""))
  );

  if (specs.length === 0) {
    container.innerHTML = `<p class="text-gray-400 text-sm">No EPA specs data available for this vehicle.</p>`;
    return;
  }

  let html = '<div class="grid grid-cols-1 md:grid-cols-2 gap-4">';

  specs.forEach((spec) => {
    html += `
      <div class="spec-card border border-gray-200 rounded-lg p-4">
        <h4 class="font-semibold text-gray-800 mb-3">${spec.option_description || `${spec.model}`}</h4>
        <div class="grid grid-cols-2 gap-y-2 text-sm">
          ${specRow("Engine", spec.engine_displacement ? `${spec.engine_displacement}L ${spec.cylinders}-cyl` : "N/A")}
          ${specRow("Transmission", spec.transmission || "N/A")}
          ${specRow("Drivetrain", spec.drive || "N/A")}
          ${specRow("Fuel Type", spec.fuel_type || "N/A")}
          ${specRow("Vehicle Class", spec.vehicle_class || "N/A")}
        </div>
        <div class="mt-3 pt-3 border-t border-gray-100">
          <div class="flex items-center gap-4">
            ${mpgBadge("City", spec.mpg_city)}
            ${mpgBadge("Hwy", spec.mpg_highway)}
            ${mpgBadge("Comb", spec.mpg_combined)}
          </div>
          ${spec.annual_fuel_cost ? `<p class="text-xs text-gray-400 mt-2">Est. annual fuel cost: $${spec.annual_fuel_cost.toLocaleString()}</p>` : ""}
        </div>
        ${spec.atv_type ? `<div class="mt-2"><span class="inline-block bg-green-100 text-green-800 text-xs font-medium px-2 py-0.5 rounded">${spec.atv_type}</span></div>` : ""}
      </div>
    `;
  });

  html += "</div>";
  container.innerHTML = html;
}

function specRow(label, value) {
  return `
    <div class="text-gray-500">${label}</div>
    <div class="text-gray-900 font-medium">${value}</div>
  `;
}

function mpgBadge(label, value) {
  if (!value) return "";
  return `
    <div class="text-center">
      <div class="text-2xl font-bold text-toyota-red">${value}</div>
      <div class="text-xs text-gray-400">${label} MPG</div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Rendering - Service Specs Panel
// ---------------------------------------------------------------------------

function renderServicePanel(container, vehicle) {
  const specs = state.serviceSpecs.find(
    (s) => s.model === vehicle.model && s.year === vehicle.year
  );

  if (!specs) {
    container.innerHTML = `<p class="text-gray-400 text-sm">No service specs available for this vehicle.</p>`;
    return;
  }

  let html = '<div class="space-y-4">';

  // Fluids table
  if (specs.fluids && specs.fluids.length > 0) {
    html += `
      <div>
        <h4 class="font-semibold text-gray-800 mb-2">Fluids &amp; Capacities</h4>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200">
                <th class="text-left py-2 pr-4 font-medium text-gray-600">Fluid</th>
                <th class="text-left py-2 pr-4 font-medium text-gray-600">Capacity</th>
                <th class="text-left py-2 font-medium text-gray-600">Specification</th>
              </tr>
            </thead>
            <tbody>
    `;
    specs.fluids.forEach((fluid) => {
      html += `
        <tr class="border-b border-gray-100">
          <td class="py-2 pr-4 font-medium text-gray-900">${fluid.type}</td>
          <td class="py-2 pr-4 text-gray-700">${fluid.capacity}</td>
          <td class="py-2 text-gray-700">${fluid.specification}</td>
        </tr>
      `;
    });
    html += "</tbody></table></div></div>";
  }

  // Tire pressure & battery
  html += '<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">';

  if (specs.tire_pressure) {
    html += `
      <div class="border border-gray-200 rounded-lg p-4">
        <h4 class="font-semibold text-gray-800 mb-2">Tire Pressure</h4>
        <div class="grid grid-cols-2 gap-y-1 text-sm">
          ${specRow("Front", typeof specs.tire_pressure === "object" ? specs.tire_pressure.front : specs.tire_pressure)}
          ${specRow("Rear", typeof specs.tire_pressure === "object" ? specs.tire_pressure.rear : specs.tire_pressure)}
        </div>
      </div>
    `;
  }

  if (specs.battery_type) {
    html += `
      <div class="border border-gray-200 rounded-lg p-4">
        <h4 class="font-semibold text-gray-800 mb-2">Battery</h4>
        <p class="text-sm text-gray-700">${specs.battery_type}</p>
      </div>
    `;
  }

  html += "</div></div>";
  container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Compare Mode
// ---------------------------------------------------------------------------

function toggleCompare(show) {
  state.compareMode = show;
  $("#compare-panel").classList.toggle("hidden", !show);
  if (show) {
    populateCompareDropdowns();
  }
}

function renderComparison() {
  const aVal = $("#compare-a").value;
  const bVal = $("#compare-b").value;
  const container = $("#compare-results");

  if (!aVal || !bVal) {
    container.innerHTML = '<p class="text-gray-400 text-sm">Select two vehicles to compare.</p>';
    return;
  }

  const [aModel, aYear] = aVal.split("|");
  const [bModel, bYear] = bVal.split("|");

  const vehicleA = state.maintenance.find(
    (v) => v.model === aModel && v.year === parseInt(aYear)
  );
  const vehicleB = state.maintenance.find(
    (v) => v.model === bModel && v.year === parseInt(bYear)
  );

  if (!vehicleA || !vehicleB) {
    container.innerHTML = '<p class="text-gray-400 text-sm">Vehicle data not found.</p>';
    return;
  }

  // Collect all unique intervals
  const allIntervals = new Set();
  vehicleA.maintenance_schedule.forEach((i) => allIntervals.add(i.interval_miles));
  vehicleB.maintenance_schedule.forEach((i) => allIntervals.add(i.interval_miles));
  const sortedIntervals = [...allIntervals].sort((a, b) => a - b);

  let html = `
    <div class="overflow-x-auto">
      <table class="w-full text-sm compare-table">
        <thead>
          <tr class="border-b-2 border-gray-200">
            <th class="text-left py-3 pr-4 font-semibold text-gray-700">Interval</th>
            <th class="text-left py-3 pr-4 font-semibold text-toyota-red">${vehicleA.year} ${vehicleA.model}</th>
            <th class="text-left py-3 font-semibold text-blue-600">${vehicleB.year} ${vehicleB.model}</th>
          </tr>
        </thead>
        <tbody>
  `;

  sortedIntervals.forEach((miles) => {
    const intA = vehicleA.maintenance_schedule.find(
      (i) => i.interval_miles === miles
    );
    const intB = vehicleB.maintenance_schedule.find(
      (i) => i.interval_miles === miles
    );

    const itemsA = intA ? intA.items.map((i) => i.service) : [];
    const itemsB = intB ? intB.items.map((i) => i.service) : [];

    // Find differences
    const onlyA = itemsA.filter((s) => !itemsB.includes(s));
    const onlyB = itemsB.filter((s) => !itemsA.includes(s));
    const common = itemsA.filter((s) => itemsB.includes(s));

    html += `
      <tr class="border-b border-gray-100">
        <td class="py-3 pr-4 align-top font-semibold whitespace-nowrap">${formatMiles(miles)}</td>
        <td class="py-3 pr-4 align-top">
          ${common.map((s) => `<div class="text-gray-600 text-xs mb-1">${s}</div>`).join("")}
          ${onlyA.map((s) => `<div class="text-red-600 text-xs mb-1 font-medium">${s}</div>`).join("")}
          ${!intA ? '<span class="text-gray-300 text-xs">--</span>' : ""}
        </td>
        <td class="py-3 align-top">
          ${common.map((s) => `<div class="text-gray-600 text-xs mb-1">${s}</div>`).join("")}
          ${onlyB.map((s) => `<div class="text-blue-600 text-xs mb-1 font-medium">${s}</div>`).join("")}
          ${!intB ? '<span class="text-gray-300 text-xs">--</span>' : ""}
        </td>
      </tr>
    `;
  });

  html += "</tbody></table></div>";
  html += `
    <div class="mt-3 flex gap-4 text-xs text-gray-500">
      <span><span class="inline-block w-3 h-3 bg-gray-200 rounded mr-1"></span> Shared items</span>
      <span><span class="inline-block w-3 h-3 bg-red-100 rounded mr-1"></span> Only in ${vehicleA.model}</span>
      <span><span class="inline-block w-3 h-3 bg-blue-100 rounded mr-1"></span> Only in ${vehicleB.model}</span>
    </div>
  `;

  container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatMiles(miles) {
  return miles.toLocaleString() + " mi";
}

function formatCondition(condition) {
  const labels = {
    dusty_roads: "Dusty Roads",
    towing: "Towing",
    heavy_loading: "Heavy Loading",
    short_trips_cold: "Short Trips / Cold",
    extensive_idling: "Extensive Idling",
    fleet_use: "Fleet Use",
  };
  return labels[condition] || condition;
}

function formatCategory(cat) {
  const labels = {
    standard: "Standard",
    inspection: "Inspect",
    special_condition: "Special",
  };
  return labels[cat] || cat;
}

// ---------------------------------------------------------------------------
// Event Listeners
// ---------------------------------------------------------------------------

function bindEvents() {
  // Filters
  $("#select-year").addEventListener("change", applyFilters);
  $("#select-model").addEventListener("change", applyFilters);
  $("#filter-category").addEventListener("change", applyFilters);

  // Debounced search
  let searchTimer;
  $("#search-service").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilters, 250);
  });

  // Compare mode
  $("#btn-compare").addEventListener("click", () => toggleCompare(true));
  $("#btn-close-compare").addEventListener("click", () => toggleCompare(false));
  $("#compare-a").addEventListener("change", renderComparison);
  $("#compare-b").addEventListener("change", renderComparison);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
  populateSelectors();
  bindEvents();
  await loadData();
  populateCompareDropdowns();
  renderVehicleCards();
}

document.addEventListener("DOMContentLoaded", init);
