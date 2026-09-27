const charts = []
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

const pad = n => ("0" + n).slice(-2)
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

function unix_to_timestamp(unix) {
  const date = new Date(unix * 1000)
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function unix_to_time(unix) {
  const date = new Date(unix * 1000)
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// "2026-09-27" -> "27 Sep"
function day_to_short(day) {
  const [, month, date] = day.split("-")
  return `${parseInt(date)} ${MONTHS[parseInt(month) - 1]}`
}

function format_uptime(seconds) {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor(seconds % 86400 / 3600)
  const m = Math.floor(seconds % 3600 / 60)
  if (d) return `${d}d ${h}h ${m}m`
  if (h) return `${h}h ${m}m`
  return `${m}m`
}

// Colours that depend on the current theme, re-read whenever it changes
function theme_colors() {
  return {
    text: css("--text-muted"),
    grid: css("--grid"),
    tooltip_bg: css("--bg-tooltip"),
    tooltip_text: css("--text"),
    border: css("--border"),
  }
}

function apply_theme(chart) {
  const c = theme_colors()
  chart.data.datasets.forEach(ds => {
    ds.borderColor = css(ds._color)
    ds.backgroundColor = css(ds._color)
  })
  chart.options.scales.x.ticks.color = c.text
  chart.options.scales.y.ticks.color = c.text
  chart.options.scales.y.grid.color = c.grid
  Object.assign(chart.options.plugins.tooltip, {
    backgroundColor: c.tooltip_bg,
    titleColor: c.tooltip_text,
    bodyColor: c.tooltip_text,
    borderColor: c.border,
  })
}

function build_legend(chart, name) {
  const legend = document.querySelector(`.legend[data-chart="${name}"]`)
  if (!legend) return

  chart.data.datasets.forEach((ds, i) => {
    const item = document.createElement("button")
    item.type = "button"
    item.className = "legend-item"
    item.style.setProperty("--swatch", `var(${ds._color})`)
    item.innerHTML = `<span class="swatch"></span>${ds.label}`
    item.addEventListener("click", () => {
      const visible = chart.isDatasetVisible(i)
      chart.setDatasetVisibility(i, !visible)
      item.classList.toggle("off", visible)
      chart.update()
    })
    legend.appendChild(item)
  })
}

function chart_maker(name, labels, series, data, { raw_labels = false } = {}) {
  const ticks = raw_labels ? labels.map(day_to_short) : labels.map(unix_to_time)
  const titles = raw_labels ? labels : labels.map(unix_to_timestamp)

  const chart = new Chart(document.getElementById(name), {
    type: "line",
    data: {
      labels: ticks,
      datasets: series.map(s => ({
        label: s.label,
        data: data[s.key],
        _color: s.color,
        borderWidth: 2,
        tension: .35,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBorderWidth: 0,
      }))
    },
    options: {
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: "index", intersect: false },
      layout: { padding: { top: 4 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          borderWidth: 1,
          padding: 10,
          cornerRadius: 4,
          boxPadding: 4,
          usePointStyle: true,
          titleFont: { weight: "600" },
          callbacks: {
            title: items => titles[items[0].dataIndex],
            label: item => ` ${item.dataset.label}: ${item.formattedValue} ms`,
          }
        }
      },
      scales: {
        x: {
          grid: { display: false, drawBorder: false },
          ticks: { maxTicksLimit: 8, maxRotation: 0, autoSkipPadding: 16 },
        },
        y: {
          beginAtZero: false,
          grid: { drawBorder: false },
          ticks: { maxTicksLimit: 5, padding: 8, callback: v => `${v} ms` },
        }
      }
    }
  })

  apply_theme(chart)
  chart.update("none")
  build_legend(chart, name)
  charts.push(chart)
}

Chart.defaults.font.family = "Figtree, sans-serif"
Chart.defaults.font.size = 12

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("year").textContent = new Date().getFullYear()

  document.querySelectorAll(".uptime").forEach(el => {
    const since = parseInt(el.dataset.since)
    el.title = unix_to_timestamp(since)
    const tick = () => { el.textContent = format_uptime(Date.now() / 1000 - since) }
    tick()
    setInterval(tick, 30000)
  })

  document.getElementById("theme_toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light"
    document.documentElement.dataset.theme = next
    try { localStorage.setItem("theme", next) } catch (e) {}
    charts.forEach(chart => { apply_theme(chart); chart.update("none") })
  })
})
