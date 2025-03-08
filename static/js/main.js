function unix_to_timestamp(unix) {
  let date = new Date(unix * 1000)
  let months_arr = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ]

  let day = ("0" + date.getDate()).slice(-2)
  let month = ("0" + (date.getMonth() + 1)).slice(-2)
  let year = date.getFullYear()

  let hours = ("0" + date.getHours()).slice(-2)
  let minutes = ("0" + date.getMinutes()).slice(-2)
  let seconds = ("0" + date.getSeconds()).slice(-2)

  const converted_date = `${day}/${month}/${year} ${hours}:${minutes}`
  return converted_date
}

function chart_maker(name, labels, data, {beginAtZero=true} = {}) {
  const ctx = document.getElementById(name).getContext('2d')
  let datasets = []
  let timestamps = []

  data.forEach(e => {
    datasets.push({
      label: e.label, data: e.data,
      borderColor: e.color, tension: .5
    })
  })

  labels.forEach(e => {
    timestamps.push(unix_to_timestamp(e))
  })

  const lines_go_brrr = new Chart(ctx, {
    type: 'line',
    data: { labels: timestamps, datasets: datasets },
    options: {
      elements: {
        point: {
          radius: 1,
          pointHitRadius: 5,
        },
        line: {
          borderWidth: 5,
          borderColor: "transparent"
        }
      },
      scales: {
        y: {
          ticks: { color: "#ccc" },
          beginAtZero: beginAtZero,
        },
        x: {
          ticks: { display: false },
          grid: { display: false }
        },
      }
    }
  })
}

document.addEventListener('DOMContentLoaded', function() {
  let timestamps = document.getElementsByClassName("timestamp")
  for (var i = 0; i < timestamps.length; i++) {
    let converted_date = unix_to_timestamp(timestamps[i].innerText)
    timestamps[i].innerText = converted_date
  }
})
