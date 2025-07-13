document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chartForm");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const stockSelect = document.getElementById("stock");
    const selectedStocks = Array.from(stockSelect.selectedOptions).map(opt => opt.value);
    const startDate = document.getElementById("start_date").value;
    const endDate = document.getElementById("end_date").value;
    const type = document.getElementById("type").value;

    if (!selectedStocks.length || !startDate || !endDate || !type) {
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

      if (!res.ok) {
        document.getElementById("plotly-chart").innerHTML =
          `<div class="alert alert-danger mt-3">${json.error}</div>`;
        return;
      }

      const plotDiv = document.getElementById("plotly-chart");
      plotDiv.innerHTML = "";
      Plotly.purge(plotDiv);

      // Build annotation markers
      const annotations = [];
      if (json.suggestions && json.suggestions.length > 0) {
        json.suggestions.forEach(s => {
          if (s.action !== "Nothing") {
            let color, bgcolor, bordercolor, ay;
            if (s.action === "Long") {
              color = "#228B22"; // forest green
              bgcolor = "#e8ffe8";
              bordercolor = "#228B22";
              ay = -40;
            } else if (s.action === "Sell") {
              color = "#B22222"; // firebrick red
              bgcolor = "#ffe8e8";
              bordercolor = "#B22222";
              ay = 40;
            } else if (s.action === "Short") {
              color = "#800080"; // vivid purple
              bgcolor = "#f5e6ff";
              bordercolor = "#800080";
              ay = 40;
            } else {
              color = "black";
              bgcolor = "#f0f0f0";
              bordercolor = "gray";
              ay = 0;
            }
            let percentText = (s.percentage !== undefined) ? `<br>Change: ${s.percentage}%` : "";
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

      // Prepare entry/exit shapes for the plot
      let layout = {...json.plotly_figure.layout}; // shallow copy
      if (annotations.length > 0) {
        layout.annotations = annotations;
      }
      if (json.default_operation) {
        const entry = json.default_operation.first_operation_date || json.default_operation.first_operation_date;
        const exit = json.default_operation.last_operation_date;
        if (entry && exit) {
          layout.shapes = (layout.shapes || []).concat([
            {
              type: 'line',
              xref: 'x', yref: 'paper',
              x0: entry, x1: entry,
              y0: 0, y1: 1,
              line: {color: 'green', width: 2, dash: 'dash'},
            },
            {
              type: 'line',
              xref: 'x', yref: 'paper',
              x0: exit, x1: exit,
              y0: 0, y1: 1,
              line: {color: 'red', width: 2, dash: 'dot'},
            }
          ]);
        }
      }
console.log("Plotly data", json.plotly_figure.data);
console.log("Plotly layout", layout);
console.log("Suggestions", json.suggestions);
      // Draw main chart (with markers and shapes)
      Plotly.newPlot(plotDiv, json.plotly_figure.data, layout);

      // Render the operation summary table (finance-style)
      if (json.default_operation) {

        const op = json.default_operation;
        let rows = "";
        for (let key in op) {
          let label = key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
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
// Add the cumulative return column to the data
addCumulativeColumn(json.trade_table, 'pnl_percentage', 'cumulative_return');

// The rest is your generic table rendering (from earlier)
if (json.trade_table && json.trade_table.length > 0) {
  // 1. Dynamically gather all unique columns
  let columns = Object.keys(json.trade_table[0]);

  // 2. Move 'stock' to the first column, if present
  if (columns.includes("stock")) {
    columns = ["stock", ...columns.filter(col => col !== "stock")];
  }

  // 3. Generate header row
  let header = columns.map(col =>
    `<th>${col.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</th>`
  ).join("");

  // 4. Generate table body
  let rows = json.trade_table.map(trade => {
    return "<tr>" + columns.map(col =>
      `<td>${trade[col] !== undefined ? trade[col] : ""}</td>`
    ).join("") + "</tr>";
  }).join("");

  // 5. Render table
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
        `<div class="alert alert-danger mt-3">Chart load failed</div>`;
    }
  });
});


function addCumulativeColumn(data, percentageKey = 'pnl_percentage', newCol = 'cumulative_return') {
  let cumulative = 1;
  for (let i = 0; i < data.length; ++i) {
    // Get value as float (handle possible missing, e.g. "")
    let pctStr = data[i][percentageKey];
    let pct = pctStr ? parseFloat(pctStr.replace('%','')) / 100 : 1;
    cumulative *= pct;
    // Optional: format as percentage string with two decimals
    data[i][newCol] = (cumulative * 100).toFixed(2) + '%';
  }
}