// Automatically detect base path from current location
// Extract base path from current URL (e.g., /expenses or empty for root)
const pathParts = window.location.pathname.split('/').filter(p => p);
const basePath = pathParts.length > 0 && pathParts[0] === 'expenses' ? '/expenses' : '';
const API_BASE_URL = window.location.origin + basePath;
// DOM elements
const recordButton = document.getElementById('recordButton');
const stopButton = document.getElementById('stopButton');
const sendButton = document.getElementById('sendButton');
const recordingsList = document.getElementById('recordingsList');
const emailInput = document.getElementById('emailInput');
const processingIndicator = document.getElementById('processingIndicator');

// Report DOM elements
const recordReportButton = document.getElementById('recordReportButton');
const stopReportButton = document.getElementById('stopReportButton');
const sendReportCommand = document.getElementById('sendReportCommand');
const reportRecordingsList = document.getElementById('reportRecordingsList');
const reportProcessingIndicator = document.getElementById('reportProcessingIndicator');

// Toast elements
const expenseToast = document.getElementById('expenseToast');
const toastTitle = document.getElementById('toastTitle');
const toastMessage = document.getElementById('toastMessage');

// Recording variables
let recorder;
let recordedBlob;
let reportRecorder;
let reportRecordedBlob;

// Initialize Bootstrap toast
const toast = new bootstrap.Toast(expenseToast);

// Function to load categories from server
function loadCategories() {
    console.log("Starting category loading...");
    fetch(`${API_BASE_URL}/api/categories`)
                .then(response => {
            console.log("API Response:", response);
            return response.json();
        })
        .then(data => {
            console.log("Dane kategorii:", data);
            if (data.success && data.categories) {
                // Get all select elements that contain categories
                const categorySelects = [
                    document.getElementById('categoryFilter'),
                    document.getElementById('expenseCategory'),
                    document.getElementById('reportCategory')
                ];

                // For each select
                categorySelects.forEach(select => {
                    if (!select) return;

                    // Keep "All Categories" option or first option
                    const firstOption = select.options[0];

                    // Clear select
                    select.innerHTML = '';

                    // Add back first option
                    if (firstOption) {
                        select.appendChild(firstOption);
                    }

                    // Add each category as new option
                    data.categories.forEach(category => {
                        const option = document.createElement('option');
                        option.value = category;
                        option.textContent = category;
                        select.appendChild(option);
                    });
                });
            }
        })
        .catch(error => {
            console.error('Error loading categories:', error);
        });
}

// Show notification
function showNotification(title, message, success = true) {
    toastTitle.textContent = title;
    toastMessage.textContent = message;
    expenseToast.className = 'toast ' + (success ? 'bg-success text-white' : 'bg-danger text-white');
    toast.show();
}

// Initialize the expense recording functionality
function initExpenseRecording() {
    // Request microphone access
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function(stream) {
            recordButton.disabled = false;

            // Setup recorder
            recordButton.onclick = function() {
                recorder = new RecordRTC(stream, {
                    type: 'audio',
                    mimeType: 'audio/webm',
                    recorderType: RecordRTC.StereoAudioRecorder,
                    numberOfAudioChannels: 1
                });

                recorder.startRecording();

                // Update UI
                recordButton.disabled = true;
                stopButton.disabled = false;
                recordingsList.innerHTML = '';
                sendButton.disabled = true;
            };

            stopButton.onclick = function() {
                recorder.stopRecording(function() {
                    recordedBlob = recorder.getBlob();

                    // Create audio element for playback
                    const audioElement = document.createElement('audio');
                    audioElement.setAttribute('controls', '');
                    audioElement.src = URL.createObjectURL(recordedBlob);

                    // Add to recordings list
                    recordingsList.innerHTML = '';
                    recordingsList.appendChild(audioElement);

                    // Update UI
                    recordButton.disabled = false;
                    stopButton.disabled = true;
                    sendButton.disabled = false;
                });
            };

            // Send button handler
            sendButton.onclick = function() {
                if (!recordedBlob) {
                    showNotification('Error', 'No recording available. Please record your expense first.', false);
                    return;
                }

                // Show processing indicator
                processingIndicator.style.display = 'block';
                sendButton.disabled = true;

                // Create form data for API request
                const formData = new FormData();
                formData.append('file', recordedBlob, 'expense_recording.webm');

                if (emailInput.value) {
                    formData.append('email', emailInput.value);
                }

                // Send to the server
                fetch(`${API_BASE_URL}/api/process-audio`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    // Hide processing indicator
                    processingIndicator.style.display = 'none';

                    if (data.success) {
                        showNotification('Success', 'Your expense has been processed and saved!', true);

                        // Refresh categories after adding expense
                        loadCategories();

                        // Clear the recording
                        recordingsList.innerHTML = '';
                        recordedBlob = null;

                        // Load the expenses table if on that tab
                        if (document.getElementById('view-tab').getAttribute('aria-selected') === 'true') {
                            loadExpenses();
                        }
                    } else {
                        showNotification('Error', data.error || 'Failed to process the expense.', false);
                        sendButton.disabled = false;
                    }
                })
                .catch(error => {
                    processingIndicator.style.display = 'none';
                    showNotification('Error', 'Failed to connect to the server. Please try again.', false);
                    sendButton.disabled = false;
                    console.error('Error:', error);
                });
            };
        })
        .catch(function(err) {
            showNotification('Error', 'Microphone access is required for voice recording.', false);
            console.error('Error accessing microphone:', err);
        });
}

// Initialize the report recording functionality
function initReportRecording() {
    // Request microphone access
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function(stream) {
            recordReportButton.disabled = false;

            // Setup recorder
            recordReportButton.onclick = function() {
                reportRecorder = new RecordRTC(stream, {
                    type: 'audio',
                    mimeType: 'audio/webm',
                    recorderType: RecordRTC.StereoAudioRecorder,
                    numberOfAudioChannels: 1
                });

                reportRecorder.startRecording();

                // Update UI
                recordReportButton.disabled = true;
                stopReportButton.disabled = false;
                reportRecordingsList.innerHTML = '';
                sendReportCommand.disabled = true;
            };

            stopReportButton.onclick = function() {
                reportRecorder.stopRecording(function() {
                    reportRecordedBlob = reportRecorder.getBlob();

                    // Create audio element for playback
                    const audioElement = document.createElement('audio');
                    audioElement.setAttribute('controls', '');
                    audioElement.src = URL.createObjectURL(reportRecordedBlob);

                    // Add to recordings list
                    reportRecordingsList.innerHTML = '';
                    reportRecordingsList.appendChild(audioElement);

                    // Update UI
                    recordReportButton.disabled = false;
                    stopReportButton.disabled = true;
                    sendReportCommand.disabled = false;
                });
            };

            // Send report command handler
            sendReportCommand.onclick = function() {
                if (!reportRecordedBlob) {
                    showNotification('Error', 'No recording available. Please record your command first.', false);
                    return;
                }

                // Show processing indicator
                reportProcessingIndicator.style.display = 'block';
                sendReportCommand.disabled = true;

                // Create form data for API request
                const formData = new FormData();
                formData.append('file', reportRecordedBlob, 'report_command.webm');

                const reportEmail = document.getElementById('reportEmail').value;
                if (reportEmail) {
                    formData.append('email', reportEmail);
                }

                // Send to the server
                fetch(`${API_BASE_URL}/api/generate-report`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    // Hide processing indicator
                    reportProcessingIndicator.style.display = 'none';

                    if (data.success) {
                        showNotification('Success', 'Your report has been generated and will be sent to your email!', true);

                        // Clear the recording
                        reportRecordingsList.innerHTML = '';
                        reportRecordedBlob = null;
                    } else {
                        showNotification('Error', data.error || 'Failed to generate the report.', false);
                        sendReportCommand.disabled = false;
                    }
                })
                .catch(error => {
                    reportProcessingIndicator.style.display = 'none';
                    showNotification('Error', 'Failed to connect to the server. Please try again.', false);
                    sendReportCommand.disabled = false;
                    console.error('Error:', error);
                });
            };
        })
        .catch(function(err) {
            showNotification('Error', 'Microphone access is required for voice recording.', false);
            console.error('Error accessing microphone:', err);
        });
}

// Load expenses table
function loadExpenses(page = 1) {
    const tableBody = document.getElementById('expenseTableBody');
    const pagination = document.getElementById('expensePagination');
    const categoryFilter = document.getElementById('categoryFilter').value;

    // Show loading state
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center">Loading expenses...</td></tr>';

    // Fetch expenses from server
    let url = `${API_BASE_URL}/api/view-expenses?page=${page}&per_page=10`;
    if (categoryFilter) {
        url += `&category=${encodeURIComponent(categoryFilter)}`;
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.expenses && data.expenses.length > 0) {
                // Populate table
                tableBody.innerHTML = '';

                data.expenses.forEach(expense => {
                    const row = document.createElement('tr');

                    // Format date
                    const date = new Date(expense.date);
                    const formattedDate = date.toLocaleDateString();

                    row.innerHTML = `
                        <td>${formattedDate}</td>
                        <td>£${parseFloat(expense.amount).toFixed(2)}</td>
                        <td>${expense.vendor || 'Unknown'}</td>
                        <td>${expense.category || 'Other'}</td>
                        <td>${expense.description || ''}</td>
                    `;

                    tableBody.appendChild(row);
                });

                // Create pagination
                generatePagination(pagination, data.page, data.total_pages);
            } else {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center">No expenses found</td></tr>';
                pagination.innerHTML = '';
            }
        })
        .catch(error => {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error loading expenses</td></tr>';
            console.error('Error:', error);
        });
}

// Generate pagination links
function generatePagination(paginationElement, currentPage, totalPages) {
    paginationElement.innerHTML = '';

    // Previous button
    const prevItem = document.createElement('li');
    prevItem.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;

    const prevLink = document.createElement('a');
    prevLink.className = 'page-link';
    prevLink.href = '#';
    prevLink.textContent = 'Previous';

    if (currentPage > 1) {
        prevLink.onclick = function(e) {
            e.preventDefault();
            loadExpenses(currentPage - 1);
        };
    }

    prevItem.appendChild(prevLink);
    paginationElement.appendChild(prevItem);

    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, startPage + 4);

    for (let i = startPage; i <= endPage; i++) {
        const pageItem = document.createElement('li');
        pageItem.className = `page-item ${i === currentPage ? 'active' : ''}`;

        const pageLink = document.createElement('a');
        pageLink.className = 'page-link';
        pageLink.href = '#';
        pageLink.textContent = i;

        if (i !== currentPage) {
            pageLink.onclick = function(e) {
                e.preventDefault();
                loadExpenses(i);
            };
        }

        pageItem.appendChild(pageLink);
        paginationElement.appendChild(pageItem);
    }

    // Next button
    const nextItem = document.createElement('li');
    nextItem.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;

    const nextLink = document.createElement('a');
    nextLink.className = 'page-link';
    nextLink.href = '#';
    nextLink.textContent = 'Next';

    if (currentPage < totalPages) {
        nextLink.onclick = function(e) {
            e.preventDefault();
            loadExpenses(currentPage + 1);
        };
    }

    nextItem.appendChild(nextLink);
    paginationElement.appendChild(nextItem);
}

// Handle view tab activation
document.getElementById('view-tab').addEventListener('shown.bs.tab', function (e) {
    loadExpenses();
});

// Handle category filter change
document.getElementById('categoryFilter').addEventListener('change', function() {
    loadExpenses();
});

// Handle refresh button
document.getElementById('refreshExpenses').addEventListener('click', function() {
    loadExpenses();
});

// Handle report form submission
document.getElementById('reportForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const category = document.getElementById('reportCategory').value;
    const groupBy = document.getElementById('reportGroupBy').value;
    const startDate = document.getElementById('reportStartDate').value;
    const endDate = document.getElementById('reportEndDate').value;
    const format = document.getElementById('reportFormat').value;
    const email = document.getElementById('reportEmail').value.trim();

    // Create request data - email will use default if not provided
    const reportData = {
        category: category,
        group_by: groupBy,
        format: format,
        email: email
    };

    if (startDate) reportData.start_date = startDate;
    if (endDate) reportData.end_date = endDate;

    // Show processing notification
    showNotification('Processing', 'Generating your report. This may take a moment...', true);

    // Send to server
    fetch(`${API_BASE_URL}/api/generate-report`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(reportData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Success', 'Your report has been generated and will be sent to your email!', true);
        } else {
            showNotification('Error', data.error || 'Failed to generate the report.', false);
        }
    })
    .catch(error => {
        showNotification('Error', 'Failed to connect to the server. Please try again.', false);
        console.error('Error:', error);
    });
});

// Handle manual expense form submission
document.getElementById('manualExpenseForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const date = document.getElementById('expenseDate').value;
    const amount = document.getElementById('expenseAmount').value;
    const vendor = document.getElementById('expenseVendor').value;
    const category = document.getElementById('expenseCategory').value;
    const description = document.getElementById('expenseDescription').value;

    // Validate inputs
    if (!date || !amount) {
        showNotification('Error', 'Date and amount are required fields.', false);
        return;
    }

    // Create expense data
    const expenseData = {
        date: date,
        amount: parseFloat(amount),
        vendor: vendor,
        category: category,
        description: description
    };

    // Send to server
    fetch(`${API_BASE_URL}/api/process-manual-expense`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(expenseData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Success', 'Your expense has been saved!', true);

            // Refresh categories after adding expense
            loadCategories();

            // Reset form
            document.getElementById('manualExpenseForm').reset();

            // Load the expenses table if on that tab
            if (document.getElementById('view-tab').getAttribute('aria-selected') === 'true') {
                loadExpenses();
            }
        } else {
            showNotification('Error', data.error || 'Failed to save the expense.', false);
        }
    })
    .catch(error => {
        showNotification('Error', 'Failed to connect to the server. Please try again.', false);
        console.error('Error:', error);
    });
});

// Initialization when document loads
document.addEventListener('DOMContentLoaded', function() {
    loadCategories();
    initExpenseRecording();
    initReportRecording();
});