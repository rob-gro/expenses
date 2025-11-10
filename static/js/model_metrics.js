(function() {
// Automatically detect base path from current location
// Extract base path from current URL (e.g., /expenses or empty for root)
const pathParts = window.location.pathname.split('/').filter(p => p);
const basePath = pathParts.length > 0 && pathParts[0] === 'expenses' ? '/expenses' : '';
const API_BASE_URL = window.location.origin + basePath;

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

// Helper function to show notification toast
function showNotification(title, message, isSuccess) {
  // Simple console log for now - can be enhanced with Bootstrap toast
  if (isSuccess) {
    console.log(`✓ ${title}: ${message}`);
    alert(`${title}: ${message}`);
  } else {
    console.error(`✗ ${title}: ${message}`);
    alert(`Error - ${title}: ${message}`);
  }
}

// Function to train the model with progress indicator
function trainExpenseModel() {
  const trainButton = document.getElementById('trainModelButton');
  const progressDiv = document.getElementById('trainingProgress');
  const progressBar = document.getElementById('trainingProgressBar');
  const progressStatus = document.getElementById('trainingStatus');

  // Show progress indicator
  if (progressDiv) {
    progressDiv.classList.remove('d-none');
  }

  // Disable button
  if (trainButton) {
    trainButton.disabled = true;
    trainButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Training...';
  }

  // Reset progress
  updateProgress(0, 'Initializing training...');

  // Simulate training progress (since we don't have real backend progress tracking)
  let progress = 0;
  const progressInterval = setInterval(() => {
    progress += Math.random() * 15; // Random increment
    if (progress > 95) progress = 95; // Don't complete until real training finishes

    let status = 'Training model...';
    if (progress < 20) status = 'Loading training data...';
    else if (progress < 40) status = 'Preparing features...';
    else if (progress < 60) status = 'Training classifier...';
    else if (progress < 80) status = 'Validating model...';
    else status = 'Finalizing training...';

    updateProgress(Math.floor(progress), status);
  }, 800);

  // First, get current metrics count, THEN start training
  fetch(`${API_BASE_URL}/api/model-metrics`)
    .then(r => r.json())
    .then(initialData => {
      const initialMetricsCount = initialData.success && initialData.metrics ? initialData.metrics.length : 0;

      // NOW start training
      return fetch(`${API_BASE_URL}/api/train-expense-model`, {
        method: 'POST'
      })
      .then(response => response.json())
      .then(data => {
    if (data.success) {
      // Training started in background - keep progress bar going
      updateProgress(95, 'Training in progress (this may take 3-5 minutes)...');

      // Poll for completion every 5 seconds
      let pollCount = 0;
      const maxPolls = 80; // 80 * 5s = 6.5 minutes max

      const pollInterval = setInterval(() => {
        pollCount++;

        fetch(`${API_BASE_URL}/api/model-metrics`)
          .then(r => r.json())
          .then(metricsData => {
            const currentCount = metricsData.success && metricsData.metrics ? metricsData.metrics.length : 0;

            if (currentCount > initialMetricsCount) {
              // New training completed!
              clearInterval(progressInterval);
              clearInterval(pollInterval);
              updateProgress(100, 'Training completed successfully!');

              setTimeout(() => {
                loadModelMetrics();
                if (progressDiv) progressDiv.classList.add('d-none');
                if (trainButton) {
                  trainButton.disabled = false;
                  trainButton.innerHTML = 'Train Model';
                }
              }, 2000);
            } else if (pollCount >= maxPolls) {
              // Timeout
              clearInterval(progressInterval);
              clearInterval(pollInterval);
              updateProgress(95, 'Training timeout - check email for results');

              setTimeout(() => {
                if (progressDiv) progressDiv.classList.add('d-none');
                if (trainButton) {
                  trainButton.disabled = false;
                  trainButton.innerHTML = 'Train Model';
                }
              }, 5000);
            }
          })
          .catch(err => console.error('Polling error:', err));
      }, 5000); // Check every 5 seconds

    } else {
      clearInterval(progressInterval);
      updateProgress(0, 'Training failed');
      showNotification('Error', data.error || 'Failed to train model.', false);

      setTimeout(() => {
        if (progressDiv) progressDiv.classList.add('d-none');
        if (trainButton) {
          trainButton.disabled = false;
          trainButton.innerHTML = 'Train Model';
        }
      }, 3000);
    }
  });
    })
    .catch(error => {
      clearInterval(progressInterval);
      updateProgress(0, 'Training failed');
      showNotification('Error', 'Failed to connect to the server. Please try again.', false);
      console.error('Error:', error);

      setTimeout(() => {
        if (progressDiv) progressDiv.classList.add('d-none');
        if (trainButton) {
          trainButton.disabled = false;
          trainButton.innerHTML = 'Train Model';
        }
      }, 3000);
    });
}

// Helper function to update progress
function updateProgress(percentage, statusText) {
  const progressBar = document.getElementById('trainingProgressBar');
  const progressStatus = document.getElementById('trainingStatus');

  if (progressBar) {
    progressBar.style.width = percentage + '%';
    progressBar.textContent = percentage + '%';
  }

  if (progressStatus) {
    progressStatus.textContent = statusText;
  }
}

// Store chart instance globally within IIFE scope
let chartInstance = null;

// Funkcja do rysowania wykresu dokładności
function drawAccuracyChart(metrics) {
  const canvas = document.getElementById('accuracyChart');
  if (!canvas) {
    console.error('Canvas element not found');
    return;
  }

  // Destroy existing chart if it exists
  if (chartInstance) {
    chartInstance.destroy();
  }

  const ctx = canvas.getContext('2d');

  // Odwróć dane, aby były chronologicznie
  const sortedMetrics = [...metrics].reverse();

  chartInstance = new Chart(ctx, {
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
document.addEventListener('DOMContentLoaded', function() {
  loadModelMetrics();

  // Add training button handling
  const trainButton = document.getElementById('trainModelButton');
  if (trainButton) {
    trainButton.addEventListener('click', trainExpenseModel);
  }

  // Load metrics when Model Metrics tab is shown
  const metricsTab = document.getElementById('metrics-tab');
  if (metricsTab) {
    metricsTab.addEventListener('shown.bs.tab', function (e) {
      loadModelMetrics();
    });
  }
});

})(); // End of IIFE