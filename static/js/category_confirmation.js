// Get expense ID and suggested category from URL
const urlParams = new URL(window.location.href).pathname.split('/');
const expenseId = urlParams[urlParams.length - 2];
const suggestedCategory = urlParams[urlParams.length - 1];

// Function to load expense details
async function loadExpenseDetails() {
    try {
        const response = await fetch(`/api/get-expense-details/${expenseId}`);
        const data = await response.json();

        if (data.error) {
            document.getElementById('expenseDetails').innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
            return;
        }

        // Display expense details
        const expense = data.expense;
        const date = new Date(expense.date).toLocaleDateString();

        document.getElementById('expenseDetails').innerHTML = `
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">Expense Details</h5>
                    <p><strong>Date:</strong> ${date}</p>
                    <p><strong>Amount:</strong> £${parseFloat(expense.amount).toFixed(2)}</p>
                    <p><strong>Vendor:</strong> ${expense.vendor || 'Not specified'}</p>
                    <p><strong>Current Category:</strong> ${expense.category}</p>
                    <p><strong>Description:</strong> ${expense.description || 'None'}</p>
                </div>
            </div>
        `;

        // Load category options
        const categoryOptions = document.getElementById('categoryOptions');
        categoryOptions.innerHTML = '';

        data.available_categories.forEach(category => {
            const isActive = category === suggestedCategory;

            const item = document.createElement('button');
            item.type = 'button';
            item.className = `list-group-item list-group-item-action ${isActive ? 'active' : ''}`;
            item.textContent = category;

            item.addEventListener('click', () => confirmCategory(category));

            categoryOptions.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading expense details:', error);
        document.getElementById('expenseDetails').innerHTML = '<div class="alert alert-danger">Error loading expense details.</div>';
    }
}

// Function to confirm category
async function confirmCategory(category) {
    try {
        const response = await fetch('/api/confirm-category', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                expense_id: expenseId,
                category: category
            })
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('successMessage').style.display = 'block';
            document.getElementById('errorMessage').style.display = 'none';

            // Redirect after 3 seconds
            setTimeout(() => {
                window.location.href = '/';
            }, 3000);
        } else {
            document.getElementById('errorMessage').textContent = data.error || 'An error occurred while confirming the category.';
            document.getElementById('errorMessage').style.display = 'block';
            document.getElementById('successMessage').style.display = 'none';
        }
    } catch (error) {
        console.error('Error confirming category:', error);
        document.getElementById('errorMessage').textContent = 'Server connection error.';
        document.getElementById('errorMessage').style.display = 'block';
        document.getElementById('successMessage').style.display = 'none';
    }
}

// Initialize event listeners
function initCategoryConfirmation() {
    // Custom category button handler
    document.getElementById('confirmCustomBtn').addEventListener('click', () => {
        const customCategory = document.getElementById('customCategory').value.trim();

        if (customCategory) {
            confirmCategory(customCategory);
        } else {
            alert('Please enter a category name.');
        }
    });

    // Load details when page loads
    loadExpenseDetails();
}

// Initialize when DOM is fully loaded
document.addEventListener('DOMContentLoaded', initCategoryConfirmation);