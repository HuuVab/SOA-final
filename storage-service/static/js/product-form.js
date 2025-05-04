const ProductForm = {

  init() {
    console.log('Initializing product form handlers');
    
    // Add product form submission
    const addProductForm = document.getElementById('add-product-form');
    if (addProductForm) {
      addProductForm.addEventListener('submit', this.handleAddProduct.bind(this));
      console.log('Add product form handler attached');
    } else {
      console.warn('Add product form not found in DOM');
    }
    
    // Edit product form submission
    const editProductForm = document.getElementById('edit-product-form');
    if (editProductForm) {
      editProductForm.addEventListener('submit', this.handleEditProduct.bind(this));
      console.log('Edit product form handler attached');
    } else {
      console.warn('Edit product form not found in DOM');
    }
    
    // File input change handlers
    const addProductImages = document.getElementById('product-images');
    if (addProductImages) {
      addProductImages.addEventListener('change', () => this.handleFileSelection('product-images', 'selected-files'));
      console.log('Add product images handler attached');
    } else {
      console.warn('Product images input not found in DOM');
    }
    
    const editProductImages = document.getElementById('edit-product-images');
    if (editProductImages) {
      editProductImages.addEventListener('change', () => this.handleFileSelection('edit-product-images', 'edit-selected-files'));
      console.log('Edit product images handler attached');
    } else {
      console.warn('Edit product images input not found in DOM');
    }
    
    // Cancel buttons
    const cancelAdd = document.getElementById('cancel-add');
    if (cancelAdd) {
      cancelAdd.addEventListener('click', () => Utils.switchView('products-view'));
      console.log('Cancel add button handler attached');
    }
    
    const cancelEdit = document.getElementById('cancel-edit');
    if (cancelEdit) {
      cancelEdit.addEventListener('click', () => Utils.switchView('products-view'));
      console.log('Cancel edit button handler attached');
    }
  },
  
  /**
   * Handle file selection for image upload
   * @param {string} inputId - The ID of the file input element
   * @param {string} containerId - The ID of the container to display selected files
   */
  handleFileSelection(inputId, containerId) {
    const fileInput = document.getElementById(inputId);
    const container = document.getElementById(containerId);
    
    if (!fileInput) {
      console.warn(`File input with ID "${inputId}" not found`);
      return;
    }
    
    if (!container) {
      console.warn(`Container with ID "${containerId}" not found`);
      return;
    }
    
    if (fileInput.files.length > 0) {
      console.log(`${fileInput.files.length} files selected for ${inputId}`);
      container.innerHTML = '';
      container.classList.remove('hidden');
      
      const fileList = document.createElement('ul');
      
      for (let i = 0; i < fileInput.files.length; i++) {
        const file = fileInput.files[i];
        console.log(`Selected file: ${file.name} (${file.type})`);
        const listItem = document.createElement('li');
        listItem.textContent = file.name;
        fileList.appendChild(listItem);
      }
      
      container.appendChild(fileList);
    } else {
      console.log('No files selected');
      container.innerHTML = '';
      container.classList.add('hidden');
    }
  },
  
  /**
   * Handle add product form submission
   * @param {Event} event - The form submission event
   */
  async handleAddProduct(event) {
    event.preventDefault();
    console.log('Add product form submitted');
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Log form data
    for (const [key, value] of formData.entries()) {
      console.log(`Form data: ${key} = ${value}`);
    }
    
    // Validate form
    if (!this.validateProductForm(form)) {
      console.log('Form validation failed');
      return;
    }
    
    Utils.toggleLoading(true);
    
    try {
      // Prepare product data
      const productData = {
        name: formData.get('name'),
        price: parseFloat(formData.get('price')),
        description: formData.get('description'),
        stock: parseInt(formData.get('stock'), 10),
        category: formData.get('category') || '',
        manufacturer: formData.get('manufacturer') || ''
      };
      
      console.log('Creating new product with data:', productData);
      
      // Create product
      const result = await API.createProduct(productData);
      console.log('Create product result:', result);
      
      if (result.status === 'success') {
        const productId = result.data.product_id;
        console.log(`Product created with ID: ${productId}`);
        
        // Upload images if selected
        const fileInput = document.getElementById('product-images');
        if (fileInput.files.length > 0) {
          console.log(`Uploading ${fileInput.files.length} images for new product`);
          const uploadResult = await API.uploadProductImages(productId, fileInput.files);
          console.log('Image upload result:', uploadResult);
          
          if (uploadResult.status !== 'success') {
            console.warn('Images uploaded with some issues:', uploadResult.message);
          }
        }
        
        // Show success notification
        Utils.showNotification('Product created successfully', 'success');
        
        // Reset form
        form.reset();
        document.getElementById('selected-files').innerHTML = '';
        document.getElementById('selected-files').classList.add('hidden');
        
        // Navigate back to products view
        Utils.switchView('products-view');
        
        // Reload products
        Products.loadProducts();
      } else {
        console.error('Failed to create product:', result.message);
        Utils.showNotification(result.message || 'Failed to create product', 'error');
      }
    } catch (error) {
      console.error('Error creating product:', error);
      Utils.showNotification('An unexpected error occurred', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Handle edit product form submission
   * @param {Event} event - The form submission event
   */
  async handleEditProduct(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const productId = formData.get('product_id');
    
    console.log(`Edit product form submitted for product ID: ${productId}`);
    
    // Log form data
    for (const [key, value] of formData.entries()) {
      console.log(`Form data: ${key} = ${value}`);
    }
    
    // Validate form
    if (!this.validateProductForm(form)) {
      console.log('Form validation failed');
      return;
    }
    
    Utils.toggleLoading(true);
    
    try {
      // Prepare product data
      const productData = {
        name: formData.get('name'),
        price: parseFloat(formData.get('price')),
        description: formData.get('description'),
        stock: parseInt(formData.get('stock'), 10),
        category: formData.get('category') || '',
        manufacturer: formData.get('manufacturer') || ''
      };
      
      console.log(`Updating product ${productId} with data:`, productData);
      
      // Update product
      const result = await API.updateProduct(productId, productData);
      console.log('Update product result:', result);
      
      if (result.status === 'success') {
        // Upload images if selected
        const fileInput = document.getElementById('edit-product-images');
        if (fileInput.files.length > 0) {
          console.log(`Uploading ${fileInput.files.length} new images for product`);
          const uploadResult = await API.uploadProductImages(productId, fileInput.files);
          console.log('Image upload result:', uploadResult);
          
          if (uploadResult.status !== 'success') {
            console.warn('Images uploaded with some issues:', uploadResult.message);
          }
        }
        
        // Show success notification
        Utils.showNotification('Product updated successfully', 'success');
        
        // Navigate back to products view
        Utils.switchView('products-view');
        
        // Reload products
        Products.loadProducts();
      } else {
        console.error('Failed to update product:', result.message);
        Utils.showNotification(result.message || 'Failed to update product', 'error');
      }
    } catch (error) {
      console.error('Error updating product:', error);
      Utils.showNotification('An unexpected error occurred', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Validate product form fields
   * @param {HTMLFormElement} form - The form to validate
   * @returns {boolean} Whether the form is valid
   */
  validateProductForm(form) {
    console.log('Validating product form');
    
    // Check required fields
    const name = form.querySelector('[name="name"]');
    const price = form.querySelector('[name="price"]');
    const stock = form.querySelector('[name="stock"]');
    const description = form.querySelector('[name="description"]');
    
    let valid = true;
    
    if (!name || !name.value.trim()) {
      this.showFieldError(name, 'Product name is required');
      console.log('Validation error: Product name is required');
      valid = false;
    } else {
      this.clearFieldError(name);
    }
    
    if (!price || !price.value || isNaN(parseFloat(price.value)) || parseFloat(price.value) < 0) {
      this.showFieldError(price, 'Please enter a valid price');
      console.log('Validation error: Invalid price');
      valid = false;
    } else {
      this.clearFieldError(price);
    }
    
    if (!stock || !stock.value || isNaN(parseInt(stock.value, 10)) || parseInt(stock.value, 10) < 0) {
      this.showFieldError(stock, 'Please enter a valid stock quantity');
      console.log('Validation error: Invalid stock quantity');
      valid = false;
    } else {
      this.clearFieldError(stock);
    }
    
    if (!description || !description.value.trim()) {
      this.showFieldError(description, 'Product description is required');
      console.log('Validation error: Product description is required');
      valid = false;
    } else {
      this.clearFieldError(description);
    }
    
    console.log(`Form validation ${valid ? 'passed' : 'failed'}`);
    return valid;
  },
  
  /**
   * Show field error message
   * @param {HTMLElement} field - The field with an error
   * @param {string} message - The error message
   */
  showFieldError(field, message) {
    if (!field) {
      console.error('Cannot show field error: field is null or undefined');
      return;
    }
    
    // Remove any existing error
    this.clearFieldError(field);
    
    // Add error class to field
    field.classList.add('error');
    
    // Create error message element
    const errorElement = document.createElement('div');
    errorElement.className = 'field-error';
    errorElement.textContent = message;
    
    // Insert after the field
    if (field.parentNode) {
      field.parentNode.insertBefore(errorElement, field.nextSibling);
    } else {
      console.error('Cannot show field error: field has no parent node');
    }
  },
  
  /**
   * Clear field error message
   * @param {HTMLElement} field - The field to clear error for
   */
  clearFieldError(field) {
    if (!field) {
      console.error('Cannot clear field error: field is null or undefined');
      return;
    }
    
    // Remove error class
    field.classList.remove('error');
    
    // Remove any existing error message
    if (field.nextElementSibling && field.nextElementSibling.classList.contains('field-error')) {
      field.nextElementSibling.remove();
    }
  }
};