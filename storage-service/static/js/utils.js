/**
 * Utility functions for the Product Management System
 */
const Utils = {
  /**
   * Show a notification message
   * @param {string} message - The message to display
   * @param {string} type - The type of notification (success, error)
   */
  showNotification(message, type = 'success') {
    console.log(`Showing notification: ${message} (${type})`);
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification notification-${type}`;
    notification.classList.remove('hidden');
    
    // Clear any existing timeout
    if (this.notificationTimeout) {
      clearTimeout(this.notificationTimeout);
    }
    
    // Hide after 3 seconds
    this.notificationTimeout = setTimeout(() => {
      notification.classList.add('hidden');
    }, 3000);
  },
  
  /**
   * Format a price value as currency
   * @param {number} price - The price to format
   * @returns {string} Formatted price string
   */
  formatPrice(price) {
    if (price === undefined || price === null) return '$0.00';
    try {
      return '$' + parseFloat(price).toFixed(2);
    } catch (e) {
      console.error('Error formatting price:', e);
      return '$0.00';
    }
  },
  
  /**
   * Format a date string
   * @param {string} dateString - The date string to format
   * @returns {string} Formatted date string
   */
  formatDate(dateString) {
    if (!dateString) return '';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch (e) {
      console.error('Error formatting date:', e);
      return dateString;
    }
  },
  
  /**
   * Toggle the loading overlay
   * @param {boolean} show - Whether to show or hide the overlay
   */
  toggleLoading(show) {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (show) {
      console.log('Showing loading overlay');
      loadingOverlay.classList.remove('hidden');
    } else {
      console.log('Hiding loading overlay');
      loadingOverlay.classList.add('hidden');
    }
  },
  
  /**
   * Show a confirmation modal
   * @param {string} title - Modal title
   * @param {string} message - Modal message
   * @returns {Promise<boolean>} Promise that resolves to true if confirmed, false if cancelled
   */
  showConfirmation(title, message) {
    console.log(`Showing confirmation dialog: ${title}`);
    return new Promise((resolve) => {
      const modal = document.getElementById('confirmation-modal');
      const modalTitle = document.getElementById('modal-title');
      const modalMessage = document.getElementById('modal-message');
      const confirmButton = document.getElementById('modal-confirm');
      const cancelButton = document.getElementById('modal-cancel');
      
      modalTitle.textContent = title;
      modalMessage.textContent = message;
      modal.classList.remove('hidden');
      
      const handleConfirm = () => {
        console.log('Confirmation dialog: confirmed');
        modal.classList.add('hidden');
        confirmButton.removeEventListener('click', handleConfirm);
        cancelButton.removeEventListener('click', handleCancel);
        resolve(true);
      };
      
      const handleCancel = () => {
        console.log('Confirmation dialog: cancelled');
        modal.classList.add('hidden');
        confirmButton.removeEventListener('click', handleConfirm);
        cancelButton.removeEventListener('click', handleCancel);
        resolve(false);
      };
      
      confirmButton.addEventListener('click', handleConfirm);
      cancelButton.addEventListener('click', handleCancel);
    });
  },
  
  /**
   * Switch between different views
   * @param {string} viewId - The ID of the view to show
   */
  switchView(viewId) {
    console.log(`Switching to view: ${viewId}`);
    // Hide all views
    const views = document.querySelectorAll('.view');
    views.forEach(view => view.classList.add('hidden'));
    
    // Show the selected view
    const selectedView = document.getElementById(viewId);
    if (selectedView) {
      selectedView.classList.remove('hidden');
    } else {
      console.error(`View with ID "${viewId}" not found!`);
    }
    
    // Handle back button visibility
    const backButton = document.getElementById('back-button');
    if (viewId === 'products-view') {
      backButton.classList.add('hidden');
      document.getElementById('add-product-button').classList.remove('hidden');
    } else {
      backButton.classList.remove('hidden');
      document.getElementById('add-product-button').classList.add('hidden');
    }
  },
  
  /**
   * Truncate text to a maximum length
   * @param {string} text - The text to truncate
   * @param {number} maxLength - Maximum length before truncating
   * @returns {string} Truncated text
   */
  truncateText(text, maxLength = 100) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  },
  
  /**
   * Create a DOM element with attributes and children
   * @param {string} tagName - The tag name of the element to create
   * @param {Object} attributes - Attributes to set on the element
   * @param {Array|string|Element} children - Child elements or text content
   * @returns {Element} The created DOM element
   */
  createElement(tagName, attributes = {}, children = []) {
    const element = document.createElement(tagName);
    
    // Set attributes
    Object.entries(attributes).forEach(([key, value]) => {
      if (key === 'className') {
        element.className = value;
      } else if (key === 'textContent') {
        element.textContent = value;
      } else if (key === 'innerHTML') {
        element.innerHTML = value;
      } else if (key.startsWith('on') && typeof value === 'function') {
        element.addEventListener(key.substring(2).toLowerCase(), value);
      } else {
        element.setAttribute(key, value);
      }
    });
    
    // Add children
    if (children) {
      if (Array.isArray(children)) {
        children.forEach(child => {
          if (child !== undefined && child !== null) {
            element.appendChild(
              typeof child === 'string' || typeof child === 'number'
                ? document.createTextNode(child)
                : child
            );
          }
        });
      } else if (typeof children === 'string' || typeof children === 'number') {
        element.textContent = children;
      } else if (children instanceof Element) {
        element.appendChild(children);
      }
    }
    
    return element;
  },
  
  /**
   * Set the current year in the footer
   */
  setCurrentYear() {
    const yearElement = document.getElementById('current-year');
    if (yearElement) {
      yearElement.textContent = new Date().getFullYear();
    }
  }
};