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

// Helper function to determine badge color class based on confidence
function getConfidenceBadgeClass(confidence) {
    if (confidence >= 0.80) {
        return 'bg-success';  // Green for high confidence
    } else if (confidence >= 0.60) {
        return 'bg-warning';  // Yellow for medium confidence
    } else {
        return 'bg-danger';   // Red for low confidence
    }
}

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
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center">Loading expenses...</td></tr>';

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
                    row.setAttribute('data-expense-id', expense.id);
                    row.setAttribute('data-mode', 'view');
                    row.setAttribute('data-original-date', expense.date.split('T')[0]);
                    row.setAttribute('data-original-amount', expense.amount);
                    row.setAttribute('data-original-vendor', expense.vendor || '');
                    row.setAttribute('data-original-description', expense.description || '');

                    row.innerHTML = `
                        <td class="expense-date">
                            <span class="date-display">${formattedDate}</span>
                            <input type="date" class="form-control form-control-sm date-edit" value="${expense.date.split('T')[0]}" style="display: none;">
                        </td>
                        <td class="expense-amount">
                            <span class="amount-display">£${parseFloat(expense.amount).toFixed(2)}</span>
                            <input type="number" step="0.01" class="form-control form-control-sm amount-edit" value="${expense.amount}" style="display: none; max-width: 100px;">
                        </td>
                        <td class="expense-vendor">
                            <span class="vendor-display">${expense.vendor || 'Unknown'}</span>
                            <input type="text" class="form-control form-control-sm vendor-edit" value="${expense.vendor || ''}" style="display: none;">
                        </td>
                        <td class="expense-description">
                            <span class="description-display">${expense.description || ''}</span>
                            <textarea class="form-control form-control-sm description-edit" rows="1" style="display: none;">${expense.description || ''}</textarea>
                        </td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <select class="form-select form-select-sm category-select" data-expense-id="${expense.id}" data-original-category="${expense.category || 'Other'}" style="max-width: 150px;">
                                    <option value="${expense.category || 'Other'}" selected>${expense.category || 'Other'}</option>
                                </select>
                                ${expense.confidence_score !== null && expense.confidence_score !== undefined ? `
                                    <span class="badge ${getConfidenceBadgeClass(expense.confidence_score)}" title="Model confidence score">
                                        ${Math.round(expense.confidence_score * 100)}%
                                    </span>
                                ` : ''}
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
                        <td class="expense-actions">
                            <button class="btn btn-sm btn-outline-secondary btn-edit-expense" data-expense-id="${expense.id}" title="Edit expense">
                                ✏️
                            </button>
                            <button class="btn btn-sm btn-outline-danger btn-delete-expense" data-expense-id="${expense.id}" title="Delete expense">
                                🗑️
                            </button>
                            <button class="btn btn-sm btn-success btn-save-all" data-expense-id="${expense.id}" style="display: none;" title="Save all changes">
                                💾 Save
                            </button>
                            <button class="btn btn-sm btn-outline-danger btn-cancel-edit" data-expense-id="${expense.id}" style="display: none;" title="Cancel editing">
                                ❌
                            </button>
                        </td>
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
                tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No expenses found</td></tr>';
                pagination.innerHTML = '';
            }
        })
        .catch(error => {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error loading expenses</td></tr>';
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

        // Handle Delete button - delete expense with confirmation
        if (e.target.classList.contains('btn-delete-expense')) {
            const button = e.target;
            const expenseId = button.getAttribute('data-expense-id');
            const row = tableBody.querySelector(`tr[data-expense-id="${expenseId}"]`);

            // Get expense details for confirmation
            const date = row.querySelector('.date-display').textContent;
            const amount = row.querySelector('.amount-display').textContent;
            const vendor = row.querySelector('.vendor-display').textContent;

            // Confirm deletion
            if (!confirm(`Delete expense?\n\nDate: ${date}\nAmount: ${amount}\nVendor: ${vendor}\n\nThis action cannot be undone.`)) {
                return;
            }

            // Disable button during delete
            button.disabled = true;
            button.textContent = '⏳';

            // Call API
            fetch(`${API_BASE_URL}/api/delete-expense`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    expense_id: parseInt(expenseId)
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Success', 'Expense deleted successfully!', true);

                    // Reload expenses to show updated list
                    loadExpenses();
                } else {
                    showNotification('Error', data.error || 'Failed to delete expense.', false);
                    button.disabled = false;
                    button.textContent = '🗑️';
                }
            })
            .catch(error => {
                showNotification('Error', 'Failed to connect to the server.', false);
                console.error('Error:', error);
                button.disabled = false;
                button.textContent = '🗑️';
            });
        }

        // Handle Edit button - switch to edit mode
        if (e.target.classList.contains('btn-edit-expense')) {
            const button = e.target;
            const expenseId = button.getAttribute('data-expense-id');
            const row = tableBody.querySelector(`tr[data-expense-id="${expenseId}"]`);

            switchToEditMode(row);
        }

        // Handle Cancel button - revert changes
        if (e.target.classList.contains('btn-cancel-edit')) {
            const button = e.target;
            const expenseId = button.getAttribute('data-expense-id');
            const row = tableBody.querySelector(`tr[data-expense-id="${expenseId}"]`);

            switchToViewMode(row);
        }

        // Handle Save All button - update entire expense
        if (e.target.classList.contains('btn-save-all')) {
            const button = e.target;
            const expenseId = button.getAttribute('data-expense-id');
            const row = tableBody.querySelector(`tr[data-expense-id="${expenseId}"]`);

            // Gather all edited values
            const updatedData = {
                expense_id: parseInt(expenseId),
                date: row.querySelector('.date-edit').value,
                amount: parseFloat(row.querySelector('.amount-edit').value),
                vendor: row.querySelector('.vendor-edit').value,
                description: row.querySelector('.description-edit').value,
                category: row.querySelector('.category-select').value
            };

            // Validate
            if (!updatedData.date || !updatedData.amount || updatedData.amount <= 0) {
                showNotification('Error', 'Date and valid amount are required', false);
                return;
            }

            // Disable buttons during save
            button.disabled = true;
            button.textContent = '⏳ Saving...';

            // Call API
            fetch(`${API_BASE_URL}/api/update-expense`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Success', 'Expense updated successfully!', true);

                    // Reload expenses to show updated data
                    loadExpenses();
                } else {
                    showNotification('Error', data.error || 'Failed to update expense.', false);
                    button.disabled = false;
                    button.textContent = '💾 Save';
                }
            })
            .catch(error => {
                showNotification('Error', 'Failed to connect to the server.', false);
                console.error('Error:', error);
                button.disabled = false;
                button.textContent = '💾 Save';
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

// Helper: Switch row to edit mode
function switchToEditMode(row) {
    row.setAttribute('data-mode', 'edit');

    // Hide display spans, show input fields
    row.querySelectorAll('.date-display, .amount-display, .vendor-display, .description-display').forEach(el => {
        el.style.display = 'none';
    });
    row.querySelectorAll('.date-edit, .amount-edit, .vendor-edit, .description-edit').forEach(el => {
        el.style.display = 'inline-block';
    });

    // Hide Edit button, show Save/Cancel
    row.querySelector('.btn-edit-expense').style.display = 'none';
    row.querySelector('.btn-save-all').style.display = 'inline-block';
    row.querySelector('.btn-cancel-edit').style.display = 'inline-block';

    // Hide Confirm button during edit (if exists)
    const confirmBtn = row.querySelector('.btn-confirm-category');
    if (confirmBtn) {
        confirmBtn.style.display = 'none';
    }
}

// Helper: Switch row to view mode
function switchToViewMode(row) {
    row.setAttribute('data-mode', 'view');

    // Revert to original values
    const originalDate = row.getAttribute('data-original-date');
    const originalAmount = row.getAttribute('data-original-amount');
    const originalVendor = row.getAttribute('data-original-vendor');
    const originalDescription = row.getAttribute('data-original-description');
    const originalCategory = row.querySelector('.category-select').getAttribute('data-original-category');

    row.querySelector('.date-edit').value = originalDate;
    row.querySelector('.amount-edit').value = originalAmount;
    row.querySelector('.vendor-edit').value = originalVendor;
    row.querySelector('.description-edit').value = originalDescription;
    row.querySelector('.category-select').value = originalCategory;

    // Show display spans, hide input fields
    row.querySelectorAll('.date-display, .amount-display, .vendor-display, .description-display').forEach(el => {
        el.style.display = 'inline-block';
    });
    row.querySelectorAll('.date-edit, .amount-edit, .vendor-edit, .description-edit').forEach(el => {
        el.style.display = 'none';
    });

    // Show Edit button, hide Save/Cancel
    row.querySelector('.btn-edit-expense').style.display = 'inline-block';
    row.querySelector('.btn-save-all').style.display = 'none';
    row.querySelector('.btn-cancel-edit').style.display = 'none';

    // Show Confirm button again (if exists)
    const confirmBtn = row.querySelector('.btn-confirm-category');
    if (confirmBtn) {
        confirmBtn.style.display = 'inline-block';
    }
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

// Load needs review count for badge
function loadNeedsReviewCount() {
    // Fetch just the count without loading full table
    fetch(`${API_BASE_URL}/api/view-expenses?page=1&per_page=1`)
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('needs-review-badge');
            if (data.needs_review_count > 0) {
                badge.textContent = data.needs_review_count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error loading needs review count:', error);
        });
}

// Initialization when document loads
document.addEventListener('DOMContentLoaded', function() {
    loadCategories();
    loadNeedsReviewCount();  // Load badge count immediately
    initExpenseRecording();
    initReportRecording();
    setupCategoryChangeHandlers();  // Set up event listeners ONCE on init
});