/**
 * API Service for Product Management
 * Handles all communication with the storage service backend
 */
const API = (function() {
  // Base URL for the API - this points to the local server
  const baseUrl = '/api';
  
  /**
   * Helper function to handle API errors
   * @param {Error} error - The error object
   * @param {string} actionName - Name of the action that failed
   * @returns {Object} Error response object
   */
  const handleError = (error, actionName) => {
    console.error(`Error ${actionName}:`, error);
    return { 
      status: 'error', 
      message: 'Failed to connect to server. Please try again later.'
    };
  };

  /**
   * Helper function to make an API call with error handling
   * @param {string} url - API endpoint URL
   * @param {Object} options - Fetch options
   * @param {string} actionName - Name of the action for error logging
   * @returns {Promise<Object>} Response data
   */
  const apiCall = async (url, options = {}, actionName = 'API call') => {
    try {
      const response = await fetch(url, options);
      
      // Handle non-JSON responses
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        if (!response.ok) {
          throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return { status: 'success' };
      }
      
      // Parse JSON response
      const data = await response.json();
      return data;
    } catch (error) {
      return handleError(error, actionName);
    }
  };

  return {
    /**
     * Get all products
     * @returns {Promise<Object>} Promise with products data
     */
    getAllProducts: async function() {
      return apiCall(`${baseUrl}/products`, {}, 'fetching products');
    },

    /**
     * Get a specific product by ID
     * @param {string} productId - The ID of the product to fetch
     * @returns {Promise<Object>} Promise with product data
     */
    getProduct: async function(productId) {
      if (!productId) {
        return { status: 'error', message: 'Product ID is required' };
      }
      return apiCall(`${baseUrl}/products/${productId}`, {}, `fetching product ${productId}`);
    },

    /**
     * Create a new product
     * @param {Object} productData - The product data
     * @returns {Promise<Object>} Promise with created product data
     */
    createProduct: async function(productData) {
      if (!productData || !productData.name || !productData.price) {
        return { status: 'error', message: 'Product data is incomplete' };
      }
      
      const options = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(productData),
      };
      
      return apiCall(`${baseUrl}/products`, options, 'creating product');
    },

    /**
     * Update an existing product
     * @param {string} productId - The ID of the product to update
     * @param {Object} updates - The updates to apply
     * @returns {Promise<Object>} Promise with updated product data
     */
    updateProduct: async function(productId, updates) {
      if (!productId || !updates) {
        return { status: 'error', message: 'Product ID and update data are required' };
      }
      
      const options = {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      };
      
      return apiCall(`${baseUrl}/products/${productId}`, options, `updating product ${productId}`);
    },

    /**
     * Delete a product
     * @param {string} productId - The ID of the product to delete
     * @returns {Promise<Object>} Promise with result data
     */
    deleteProduct: async function(productId) {
      if (!productId) {
        return { status: 'error', message: 'Product ID is required' };
      }
      
      const options = {
        method: 'DELETE',
      };
      
      return apiCall(`${baseUrl}/products/${productId}`, options, `deleting product ${productId}`);
    },

    /**
     * Upload multiple images for a product
     * @param {string} productId - The ID of the product
     * @param {FileList} files - The images to upload
     * @returns {Promise<Object>} Promise with upload result
     */
    uploadProductImages: async function(productId, files) {
      if (!productId || !files || files.length === 0) {
        return { status: 'error', message: 'Product ID and files are required' };
      }
      
      try {
        const formData = new FormData();
        
        // Validate each file is an image before adding to FormData
        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          if (!file.type.match('image.*')) {
            return { status: 'error', message: `File "${file.name}" is not an image` };
          }
          formData.append('files[]', file);
        }
        
        const options = {
          method: 'POST',
          body: formData,
          // Don't set Content-Type header, the browser will set it with the boundary
        };
        
        return apiCall(
          `${baseUrl}/products/${productId}/images/upload/multiple`, 
          options, 
          `uploading images for product ${productId}`
        );
      } catch (error) {
        return handleError(error, `uploading images for product ${productId}`);
      }
    },

    /**
     * Set an image as the primary image for a product
     * @param {string} imageId - The ID of the image
     * @returns {Promise<Object>} Promise with result data
     */
    setPrimaryImage: async function(imageId) {
      if (!imageId) {
        return { status: 'error', message: 'Image ID is required' };
      }
      
      const options = {
        method: 'PUT',
      };
      
      return apiCall(`${baseUrl}/images/${imageId}/set-primary`, options, `setting image ${imageId} as primary`);
    },

    /**
     * Delete a product image
     * @param {string} imageId - The ID of the image to delete
     * @returns {Promise<Object>} Promise with result data
     */
    deleteProductImage: async function(imageId) {
      if (!imageId) {
        return { status: 'error', message: 'Image ID is required' };
      }
      
      const options = {
        method: 'DELETE',
      };
      
      return apiCall(`${baseUrl}/images/${imageId}`, options, `deleting image ${imageId}`);
    },

    /**
     * Get URL for a product image
     * @param {string} imagePath - The relative path
     * @returns {string|null} Full URL to the image or null if no path provided
     */
    getImageUrl: function(imagePath) {
      if (!imagePath) return null;
      return `${baseUrl}/storage/serve/${imagePath}`;
    },

    /**
     * Search for products
     * @param {string} query - The search query
     * @returns {Promise<Object>} Promise with search results
     */
    searchProducts: async function(query) {
      if (!query) {
        return { status: 'error', message: 'Search query is required' };
      }
      
      return apiCall(
        `${baseUrl}/products/search?q=${encodeURIComponent(query)}`,
        {},
        'searching products'
      );
    },

    /**
     * Get all categories
     * @returns {Promise<Object>} Promise with categories data
     */
    getAllCategories: async function() {
      return apiCall(`${baseUrl}/categories`, {}, 'fetching categories');
    },

    /**
     * Get all manufacturers
     * @returns {Promise<Object>} Promise with manufacturers data
     */
    getAllManufacturers: async function() {
      return apiCall(`${baseUrl}/manufacturers`, {}, 'fetching manufacturers');
    },
    
    /**
     * Get products by category
     * @param {string} category - The category to filter by
     * @returns {Promise<Object>} Promise with products in category
     */
    getProductsByCategory: async function(category) {
      if (!category) {
        return { status: 'error', message: 'Category is required' };
      }
      
      return apiCall(
        `${baseUrl}/products/category/${encodeURIComponent(category)}`,
        {},
        `fetching products in category ${category}`
      );
    },
    
    /**
     * Get products by manufacturer
     * @param {string} manufacturer - The manufacturer to filter by
     * @returns {Promise<Object>} Promise with products by manufacturer
     */
    getProductsByManufacturer: async function(manufacturer) {
      if (!manufacturer) {
        return { status: 'error', message: 'Manufacturer is required' };
      }
      
      return apiCall(
        `${baseUrl}/products/manufacturer/${encodeURIComponent(manufacturer)}`,
        {},
        `fetching products by manufacturer ${manufacturer}`
      );
    },
    
    /**
     * Check API health status
     * @returns {Promise<Object>} Promise with API health information
     */
    checkHealth: async function() {
      return apiCall(`${baseUrl}/health`, {}, 'checking API health');
    }
  };
})();