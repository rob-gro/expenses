const API_BASE_URL = 'http://localhost:5000';

// Funkcja do ładowania i wyświetlania metryk modelu
function loadModelMetrics() {
  fetch(`${API_BASE_URL}/api/model-metrics`)
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Aktualizacja bieżącej dokładności
        document.getElementById('currentAccuracy').textContent =
          `${(data.current_accuracy * 100).toFixed(2)}%`;

        // Wypełnienie tabeli historią
        const tableBody = document.getElementById('metricsTableBody');
        tableBody.innerHTML = '';

        data.metrics.forEach(metric => {
          const row = document.createElement('tr');
          row.innerHTML = `
            <td>${new Date(metric.timestamp).toLocaleString()}</td>
            <td>${(metric.accuracy * 100).toFixed(2)}%</td>
            <td>${metric.samples_count}</td>
            <td>${metric.categories_count}</td>
            <td>${metric.training_type}</td>
            <td>${metric.notes || ''}</td>
          `;
          tableBody.appendChild(row);
        });

        // Rysowanie wykresu trendu
        drawAccuracyChart(data.metrics);
      }
    })
    .catch(error => console.error('Error loading model metrics:', error));
}

// Funkcja do rysowania wykresu dokładności
function drawAccuracyChart(metrics) {
  const ctx = document.getElementById('accuracyChart').getContext('2d');

  // Odwróć dane, aby były chronologicznie
  const sortedMetrics = [...metrics].reverse();

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: sortedMetrics.map(m => new Date(m.timestamp).toLocaleDateString()),
      datasets: [{
        label: 'Model Accuracy',
        data: sortedMetrics.map(m => m.accuracy * 100),
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1,
        fill: false
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          min: 0,
          max: 100,
          title: {
            display: true,
            text: 'Accuracy (%)'
          }
        },
        x: {
          title: {
            display: true,
            text: 'Training Date'
          }
        }
      }
    }
  });
}

// Ładuj metryki przy starcie strony
document.addEventListener('DOMContentLoaded', loadModelMetrics);