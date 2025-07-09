document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chartForm");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const stockSelect = document.getElementById("stock");
    const selectedStocks = Array.from(stockSelect.selectedOptions).map(opt => opt.value);
    const startDate = document.getElementById("start_date").value;
    const endDate = document.getElementById("end_date").value;
    const type = document.getElementById("type").value; // ✅ FIXED: grab actual value

    if (!selectedStocks.length || !startDate || !endDate || !type) {
      alert("Please select stock(s), chart type, and date range.");
      return;
    }

    const chartContainer = document.getElementById("chart");

    // Reset chart with loading state
    chartContainer.innerHTML = `
      <div id="plotly-chart" style="height: 500px; width: 100%;">
        <div class="text-muted text-center pt-3">⏳ Loading...</div>
      </div>
    `;

const avgDays = document.getElementById("avg_days").value;
const includeCurrent = document.getElementById("include_current").checked;

const query = new URLSearchParams({
  stock: selectedStocks.join(","),
  start: startDate,
  end: endDate,
  type: type
});

// Only send avg/include if avgDays is provided
if (avgDays) {
  query.set("avg", avgDays);
  query.set("include", includeCurrent ? "1" : "0");
}

    try {
      const res = await fetch(`/chart-data?${query.toString()}`);
      const json = await res.json();

      if (!res.ok) {
        document.getElementById("plotly-chart").innerHTML =
          `<div class="alert alert-danger mt-3">${json.error}</div>`;
        return;
      }

      const plotDiv = document.getElementById("plotly-chart");
plotDiv.innerHTML = "";
Plotly.purge(plotDiv);

// Draw main chart
Plotly.newPlot(plotDiv, json.plotly_figure.data, json.plotly_figure.layout);

// Add suggestion markers
if (json.suggestions && json.suggestions.length > 0) {
  const annotations = [];
  json.suggestions.forEach(s => {
    if (s.action !== "Nothing") {
      annotations.push({
        x: s.date,
        y: s.price,
        text: s.action,
        xref: 'x',
        yref: 'y',
        showarrow: true,
        arrowhead: 2,
        ax: 0,
        ay: s.action === "Buy" ? -40 : 40,
        bgcolor: s.action === "Buy" ? "#e8ffe8" : "#ffe8e8",
        font: { color: s.action === "Buy" ? "green" : "red", size: 13 },
        bordercolor: s.action === "Buy" ? "green" : "red",
        borderwidth: 1
      });
    }
  });
  Plotly.relayout(plotDiv, {annotations});
}


    } catch (err) {
      console.error("❌ Chart fetch failed:", err);
      document.getElementById("plotly-chart").innerHTML =
        `<div class="alert alert-danger mt-3">Chart load failed</div>`;
    }
  });
});
