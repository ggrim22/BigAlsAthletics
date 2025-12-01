class OrderEditMode {
    constructor() {
        this.editMode = false;
        this.selectedOrders = new Set();
        this.init();
        this.createModals();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupEventListeners());
        } else {
            this.setupEventListeners();
        }
    }

    createModals() {
        // Create delete confirmation modal
        const deleteModal = document.createElement('div');
        deleteModal.id = 'deleteConfirmModal';
        deleteModal.className = 'fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-[100]';
        deleteModal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
                <div class="p-6">
                    <div class="flex items-center gap-4 mb-4">
                        <div class="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                        </div>
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900">Delete Orders</h3>
                            <p class="text-sm text-gray-500 mt-1">This action cannot be undone</p>
                        </div>
                    </div>
                    <p class="text-gray-700 mb-6">
                        Are you sure you want to delete <span class="font-semibold delete-count">0</span> order(s)?
                    </p>
                    <div class="flex gap-3 justify-end">
                        <button id="cancelDelete" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium">
                            Cancel
                        </button>
                        <button id="confirmDelete" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-medium">
                            Delete Orders
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(deleteModal);

        // Create archive confirmation modal
        const archiveModal = document.createElement('div');
        archiveModal.id = 'archiveConfirmModal';
        archiveModal.className = 'fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-[100]';
        archiveModal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
                <div class="p-6">
                    <div class="flex items-center gap-4 mb-4">
                        <div class="flex-shrink-0 w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                            </svg>
                        </div>
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900">Archive Orders</h3>
                            <p class="text-sm text-gray-500 mt-1">Orders can be restored later</p>
                        </div>
                    </div>
                    <p class="text-gray-700 mb-6">
                        Are you sure you want to archive <span class="font-semibold archive-count">0</span> order(s)?
                    </p>
                    <div class="flex gap-3 justify-end">
                        <button id="cancelArchive" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium">
                            Cancel
                        </button>
                        <button id="confirmArchive" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium">
                            Archive Orders
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(archiveModal);

        // Setup modal event listeners
        this.setupModalListeners();
    }

    setupModalListeners() {
        // Delete modal
        const deleteModal = document.getElementById('deleteConfirmModal');
        const cancelDelete = document.getElementById('cancelDelete');
        const confirmDelete = document.getElementById('confirmDelete');

        if (cancelDelete) {
            cancelDelete.addEventListener('click', () => this.hideModal('deleteConfirmModal'));
        }
        if (confirmDelete) {
            confirmDelete.addEventListener('click', () => this.executeDelete());
        }
        if (deleteModal) {
            deleteModal.addEventListener('click', (e) => {
                if (e.target === deleteModal) this.hideModal('deleteConfirmModal');
            });
        }

        // Archive modal
        const archiveModal = document.getElementById('archiveConfirmModal');
        const cancelArchive = document.getElementById('cancelArchive');
        const confirmArchive = document.getElementById('confirmArchive');

        if (cancelArchive) {
            cancelArchive.addEventListener('click', () => this.hideModal('archiveConfirmModal'));
        }
        if (confirmArchive) {
            confirmArchive.addEventListener('click', () => this.executeArchive());
        }
        if (archiveModal) {
            archiveModal.addEventListener('click', (e) => {
                if (e.target === archiveModal) this.hideModal('archiveConfirmModal');
            });
        }

        // ESC key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideModal('deleteConfirmModal');
                this.hideModal('archiveConfirmModal');
            }
        });
    }

    showModal(modalId, count) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        // Update count in modal
        const countSpan = modal.querySelector(modalId === 'deleteConfirmModal' ? '.delete-count' : '.archive-count');
        if (countSpan) {
            countSpan.textContent = count;
        }

        modal.classList.remove('hidden');
        modal.classList.add('flex');
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }

    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        modal.classList.add('hidden');
        modal.classList.remove('flex');
        // Restore body scroll
        document.body.style.overflow = '';
    }

    setupEventListeners() {
        // Edit mode toggle - only setup once, don't clone this one
        const editModeToggle = document.getElementById('editModeToggle');
        if (editModeToggle && !editModeToggle.dataset.listenerAttached) {
            editModeToggle.addEventListener('change', (e) => this.toggleEditMode(e.target.checked));
            editModeToggle.dataset.listenerAttached = 'true';
        }

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('selectAllOrders');
        if (selectAllCheckbox) {
            selectAllCheckbox.replaceWith(selectAllCheckbox.cloneNode(true));
            const newSelectAll = document.getElementById('selectAllOrders');
            newSelectAll.addEventListener('change', (e) => this.toggleAll(e.target.checked));
        }

        // Individual order checkboxes
        document.querySelectorAll('.order-checkbox').forEach(checkbox => {
            // Clone to remove old listeners
            const newCheckbox = checkbox.cloneNode(true);
            checkbox.parentNode.replaceChild(newCheckbox, checkbox);
            newCheckbox.addEventListener('change', (e) => this.toggleOrder(parseInt(e.target.value), e.target.checked));
        });

        // Bulk action buttons
        const archiveBtn = document.getElementById('bulkArchiveBtn');
        const deleteBtn = document.getElementById('bulkDeleteBtn');

        if (archiveBtn) {
            const newArchiveBtn = archiveBtn.cloneNode(true);
            archiveBtn.parentNode.replaceChild(newArchiveBtn, archiveBtn);
            newArchiveBtn.addEventListener('click', () => this.bulkArchive());
        }

        if (deleteBtn) {
            const newDeleteBtn = deleteBtn.cloneNode(true);
            deleteBtn.parentNode.replaceChild(newDeleteBtn, deleteBtn);
            newDeleteBtn.addEventListener('click', () => this.bulkDelete());
        }

        // Restore edit mode state after HTMX swap
        this.restoreEditModeState();
    }

    restoreEditModeState() {
        const editModeToggle = document.getElementById('editModeToggle');
        if (editModeToggle && editModeToggle.checked) {
            // Re-apply edit mode
            this.editMode = true;
            this.updateUI();
        }
    }

    toggleEditMode(enabled) {
        this.editMode = enabled;
        if (!enabled) {
            // Clear selections when turning off edit mode
            this.selectedOrders.clear();
            document.querySelectorAll('.order-checkbox').forEach(cb => {
                cb.checked = false;
            });
            const selectAllCheckbox = document.getElementById('selectAllOrders');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
        }
        this.updateUI();
    }

    toggleAll(checked) {
        if (checked) {
            document.querySelectorAll('.order-checkbox').forEach(cb => {
                this.selectedOrders.add(parseInt(cb.value));
                cb.checked = true;
            });
        } else {
            this.selectedOrders.clear();
            document.querySelectorAll('.order-checkbox').forEach(cb => {
                cb.checked = false;
            });
        }
        this.updateUI();
    }

    toggleOrder(orderId, checked) {
        if (checked) {
            this.selectedOrders.add(orderId);
        } else {
            this.selectedOrders.delete(orderId);
        }
        this.updateSelectAllCheckbox();
        this.updateUI();
    }

    updateSelectAllCheckbox() {
        const selectAllCheckbox = document.getElementById('selectAllOrders');
        const allCheckboxes = document.querySelectorAll('.order-checkbox');

        if (selectAllCheckbox && allCheckboxes.length > 0) {
            selectAllCheckbox.checked = this.selectedOrders.size > 0 &&
                                       this.selectedOrders.size === allCheckboxes.length;
        }
    }

    updateUI() {
        // Show/hide edit mode columns (including header checkbox)
        document.querySelectorAll('.edit-mode-column').forEach(el => {
            el.style.display = this.editMode ? '' : 'none';
        });

        // Show/hide action buttons
        const actionButtons = document.getElementById('bulkActionButtons');
        if (actionButtons) {
            if (this.editMode && this.selectedOrders.size > 0) {
                actionButtons.style.display = 'flex';
                actionButtons.classList.add('fade-in');
            } else {
                actionButtons.style.display = 'none';
                actionButtons.classList.remove('fade-in');
            }
        }

        // Update button counters
        const counters = document.querySelectorAll('.selected-count');
        counters.forEach(counter => {
            counter.textContent = this.selectedOrders.size;
        });

        // Update empty state colspan
        const emptyRow = document.querySelector('.empty-orders-row');
        if (emptyRow) {
            const td = emptyRow.querySelector('td');
            if (td) {
                td.colSpan = this.editMode ? 7 : 7; // Always 7 columns (with/without checkbox)
            }
        }
    }

    bulkDelete() {
        if (this.selectedOrders.size === 0) return;
        this.showModal('deleteConfirmModal', this.selectedOrders.size);
    }

    bulkArchive() {
        if (this.selectedOrders.size === 0) return;
        this.showModal('archiveConfirmModal', this.selectedOrders.size);
    }

    async executeDelete() {
        this.hideModal('deleteConfirmModal');

        const formData = new FormData();
        this.selectedOrders.forEach(id => formData.append('order_ids[]', id));

        try {
            const response = await fetch(window.bulkDeleteUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: formData
            });

            if (response.ok) {
                this.selectedOrders.clear();
                if (typeof htmx !== 'undefined') {
                    htmx.trigger(document.body, 'order-items-updated');
                } else {
                    location.reload();
                }
            }
        } catch (error) {
            console.error('Error deleting orders:', error);
        }
    }

    async executeArchive() {
        this.hideModal('archiveConfirmModal');

        const formData = new FormData();
        this.selectedOrders.forEach(id => formData.append('order_ids[]', id));

        try {
            const response = await fetch(window.bulkArchiveUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: formData
            });

            if (response.ok) {
                this.selectedOrders.clear();
                if (typeof htmx !== 'undefined') {
                    htmx.trigger(document.body, 'order-items-updated');
                } else {
                    location.reload();
                }
            }
        } catch (error) {
            console.error('Error archiving orders:', error);
        }
    }

    getCsrfToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
}

// Initialize when script loads
let orderEditMode;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        orderEditMode = new OrderEditMode();
    });
} else {
    orderEditMode = new OrderEditMode();
}

// Reinitialize after HTMX swaps
document.body.addEventListener('htmx:afterSwap', (event) => {
    // Check if the swap affected the order list
    const target = event.detail.target;
    if (target.querySelector('#order-list-container') ||
        target.id === 'order-list-container' ||
        target.closest('[hx-get*="order_list"]')) {
        if (orderEditMode) {
            orderEditMode.setupEventListeners();
        }
    }
});