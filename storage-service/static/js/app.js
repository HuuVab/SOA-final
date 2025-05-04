/**
 * Main application initialization
 */
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM content loaded, initializing application');
  
  // Set current year in footer
  if (typeof Utils !== 'undefined') {
    Utils.setCurrentYear();
    console.log('Current year set in footer');
  } else {
    console.error('Utils is not defined');
  }

  // Initialize product form handlers if available
  if (typeof ProductForm !== 'undefined') {
    ProductForm.init();
    console.log('Product form handlers initialized');
  } else {
    console.error('ProductForm is not defined - check if product-form.js is loaded correctly');
  }

  // Set up event listeners
  setupEventListeners();
  console.log('Global event listeners set up');

  // Load products on initial page load if Products is available
  if (typeof Products !== 'undefined') {
    console.log('Loading products...');
    Products.loadProducts();
  } else {
    console.error('Products is not defined - check if products.js is loaded correctly');
  }
});

/**
 * Set up global event listeners
 */
function setupEventListeners() {
  // Back button
  const backButton = document.getElementById('back-button');
  if (backButton) {
    backButton.addEventListener('click', function() {
      console.log('Back button clicked');
      if (typeof Utils !== 'undefined') {
        Utils.switchView('products-view');
      } else {
        // Fallback navigation if Utils is not available
        document.querySelectorAll('.view').forEach(view => {
          view.classList.add('hidden');
        });
        const productsView = document.getElementById('products-view');
        if (productsView) {
          productsView.classList.remove('hidden');
        }
        backButton.classList.add('hidden');
        const addButton = document.getElementById('add-product-button');
        if (addButton) {
          addButton.classList.remove('hidden');
        }
      }
    });
    console.log('Back button handler attached');
  } else {
    console.warn('Back button not found in DOM');
  }

  // Add product button
  const addProductButton = document.getElementById('add-product-button');
  if (addProductButton) {
    addProductButton.addEventListener('click', function() {
      console.log('Add product button clicked');
      // Reset the add product form
      const form = document.getElementById('add-product-form');
      if (form) {
        form.reset();
      } else {
        console.warn('Add product form not found');
      }
      
      // Clear selected files
      const selectedFiles = document.getElementById('selected-files');
      if (selectedFiles) {
        selectedFiles.innerHTML = '';
        selectedFiles.classList.add('hidden');
      } else {
        console.warn('Selected files container not found');
      }
      
      if (typeof Utils !== 'undefined') {
        Utils.switchView('add-product-view');
      } else {
        // Fallback navigation if Utils is not available
        document.querySelectorAll('.view').forEach(view => {
          view.classList.add('hidden');
        });
        const addView = document.getElementById('add-product-view');
        if (addView) {
          addView.classList.remove('hidden');
        }
        addProductButton.classList.add('hidden');
        const backButton = document.getElementById('back-button');
        if (backButton) {
          backButton.classList.remove('hidden');
        }
      }
    });
    console.log('Add product button handler attached');
  } else {
    console.warn('Add product button not found in DOM');
  }
  
  // Add error event listener to monitor for script loading issues
  window.addEventListener('error', function(event) {
    // Check if it's a script loading error
    if (event.target && (event.target.tagName === 'SCRIPT' || event.target.tagName === 'LINK')) {
      console.error(`Failed to load resource: ${event.target.src || event.target.href}`);
    } else {
      console.error('Global error caught:', event.error || event.message);
    }
  }, true); // Use capture to catch all errors
  
  // Check API health if available
  setTimeout(() => {
    if (typeof API !== 'undefined' && typeof API.checkHealth === 'function') {
      API.checkHealth()
        .then(result => {
          console.log('API health check result:', result);
        })
        .catch(error => {
          console.error('API health check failed:', error);
        });
    } else {
      console.warn('API.checkHealth not available - check if api.js is loaded correctly');
    }
  }, 1000);
}