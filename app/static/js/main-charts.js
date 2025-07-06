document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chartForm");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const stock = document.getElementById("stock").value;
    const type = document.getElementById("type").value;
    const chartContainer = document.getElementById("chart");

    // Always reset container
    chartContainer.innerHTML = '<div id="plotly-chart" style="height: 500px;">⏳ Loading...</div>';

    try {
      const res = await fetch(`/chart-data?stock=${encodeURIComponent(stock)}&type=${type}`);
      const json = await res.json();

      if (!res.ok) {
        document.getElementById("plotly-chart").innerHTML =
          `<div class="alert alert-danger mt-3">${json.error}</div>`;
        return;
      }

      // Log the actual data you're plotting
      console.log("🔍 Plotly chart data:", json.data);

      // Remove any previous plot
      Plotly.purge("plotly-chart");

      // Now safely render new chart
      Plotly.newPlot("plotly-chart", json.data, {
        ...json.layout,
        autosize: true,
        margin: { t: 50 },
        xaxis: { title: "Date" },
        yaxis: { title: "Price" }
      });

    } catch (err) {
      console.error("❌ Chart fetch failed:", err);
      document.getElementById("plotly-chart").innerHTML =
        `<div class="alert alert-danger mt-3">Chart load failed</div>`;
    }
  });
});