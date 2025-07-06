document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chartForm");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const stock = document.getElementById("stock").value;
    const type = document.getElementById("type").value;
    const chartContainer = document.getElementById("chart");

    // Reset the chart container and show loading state
    chartContainer.innerHTML = `
      <div id="plotly-chart" style="height: 500px; width: 100%;">
        <div class="text-muted text-center pt-3">⏳ Loading...</div>
      </div>
    `;

    try {
      const res = await fetch(`/chart-data?stock=${encodeURIComponent(stock)}&type=${type}`);
      const json = await res.json();

      if (!res.ok) {
        document.getElementById("plotly-chart").innerHTML =
          `<div class="alert alert-danger mt-3">${json.error}</div>`;
        return;
      }

      // Confirm container is clean and targetable
      const plotDiv = document.getElementById("plotly-chart");

      // ✅ Clear any loading message
      plotDiv.innerHTML = "";

      // ✅ Optional: ensure no lingering old plot
      Plotly.purge(plotDiv);

      // ✅ Render the new chart
      Plotly.newPlot(plotDiv, json.data, {
        ...json.layout,
        autosize: true,
        margin: { t: 50 },
        // xaxis: {
        //   title: "Date",
        //   type: "date",
        //   rangeslider: type === "candlestick" ? { visible: true } : undefined
        // },
        xaxis: {
  title: "Date",
  type: "category",  // ← change "date" to "category" for string-based x-axis
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