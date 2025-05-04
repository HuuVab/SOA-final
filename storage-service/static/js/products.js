/**
 * Products management functionality
 */
const Products = {
  /**
   * Load and display all products
   */
  async loadProducts() {
    Utils.toggleLoading(true);
    
    const productsGrid = document.getElementById('products-grid');
    productsGrid.innerHTML = '';
    
    try {
      console.log('Fetching products...');
      const result = await API.getAllProducts();
      console.log('Products API response:', result);
      
      // Handle different response structures
      let products = [];
      if (result.status === 'success') {
        if (Array.isArray(result.data)) {
          products = result.data;
        } else if (result.data && Array.isArray(result.data.products)) {
          products = result.data.products;
        } else if (result.data && typeof result.data === 'object') {
          products = [result.data]; // Single product object
        }
      } else {
        // Check if products are directly in the response
        if (Array.isArray(result)) {
          products = result;
        } else if (result.products && Array.isArray(result.products)) {
          products = result.products;
        }
      }
      
      console.log(`Found ${products.length} products to display`);
      
      if (products.length > 0) {
        products.forEach(product => {
          try {
            productsGrid.appendChild(this.createProductCard(product));
          } catch (error) {
            console.error('Error creating product card:', error, product);
          }
        });
      } else {
        productsGrid.innerHTML = `
          <div class="text-center" style="grid-column: 1/-1; padding: 2rem;">
            <i class="fas fa-box-open" style="font-size: 3rem; color: var(--secondary-color); margin-bottom: 1rem;"></i>
            <p>No products found. Add your first product!</p>
          </div>
        `;
      }
    } catch (error) {
      console.error('Error loading products:', error);
      Utils.showNotification('An unexpected error occurred while loading products', 'error');
      
      productsGrid.innerHTML = `
        <div class="text-center" style="grid-column: 1/-1; padding: 2rem;">
          <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: var(--danger-color); margin-bottom: 1rem;"></i>
          <p>Error loading products. Please try again later.</p>
          <p class="text-secondary mt-2">Error details: ${error.message || 'Unknown error'}</p>
        </div>
      `;
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Create a product card element
   * @param {Object} product - The product data
   * @returns {Element} The product card element
   */
  createProductCard(product) {
    if (!product) {
      console.error('Cannot create product card: product is null or undefined');
      return document.createElement('div');
    }
    
    console.log('Creating product card for:', product);
    
    // Normalize product data to handle different API structures
    const normalizedProduct = {
      id: product.product_id || product.id || '',
      name: product.name || 'Unnamed Product',
      price: typeof product.price === 'number' ? product.price : 
             typeof product.price === 'string' ? parseFloat(product.price) : 0,
      description: product.description || 'No description available',
      stock: product.stock_quantity || product.stock || 0,
      category: product.category || '',
      manufacturer: product.manufacturer || '',
      image: product.image_url || product.image || ''
    };
    
    const card = Utils.createElement('div', { className: 'product-card' });
    
    // Product image
    const imageContainer = Utils.createElement('div', { className: 'product-image' });
    if (normalizedProduct.image) {
      const img = Utils.createElement('img', {
        src: API.getImageUrl(normalizedProduct.image),
        alt: normalizedProduct.name,
        onerror: function() {
          console.log('Image failed to load for product:', normalizedProduct.id);
          this.onerror = null;
          this.parentElement.innerHTML = '<i class="fas fa-image"></i>';
        }
      });
      imageContainer.appendChild(img);
    } else {
      imageContainer.innerHTML = '<i class="fas fa-image"></i>';
    }
    card.appendChild(imageContainer);
    
    // Product info
    const info = Utils.createElement('div', { className: 'product-info' });
    
    info.appendChild(Utils.createElement('h3', { className: 'product-title' }, normalizedProduct.name));
    info.appendChild(Utils.createElement('div', { className: 'product-price' }, Utils.formatPrice(normalizedProduct.price)));
    
    const descriptionEl = Utils.createElement('p', { className: 'product-description' }, normalizedProduct.description);
    info.appendChild(descriptionEl);
    
    // Product meta
    const meta = Utils.createElement('div', { className: 'product-meta' });
    meta.appendChild(Utils.createElement('span', { className: 'product-stock' }, `Stock: ${normalizedProduct.stock}`));
    if (normalizedProduct.category) {
      meta.appendChild(Utils.createElement('span', { className: 'product-category' }, `Category: ${normalizedProduct.category}`));
    }
    info.appendChild(meta);
    
    // Product actions
    const actions = Utils.createElement('div', { className: 'product-actions' });
    
    const viewButton = Utils.createElement('button', { 
      className: 'btn btn-primary btn-sm',
      onclick: () => this.viewProductDetails(normalizedProduct.id)
    }, 'View Details');
    actions.appendChild(viewButton);
    
    const actionButtons = Utils.createElement('div', { className: 'action-buttons' });
    
    const editButton = Utils.createElement('button', { 
      className: 'btn btn-warning btn-sm btn-icon',
      title: 'Edit Product',
      onclick: () => this.editProduct(normalizedProduct.id)
    }, Utils.createElement('i', { className: 'fas fa-edit' }));
    actionButtons.appendChild(editButton);
    
    const deleteButton = Utils.createElement('button', { 
      className: 'btn btn-danger btn-sm btn-icon',
      title: 'Delete Product',
      onclick: () => this.deleteProduct(normalizedProduct.id, normalizedProduct.name)
    }, Utils.createElement('i', { className: 'fas fa-trash' }));
    actionButtons.appendChild(deleteButton);
    
    actions.appendChild(actionButtons);
    info.appendChild(actions);
    
    card.appendChild(info);
    return card;
  },
  
  /**
   * View product details
   * @param {string} productId - The ID of the product to view
   */
  async viewProductDetails(productId) {
    if (!productId) {
      console.error('Cannot view product details: product ID is missing');
      Utils.showNotification('Product ID is missing', 'error');
      return;
    }
    
    Utils.toggleLoading(true);
    
    try {
      console.log(`Fetching details for product ${productId}`);
      const result = await API.getProduct(productId);
      console.log('Product details response:', result);
      
      // Extract product data from response
      let product = null;
      if (result.status === 'success' && result.data) {
        product = result.data;
      } else if (result.product) {
        product = result.product;
      } else if (!result.status && typeof result === 'object') {
        product = result; // Direct product object
      }
      
      if (!product) {
        console.error('No product data found in response');
        Utils.showNotification('Product details not found', 'error');
        Utils.toggleLoading(false);
        return;
      }
      
      // Normalize product data
      const normalizedProduct = {
        id: product.product_id || product.id || productId,
        name: product.name || 'Unnamed Product',
        price: typeof product.price === 'number' ? product.price : 
               typeof product.price === 'string' ? parseFloat(product.price) : 0,
        description: product.description || 'No description available',
        stock: product.stock_quantity || product.stock || 0,
        category: product.category || '',
        manufacturer: product.manufacturer || '',
        image: product.image_url || product.image || '',
        images: Array.isArray(product.images) ? product.images : [],
        created_at: product.created_at || '',
        updated_at: product.updated_at || ''
      };
      
      console.log('Normalized product data:', normalizedProduct);
      
      // Populate the product details view
      const detailsContainer = document.getElementById('product-details-container');
      detailsContainer.innerHTML = '';
      
      // Product header
      const header = Utils.createElement('div', { className: 'product-header' });
      header.appendChild(Utils.createElement('h2', { className: 'product-title' }, normalizedProduct.name));
      detailsContainer.appendChild(header);
      
      // Product content
      const content = Utils.createElement('div', { className: 'product-content' });
      
      // Main image
      const mainImage = Utils.createElement('div', { className: 'product-main-image' });
      if (normalizedProduct.images.length > 0) {
        // Find primary image or use first one
        const primaryImage = normalizedProduct.images.find(img => img.is_primary === 1) || normalizedProduct.images[0];
        const imagePath = primaryImage.path || primaryImage.url || '';
        
        if (imagePath) {
          const img = Utils.createElement('img', {
            src: API.getImageUrl(imagePath),
            alt: normalizedProduct.name,
            onerror: function() {
              console.log('Main image failed to load');
              this.onerror = null;
              this.parentElement.innerHTML = '<i class="fas fa-image" style="font-size: 5rem; color: var(--secondary-color);"></i>';
            }
          });
          mainImage.appendChild(img);
        } else {
          mainImage.innerHTML = '<i class="fas fa-image" style="font-size: 5rem; color: var(--secondary-color);"></i>';
        }
      } else if (normalizedProduct.image) {
        const img = Utils.createElement('img', {
          src: API.getImageUrl(normalizedProduct.image),
          alt: normalizedProduct.name,
          onerror: function() {
            console.log('Fallback image failed to load');
            this.onerror = null;
            this.parentElement.innerHTML = '<i class="fas fa-image" style="font-size: 5rem; color: var(--secondary-color);"></i>';
          }
        });
        mainImage.appendChild(img);
      } else {
        mainImage.innerHTML = '<i class="fas fa-image" style="font-size: 5rem; color: var(--secondary-color);"></i>';
      }
      content.appendChild(mainImage);
      
      // Product info panel
      const infoPanel = Utils.createElement('div', { className: 'product-info-panel' });
      
      const price = Utils.createElement('div', { className: 'product-price' }, Utils.formatPrice(normalizedProduct.price));
      
      const stock = Utils.createElement('span', {
        className: normalizedProduct.stock > 0 ? 'text-success' : 'text-danger',
        style: 'margin-left: 1rem;'
      }, normalizedProduct.stock > 0 ? `In Stock (${normalizedProduct.stock})` : 'Out of Stock');
      
      price.appendChild(stock);
      infoPanel.appendChild(price);
      
      // Product specs
      const specs = Utils.createElement('div', { className: 'product-specs' });
      
      if (normalizedProduct.category) {
        const category = Utils.createElement('p', { className: 'product-spec' });
        category.appendChild(Utils.createElement('span', {}, 'Category: '));
        category.appendChild(document.createTextNode(normalizedProduct.category));
        specs.appendChild(category);
      }
      
      if (normalizedProduct.manufacturer) {
        const manufacturer = Utils.createElement('p', { className: 'product-spec' });
        manufacturer.appendChild(Utils.createElement('span', {}, 'Manufacturer: '));
        manufacturer.appendChild(document.createTextNode(normalizedProduct.manufacturer));
        specs.appendChild(manufacturer);
      }
      
      const id = Utils.createElement('p', { className: 'product-spec' });
      id.appendChild(Utils.createElement('span', {}, 'ID: '));
      id.appendChild(document.createTextNode(normalizedProduct.id));
      specs.appendChild(id);
      
      if (normalizedProduct.created_at) {
        const created = Utils.createElement('p', { className: 'product-spec' });
        created.appendChild(Utils.createElement('span', {}, 'Created: '));
        created.appendChild(document.createTextNode(Utils.formatDate(normalizedProduct.created_at)));
        specs.appendChild(created);
      }
      
      if (normalizedProduct.updated_at) {
        const updated = Utils.createElement('p', { className: 'product-spec' });
        updated.appendChild(Utils.createElement('span', {}, 'Last Updated: '));
        updated.appendChild(document.createTextNode(Utils.formatDate(normalizedProduct.updated_at)));
        specs.appendChild(updated);
      }
      
      infoPanel.appendChild(specs);
      
      // Product actions
      const actionsPanel = Utils.createElement('div', { className: 'product-actions-panel' });
      
      const editButton = Utils.createElement('button', { 
        className: 'btn btn-warning',
        onclick: () => this.editProduct(normalizedProduct.id)
      }, [
        Utils.createElement('i', { className: 'fas fa-edit', style: 'margin-right: 0.5rem;' }),
        'Edit Product'
      ]);
      actionsPanel.appendChild(editButton);
      
      const deleteButton = Utils.createElement('button', { 
        className: 'btn btn-danger',
        onclick: () => this.deleteProduct(normalizedProduct.id, normalizedProduct.name)
      }, [
        Utils.createElement('i', { className: 'fas fa-trash', style: 'margin-right: 0.5rem;' }),
        'Delete Product'
      ]);
      actionsPanel.appendChild(deleteButton);
      
      infoPanel.appendChild(actionsPanel);
      content.appendChild(infoPanel);
      
      detailsContainer.appendChild(content);
      
      // Product description
      const descriptionPanel = Utils.createElement('div', { className: 'product-description-panel' });
      descriptionPanel.appendChild(Utils.createElement('h3', {}, 'Description'));
      descriptionPanel.appendChild(Utils.createElement('p', { className: 'product-description-content' }, normalizedProduct.description));
      detailsContainer.appendChild(descriptionPanel);
      
      // Product images
      if (normalizedProduct.images.length > 0) {
        const imagesPanel = Utils.createElement('div', { className: 'product-images-panel mt-4' });
        imagesPanel.appendChild(Utils.createElement('h3', { className: 'mb-2' }, 'Product Images'));
        
        const gallery = Utils.createElement('div', { className: 'image-gallery' });
        
        normalizedProduct.images.forEach(image => {
          const imagePath = image.path || image.url || '';
          if (!imagePath) return;
          
          const item = Utils.createElement('div', { 
            className: `gallery-item ${image.is_primary === 1 ? 'primary' : ''}`
          });
          
          const img = Utils.createElement('img', {
            src: API.getImageUrl(imagePath),
            alt: image.alt_text || normalizedProduct.name,
            onerror: function() {
              console.log('Gallery image failed to load');
              this.onerror = null;
              this.src = '/img/placeholder.svg';
            }
          });
          item.appendChild(img);
          
          if (image.is_primary === 1) {
            item.appendChild(Utils.createElement('div', { className: 'primary-badge' }, 'Primary'));
          }
          
          const overlay = Utils.createElement('div', { className: 'gallery-item-overlay' });
          const actions = Utils.createElement('div', { className: 'gallery-item-actions' });
          
          if (image.is_primary !== 1) {
            const setPrimaryBtn = Utils.createElement('button', { 
              className: 'btn btn-primary btn-sm btn-icon',
              title: 'Set as Primary Image',
              onclick: (e) => {
                e.stopPropagation();
                this.setPrimaryImage(image.image_id, normalizedProduct.id);
              }
            }, Utils.createElement('i', { className: 'fas fa-check' }));
            actions.appendChild(setPrimaryBtn);
          }
          
          const deleteBtn = Utils.createElement('button', { 
            className: 'btn btn-danger btn-sm btn-icon',
            title: 'Delete Image',
            onclick: (e) => {
              e.stopPropagation();
              this.deleteProductImage(image.image_id, normalizedProduct.id);
            }
          }, Utils.createElement('i', { className: 'fas fa-trash' }));
          actions.appendChild(deleteBtn);
          
          overlay.appendChild(actions);
          item.appendChild(overlay);
          
          gallery.appendChild(item);
        });
        
        imagesPanel.appendChild(gallery);
        detailsContainer.appendChild(imagesPanel);
      }
      
      // Switch to product details view
      Utils.switchView('product-details-view');
    } catch (error) {
      console.error(`Error loading product details:`, error);
      Utils.showNotification('Failed to load product details', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Delete a product
   * @param {string} productId - The ID of the product to delete
   * @param {string} productName - The name of the product
   */
  async deleteProduct(productId, productName) {
    if (!productId) {
      console.error('Cannot delete product: product ID is missing');
      Utils.showNotification('Product ID is required for deletion', 'error');
      return;
    }
    
    const confirmed = await Utils.showConfirmation(
      'Delete Product',
      `Are you sure you want to delete "${productName || 'this product'}"? This action cannot be undone.`
    );
    
    if (!confirmed) return;
    
    Utils.toggleLoading(true);
    
    try {
      console.log(`Deleting product ${productId}`);
      const result = await API.deleteProduct(productId);
      console.log('Delete result:', result);
      
      // Check if deletion was successful
      let success = false;
      if (result && result.status === 'success') {
        success = true;
      } else if (result && result.message && result.message.toLowerCase().includes('deleted')) {
        success = true;
      } else if (result && result.status === 200) {
        success = true;
      }
      
      if (success) {
        Utils.showNotification('Product deleted successfully', 'success');
        
        // Return to products view if we're in the details view
        if (document.getElementById('product-details-view').classList.contains('hidden') === false) {
          Utils.switchView('products-view');
        }
        
        // Reload products
        this.loadProducts();
      } else {
        console.error('Failed to delete product:', result ? result.message : 'Unknown error');
        Utils.showNotification(result && result.message ? result.message : 'Failed to delete product', 'error');
      }
    } catch (error) {
      console.error(`Error deleting product:`, error);
      Utils.showNotification('An unexpected error occurred during deletion', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Set primary image for a product
   * @param {string} imageId - The ID of the image to set as primary
   * @param {string} productId - The ID of the product
   */
  async setPrimaryImage(imageId, productId) {
    if (!imageId || !productId) {
      console.error('Cannot set primary image: required IDs missing');
      Utils.showNotification('Image ID and Product ID are required', 'error');
      return;
    }
    
    Utils.toggleLoading(true);
    
    try {
      console.log(`Setting image ${imageId} as primary for product ${productId}`);
      const result = await API.setPrimaryImage(imageId);
      console.log('Set primary image result:', result);
      
      let success = false;
      if (result && result.status === 'success') {
        success = true;
      } else if (result && result.message && result.message.toLowerCase().includes('primary')) {
        success = true;
      }
      
      if (success) {
        Utils.showNotification('Primary image updated successfully', 'success');
        
        // Refresh product details
        await this.viewProductDetails(productId);
      } else {
        console.error('Failed to set primary image:', result ? result.message : 'Unknown error');
        Utils.showNotification(result && result.message ? result.message : 'Failed to set primary image', 'error');
      }
    } catch (error) {
      console.error(`Error setting primary image:`, error);
      Utils.showNotification('An unexpected error occurred', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Delete product image
   * @param {string} imageId - The ID of the image to delete
   * @param {string} productId - The ID of the product
   */
  async deleteProductImage(imageId, productId) {
    if (!imageId || !productId) {
      console.error('Cannot delete image: required IDs missing');
      Utils.showNotification('Image ID and Product ID are required', 'error');
      return;
    }
    
    const confirmed = await Utils.showConfirmation(
      'Delete Image',
      'Are you sure you want to delete this image? This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    Utils.toggleLoading(true);
    
    try {
      console.log(`Deleting image ${imageId} from product ${productId}`);
      const result = await API.deleteProductImage(imageId);
      console.log('Delete image result:', result);
      
      let success = false;
      if (result && result.status === 'success') {
        success = true;
      } else if (result && result.message && result.message.toLowerCase().includes('deleted')) {
        success = true;
      }
      
      if (success) {
        Utils.showNotification('Image deleted successfully', 'success');
        
        // Refresh product details
        await this.viewProductDetails(productId);
      } else {
        console.error('Failed to delete image:', result ? result.message : 'Unknown error');
        Utils.showNotification(result && result.message ? result.message : 'Failed to delete image', 'error');
      }
    } catch (error) {
      console.error(`Error deleting image:`, error);
      Utils.showNotification('An unexpected error occurred', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  },
  
  /**
   * Prepare the edit product form
   * @param {string} productId - The ID of the product to edit
   */
  async editProduct(productId) {
    if (!productId) {
      console.error('Cannot edit product: product ID is missing');
      Utils.showNotification('Product ID is required', 'error');
      return;
    }
    
    Utils.toggleLoading(true);
    
    try {
      console.log(`Preparing to edit product ${productId}`);
      const result = await API.getProduct(productId);
      console.log('Product details for editing:', result);
      
      // Extract product data from response
      let product = null;
      if (result.status === 'success' && result.data) {
        product = result.data;
      } else if (result.product) {
        product = result.product;
      } else if (!result.status && typeof result === 'object') {
        product = result; // Direct product object
      }
      
      if (!product) {
        console.error('No product data found for editing');
        Utils.showNotification('Product details not found', 'error');
        Utils.toggleLoading(false);
        return;
      }
      
      // Normalize product data
      const normalizedProduct = {
        id: product.product_id || product.id || productId,
        name: product.name || '',
        price: product.price || '',
        description: product.description || '',
        stock: product.stock_quantity || product.stock || '',
        category: product.category || '',
        manufacturer: product.manufacturer || '',
        image: product.image_url || product.image || '',
        images: Array.isArray(product.images) ? product.images : []
      };
      
      console.log('Normalized product data for form:', normalizedProduct);
      
      // Fill the edit form
      document.getElementById('edit-product-id').value = normalizedProduct.id;
      document.getElementById('edit-name').value = normalizedProduct.name;
      document.getElementById('edit-price').value = normalizedProduct.price;
      document.getElementById('edit-stock').value = normalizedProduct.stock;
      document.getElementById('edit-category').value = normalizedProduct.category;
      document.getElementById('edit-manufacturer').value = normalizedProduct.manufacturer;
      document.getElementById('edit-description').value = normalizedProduct.description;
      
      // Clear selected files
      document.getElementById('edit-product-images').value = '';
      document.getElementById('edit-selected-files').innerHTML = '';
      document.getElementById('edit-selected-files').classList.add('hidden');
      
      // Populate current images
      const currentImagesContainer = document.getElementById('current-images-container');
      currentImagesContainer.innerHTML = '';
      
      if (normalizedProduct.images.length > 0) {
        console.log(`Displaying ${normalizedProduct.images.length} existing images in edit form`);
        normalizedProduct.images.forEach(image => {
          const imagePath = image.path || image.url || '';
          if (!imagePath) return;
          
          const item = Utils.createElement('div', { 
            className: `gallery-item ${image.is_primary === 1 ? 'primary' : ''}`
          });
          
          const img = Utils.createElement('img', {
            src: API.getImageUrl(imagePath),
            alt: image.alt_text || normalizedProduct.name,
            onerror: function() {
              console.log('Edit form image failed to load');
              this.onerror = null;
              this.src = '/img/placeholder.svg';
            }
          });
          item.appendChild(img);
          
          if (image.is_primary === 1) {
            item.appendChild(Utils.createElement('div', { className: 'primary-badge' }, 'Primary'));
          }
          
          currentImagesContainer.appendChild(item);
        });
        
        document.getElementById('current-images').classList.remove('hidden');
      } else if (normalizedProduct.image) {
        // Create single image display if only main image is available
        const item = Utils.createElement('div', { className: 'gallery-item primary' });
        
        const img = Utils.createElement('img', {
          src: API.getImageUrl(normalizedProduct.image),
          alt: normalizedProduct.name,
          onerror: function() {
            console.log('Edit form main image failed to load');
            this.onerror = null;
            this.src = '/img/placeholder.svg';
          }
        });
        item.appendChild(img);
        
        item.appendChild(Utils.createElement('div', { className: 'primary-badge' }, 'Primary'));
        
        currentImagesContainer.appendChild(item);
        document.getElementById('current-images').classList.remove('hidden');
      } else {
        console.log('No existing images for product in edit form');
        document.getElementById('current-images').classList.add('hidden');
      }
      
      // Switch to edit view
      Utils.switchView('edit-product-view');
    } catch (error) {
      console.error(`Error preparing product for edit:`, error);
      Utils.showNotification('Failed to load product for editing', 'error');
    } finally {
      Utils.toggleLoading(false);
    }
  }
};