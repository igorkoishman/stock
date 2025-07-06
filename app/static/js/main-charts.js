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

    const query = new URLSearchParams({
      stock: selectedStocks.join(","),
      start: startDate,
      end: endDate,
      type: type
    });

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

      Plotly.newPlot(plotDiv, json.data, {
        ...json.layout,
        autosize: true,
        margin: { t: 50 },
        xaxis: {
          title: "Date",
          type: "category",
          rangeslider: type === "candlestick" ? { visible: true } : undefined
        },
        yaxis: {
          title: "Price"
        }
      });

    } catch (err) {
      console.error("❌ Chart fetch failed:", err);
      document.getElementById("plotly-chart").innerHTML =
        `<div class="alert alert-danger mt-3">Chart load failed</div>`;
    }
  });
});
