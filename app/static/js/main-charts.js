document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chartForm");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const stockSelect = document.getElementById("stock");
    const selectedStocks = Array.from(stockSelect.selectedOptions).map(opt => opt.value);
    const startDate = document.getElementById("start_date").value;
    const endDate = document.getElementById("end_date").value;
    const type = document.getElementById("type").value;

    if (!selectedStocks.length || /*!startDate || !endDate ||*/ !type) {
      alert("Please select stock(s), chart type, and date range.");
      return;
    }

    const chartContainer = document.getElementById("chart");
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

    if (avgDays) {
      query.set("avg", avgDays);
      query.set("include", includeCurrent ? "1" : "0");
    }

    try {
      const res = await fetch(`/chart-data?${query.toString()}`);
      const json = await res.json();

      if (!res.ok || !json.plotly_figure) {
        throw new Error(json.error || "Server returned no chart data");
      }

      const plotDiv = document.getElementById("plotly-chart");
      plotDiv.innerHTML = "";
      Plotly.purge(plotDiv);

      const annotations = [];
      if (Array.isArray(json.suggestions)) {
        json.suggestions.forEach(s => {
          if (s.action !== "Nothing") {
            let color, bgcolor, bordercolor, ay;
            if (s.action === "Long") {
              color = "#228B22";
              bgcolor = "#e8ffe8";
              bordercolor = "#228B22";
              ay = -40;
            } else if (s.action === "Sell") {
              color = "#B22222";
              bgcolor = "#ffe8e8";
              bordercolor = "#B22222";
              ay = 40;
            } else if (s.action === "Short") {
              color = "#800080";
              bgcolor = "#f5e6ff";
              bordercolor = "#800080";
              ay = 40;
            } else {
              color = "black";
              bgcolor = "#f0f0f0";
              bordercolor = "gray";
              ay = 0;
            }

            const percentText = s.percentage !== undefined ? `<br>Change: ${s.percentage}%` : "";
            annotations.push({
              x: s.date,
              y: s.price,
              text: s.action,
              hovertext: `Price: ${s.price}<br>Avg: ${s.avg}${percentText}`,
              hoverlabel: {
                bgcolor: bgcolor,
                font: { color: color }
              },
              xref: 'x',
              yref: 'y',
              showarrow: true,
              arrowhead: 2,
              ax: 0,
              ay: ay,
              bgcolor: bgcolor,
              font: { color: color, size: 13 },
              bordercolor: bordercolor,
              borderwidth: 1
            });
          }
        });
      }

      let layout = { ...json.plotly_figure.layout };
      if (annotations.length > 0) layout.annotations = annotations;

      if (json.default_operation) {
        const entry = json.default_operation.first_operation_date;
        const exit = json.default_operation.last_operation_date;
        if (entry && exit) {
          layout.shapes = (layout.shapes || []).concat([
            {
              type: 'line',
              xref: 'x', yref: 'paper',
              x0: entry, x1: entry,
              y0: 0, y1: 1,
              line: { color: 'green', width: 2, dash: 'dash' },
            },
            {
              type: 'line',
              xref: 'x', yref: 'paper',
              x0: exit, x1: exit,
              y0: 0, y1: 1,
              line: { color: 'red', width: 2, dash: 'dot' },
            }
          ]);
        }
      }

      console.log("Plotly data", json.plotly_figure.data);
      console.log("Plotly layout", layout);
      console.log("Suggestions", json.suggestions);

      Plotly.newPlot(plotDiv, json.plotly_figure.data, layout);

      // Operation Summary
      if (json.default_operation) {
        const op = json.default_operation;
        let rows = "";
        for (let key in op) {
          const label = key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
          rows += `<tr><th>${label}</th><td>${op[key]}</td></tr>`;
        }
        document.getElementById("default-operation-summary-table").innerHTML = `
          <h5>Default Operation Summary</h5>
          <table class="table table-bordered table-striped">
            <tbody>${rows}</tbody>
          </table>
        `;
      } else {
        document.getElementById("default-operation-summary-table").innerHTML = "";
      }

      // ✅ Fix: only run if trade_table exists
      if (Array.isArray(json.trade_table)&& json.trade_table.length > 0) {
        addCumulativeColumn(json.trade_table, 'pnl_percentage', 'cumulative_return');

        const columns = Object.keys(json.trade_table[0]);
        if (columns.includes("stock")) {
          columns.unshift(...columns.splice(columns.indexOf("stock"), 1));
        }

        const header = columns.map(col =>
          `<th>${col.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</th>`
        ).join("");

        const rows = json.trade_table.map(trade =>
          `<tr>${columns.map(col => `<td>${trade[col] !== undefined ? trade[col] : ""}</td>`).join("")}</tr>`
        ).join("");

        document.getElementById("trade-table").innerHTML = `
          <h5>Trade Analysis Table</h5>
          <table class="table table-bordered table-striped">
            <thead><tr>${header}</tr></thead>
            <tbody>${rows}</tbody>
          </table>
        `;
      } else {
        document.getElementById("trade-table").innerHTML = "";
      }

    } catch (err) {
      console.error("❌ Chart fetch failed:", err);
      document.getElementById("plotly-chart").innerHTML =
        `<div class="alert alert-danger mt-3">Chart load failed: ${err.message}</div>`;
    }
  });
});

function addCumulativeColumn(data, percentageKey = 'pnl_percentage', newCol = 'cumulative_return') {
  if (!Array.isArray(data)) {
    console.warn("⚠️ addCumulativeColumn skipped: data is not an array");
    return;
  }
  let cumulative = 1;
  for (let i = 0; i < data.length; ++i) {
    const pctStr = data[i][percentageKey];
    const pct = pctStr ? parseFloat(pctStr.replace('%', '')) / 100 : 1;
    cumulative *= pct;
    data[i][newCol] = (cumulative * 100).toFixed(2) + '%';
  }
}
