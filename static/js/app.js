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
    const needsReview = document.getElementById('needsReviewFilter').checked;

    // Show loading state
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center">Loading expenses...</td></tr>';

    // Fetch expenses from server
    let url = `${API_BASE_URL}/api/view-expenses?page=${page}&per_page=10`;
    if (categoryFilter) {
        url += `&category=${encodeURIComponent(categoryFilter)}`;
    }
    if (needsReview) {
        url += `&needs_review=true`;
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

                    // Determine border color based on confidence score
                    let borderStyle = '';
                    if (expense.confidence_score !== null && expense.confidence_score !== undefined) {
                        if (expense.confidence_score >= 0.80) {
                            borderStyle = 'border-left: 4px solid #28a745;'; // Green
                        } else if (expense.confidence_score >= 0.60) {
                            borderStyle = 'border-left: 4px solid #ffc107;'; // Yellow
                        } else {
                            borderStyle = 'border-left: 4px solid #dc3545; animation: pulse 2s infinite;'; // Red + pulse
                        }
                    }

                    row.setAttribute('style', borderStyle);

                    row.innerHTML = `
                        <td>${formattedDate}</td>
                        <td>£${parseFloat(expense.amount).toFixed(2)}</td>
                        <td>${expense.vendor || 'Unknown'}</td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <select class="form-select form-select-sm category-select" data-expense-id="${expense.id}" data-original-category="${expense.category || 'Other'}" style="max-width: 150px;">
                                    <option value="${expense.category || 'Other'}" selected>${expense.category || 'Other'}</option>
                                </select>
                                <button class="btn btn-sm btn-success btn-save-category" data-expense-id="${expense.id}" style="display: none;" title="Save category">
                                    💾
                                </button>
                                ${expense.confidence_score !== null && expense.confidence_score < 0.70 ? `
                                    <button class="btn btn-sm btn-primary btn-confirm-category" data-expense-id="${expense.id}" data-category="${expense.category || 'Other'}" title="Confirm category is correct">
                                        ✓ Confirm
                                    </button>
                                ` : ''}
                            </div>
                        </td>
                        <td>${expense.description || ''}</td>
                    `;

                    tableBody.appendChild(row);
                });

                // Create pagination
                generatePagination(pagination, data.page, data.total_pages);

                // Populate category dropdowns after table is created
                populateCategorySelects();

                // Update badge
                const badge = document.getElementById('needs-review-badge');
                if (data.needs_review_count > 0) {
                    badge.textContent = data.needs_review_count;
                    badge.style.display = 'inline-block';
                } else {
                    badge.style.display = 'none';
                }
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

// Populate all category select dropdowns in expense table
function populateCategorySelects() {
    // Fetch categories
    fetch(`${API_BASE_URL}/api/categories`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.categories) {
                // Get all category select elements in the table
                const categorySelects = document.querySelectorAll('.category-select');

                categorySelects.forEach(select => {
                    const originalCategory = select.getAttribute('data-original-category');

                    // Clear and repopulate
                    select.innerHTML = '';

                    // Add all categories
                    data.categories.forEach(category => {
                        const option = document.createElement('option');
                        option.value = category;
                        option.textContent = category;

                        // Select the original category
                        if (category === originalCategory) {
                            option.selected = true;
                        }

                        select.appendChild(option);
                    });
                });

                // Event listeners are set up once in DOMContentLoaded, not here
            }
        })
        .catch(error => {
            console.error('Error loading categories for expense table:', error);
        });
}

// Setup event handlers for category changes (called ONCE on init)
function setupCategoryChangeHandlers() {
    // Use event delegation on table body
    const tableBody = document.getElementById('expenseTableBody');

    // Handle category select change
    tableBody.addEventListener('change', function(e) {
        if (e.target.classList.contains('category-select')) {
            const select = e.target;
            const expenseId = select.getAttribute('data-expense-id');
            const originalCategory = select.getAttribute('data-original-category');
            const newCategory = select.value;
            const saveButton = tableBody.querySelector(`.btn-save-category[data-expense-id="${expenseId}"]`);

            // Show/hide save button based on whether category changed
            if (newCategory !== originalCategory) {
                saveButton.style.display = 'inline-block';
            } else {
                saveButton.style.display = 'none';
            }
        }
    });

    // Handle save button click
    tableBody.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-save-category')) {
            const button = e.target;
            const expenseId = button.getAttribute('data-expense-id');
            const select = tableBody.querySelector(`.category-select[data-expense-id="${expenseId}"]`);
            const newCategory = select.value;

            // Disable button during save
            button.disabled = true;
            button.textContent = '⏳';

            // Call API to save category
            fetch(`${API_BASE_URL}/api/confirm-category`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expense_id: parseInt(expenseId),
                    category: newCategory
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Success', 'Category updated and model retrained!', true);

                    // Update original category attribute
                    select.setAttribute('data-original-category', newCategory);

                    // Hide save button
                    button.style.display = 'none';
                    button.textContent = '💾';
                    button.disabled = false;

                    // Refresh categories in case new one was added
                    loadCategories();
                } else {
                    showNotification('Error', data.error || 'Failed to update category.', false);
                    button.textContent = '💾';
                    button.disabled = false;
                }
            })
            .catch(error => {
                showNotification('Error', 'Failed to connect to the server. Please try again.', false);
                console.error('Error:', error);
                button.textContent = '💾';
                button.disabled = false;
            });
        }

        // Handle confirm button click
        if (e.target.classList.contains('btn-confirm-category')) {
            const button = e.target;
            const expenseId = button.getAttribute('data-expense-id');
            const category = button.getAttribute('data-category');

            // Disable button during confirmation
            button.disabled = true;
            button.textContent = '⏳';

            // Call API to confirm category
            fetch(`${API_BASE_URL}/api/confirm-category`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expense_id: parseInt(expenseId),
                    category: category  // Same category, just confirming
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Success', 'Category confirmed! Confidence set to 100%', true);

                    // Reload expenses to reflect changes (expense should disappear from filtered view)
                    loadExpenses();
                } else {
                    showNotification('Error', data.error || 'Failed to confirm category.', false);
                    button.textContent = '✓ Confirm';
                    button.disabled = false;
                }
            })
            .catch(error => {
                showNotification('Error', 'Failed to connect to the server. Please try again.', false);
                console.error('Error:', error);
                button.textContent = '✓ Confirm';
                button.disabled = false;
            });
        }
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

// Handle needs review filter change
document.getElementById('needsReviewFilter').addEventListener('change', function() {
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
    setupCategoryChangeHandlers();  // Set up event listeners ONCE on init
});