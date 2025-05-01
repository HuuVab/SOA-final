// Helper function to format price
function formatPrice(price) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(price);
}

// Function to load all products
function loadAllProducts() {
    fetch('/api/frontend/products')
        .then(response => response.json())
        .then(data => {
            const productsContainer = document.getElementById('allProducts');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                productsContainer.innerHTML = '';
                
                // Display all products without filtering
                data.data.forEach(product => {
                    const productCard = createProductCard(product);
                    productsContainer.appendChild(productCard);
                });
            } else {
                productsContainer.innerHTML = '<div class="col-12 text-center">No products available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading products:', error);
            document.getElementById('allProducts').innerHTML = 
                '<div class="col-12 text-center">Failed to load products. Please try again later.</div>';
        });
}

// Function to load categories
function loadCategories() {
    fetch('/api/frontend/categories')
        .then(response => response.json())
        .then(data => {
            const categoryContainer = document.getElementById('categoryList');
            const categoriesMenu = document.getElementById('categoriesMenu');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                // Update category list on homepage
                categoryContainer.innerHTML = '';
                
                data.data.forEach(category => {
                    // Create category card for homepage
                    const categoryCol = document.createElement('div');
                    categoryCol.className = 'col-md-4 col-sm-6';
                    
                    categoryCol.innerHTML = `
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h5 class="card-title">${category}</h5>
                                <a href="/products?category=${encodeURIComponent(category)}" class="btn btn-primary">View Products</a>
                            </div>
                        </div>
                    `;
                    
                    categoryContainer.appendChild(categoryCol);
                    
                    // Add to dropdown menu
                    const menuItem = document.createElement('li');
                    menuItem.innerHTML = `<a class="dropdown-item" href="/products?category=${encodeURIComponent(category)}">${category}</a>`;
                    categoriesMenu.appendChild(menuItem);
                });
            } else {
                categoryContainer.innerHTML = '<div class="col-12 text-center">No categories available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading categories:', error);
            document.getElementById('categoryList').innerHTML = 
                '<div class="col-12 text-center">Failed to load categories. Please try again later.</div>';
        });
}

// Function to create a product card with hover slideshow and loading bar
function createProductCard(product) {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6 mb-4';
    
    // Define pricing variables
    const regularPrice = formatPrice(product.price);
    const hasPromotion = product.has_promotion || false;
    const discountedPrice = product.discounted_price ? formatPrice(product.discounted_price) : regularPrice;

    // Generate a unique ID for this card
    const cardId = `product-${product.product_id}`;
    
    // Create image container HTML
    let imageHTML = '';
    let imageList = [];
    
    // Check if product has images array directly
    if (product.images && product.images.length > 0) {
        // Direct images array
        imageList = product.images;
    } else if (product.promotion && product.promotion.product && product.promotion.product.images) {
        // Images in promotion.product (for promoted products)
        imageList = product.promotion.product.images;
    } else if (product.data && Array.isArray(product.data)) {
        // Images from direct API response
        imageList = product.data;
    }
    
    if (imageList.length > 0) {
        // Create container for the images
        imageHTML = `<div class="product-image-container" id="images-${cardId}">`;
        
        // Add each image
        imageList.forEach((image, index) => {
            const imagePath = image.path;
            const imageSrc = `/api/storage/serve/${imagePath}`;
            
            imageHTML += `
                <img src="${imageSrc}" 
                     class="product-image ${index === 0 ? 'active' : ''}" 
                     alt="${image.alt_text || 'Product image'}"
                     data-index="${index}">
            `;
        });
        
        // Add loading bar for multi-image products
        if (imageList.length > 1) {
            imageHTML += `<div class="image-progress-container"><div class="image-progress-bar" id="progress-${cardId}"></div></div>`;
        }
        
        imageHTML += '</div>';
    } else {
        // Fallback for products without images
        const imgSrc = product.image_url 
            ? `/api/storage/serve/${product.image_url}` 
            : 'https://placehold.co/300x300?text=No+Image';
            
        imageHTML = `<img src="${imgSrc}" class="card-img-top" alt="${product.name || 'Product'}">`;
    }
    
    // Create the card HTML
    col.innerHTML = `
        <div class="card h-100 product-card" id="${cardId}">
            <div class="position-relative">
                ${imageHTML}
                ${hasPromotion ? `<div class="badge bg-danger position-absolute top-0 end-0 m-2">SALE</div>` : ''}
            </div>
            <div class="card-body">
                <h5 class="card-title">${product.name || ''}</h5>
                <p class="card-text text-truncate">${product.description || ''}</p>
                <div class="d-flex justify-content-between align-items-center">
                    <div class="price-container">
                        ${hasPromotion ? `
                            <span class="text-muted text-decoration-line-through">${regularPrice}</span>
                            <span class="text-danger fw-bold ms-2">${discountedPrice}</span>
                        ` : `
                            <span class="fw-bold">${regularPrice || '$0.00'}</span>
                        `}
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline-primary add-to-cart-btn" data-product-id="${product.product_id}">Add to Cart</button>
                    </div>
                </div>
            </div>
            <div class="card-footer bg-white">
                <small class="text-muted">Category: ${product.category || 'Uncategorized'}</small>
            </div>
        </div>
    `;
    
    // Add to DOM first, then we can attach event listeners
    setTimeout(() => {
        if (imageList.length > 1) {
            const card = document.getElementById(cardId);
            if (!card) return;
            
            const imageContainer = document.getElementById(`images-${cardId}`);
            if (!imageContainer) return;
            
            const images = imageContainer.querySelectorAll('.product-image');
            if (images.length === 0) return;
            
            const progressBar = document.getElementById(`progress-${cardId}`);
            if (!progressBar) return;
            
            let currentIndex = 0;
            let animationId;
            let startTime;
            const slideDuration = 3000; // 3 seconds per slide
            
            // Animation function for the loading bar
            function animateProgress(timestamp) {
                if (!startTime) startTime = timestamp;
                const elapsed = timestamp - startTime;
                const progress = Math.min(elapsed / slideDuration * 100, 100);
                
                // Update progress bar width
                progressBar.style.width = `${progress}%`;
                
                // If completed, change image
                if (progress === 100) {
                    // Reset progress bar
                    progressBar.style.width = '0%';
                    startTime = null;
                    
                    // Hide current image
                    images[currentIndex].classList.remove('active');
                    
                    // Move to next image
                    currentIndex = (currentIndex + 1) % images.length;
                    
                    // Show new image
                    images[currentIndex].classList.add('active');
                    
                    // Continue animation
                    animationId = requestAnimationFrame(animateProgress);
                } else {
                    // Continue animation
                    animationId = requestAnimationFrame(animateProgress);
                }
            }
            
            // Start slideshow on hover
            card.addEventListener('mouseenter', () => {
                startTime = null;
                progressBar.style.width = '0%';
                progressBar.classList.add('active');
                animationId = requestAnimationFrame(animateProgress);
            });
            
            // Stop slideshow when mouse leaves
            card.addEventListener('mouseleave', () => {
                // Cancel animation
                cancelAnimationFrame(animationId);
                progressBar.classList.remove('active');
                progressBar.style.width = '0%';
                
                // Reset to first image
                images.forEach(img => img.classList.remove('active'));
                images[0].classList.add('active');
                currentIndex = 0;
            });
        }
        
        // Add to cart functionality
        const addToCartBtn = col.querySelector('.add-to-cart-btn');
        if (addToCartBtn) {
            addToCartBtn.addEventListener('click', function(event) {
                event.preventDefault();
                event.stopPropagation();
                addToCart(product.product_id);
            });
        }
    }, 100);
    
    return col;
}

async function addToCart(productId, quantity = 1) {
    const token = localStorage.getItem('ecomm_auth_token');
    
    if (!token) {
        // Show login modal if not logged in
        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
        loginModal.show();
        return;
    }
    
    try {
        // Add product to cart
        const response = await fetch('/api/cart/items', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                product_id: productId,
                quantity: quantity
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            // Update cart count
            updateCartCount(data.cart.item_count);
            
            // Show success toast
            showToast('Product added to cart', 'success');
        } else {
            showToast(data.message || 'Failed to add product to cart', 'danger');
        }
    } catch (error) {
        console.error('Error adding product to cart:', error);
        showToast('An error occurred. Please try again.', 'danger');
    }
}
function updateCartCount(count) {
    const cartCountElement = document.getElementById('cartCount');
    if (cartCountElement) {
        cartCountElement.textContent = count || '0';
        
        // Highlight the cart count when updated
        cartCountElement.classList.add('highlight');
        setTimeout(() => {
            cartCountElement.classList.remove('highlight');
        }, 1000);
    }
}

// Function to show toast notification
function showToast(message, type = 'info') {
    // Check if toast container exists, if not create it
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.className = `toast show border-${type}`;
    toast.role = 'alert';
    toast.ariaLive = 'assertive';
    toast.ariaAtomic = 'true';
    toast.id = toastId;
    
    toast.innerHTML = `
        <div class="toast-header">
            <strong class="me-auto text-${type}">${type === 'success' ? 'Success' : type === 'danger' ? 'Error' : 'Notification'}</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    // Add toast to container
    toastContainer.appendChild(toast);
    
    // Auto-hide toast after 3 seconds
    setTimeout(() => {
        const toastElement = document.getElementById(toastId);
        if (toastElement) {
            toastElement.classList.remove('show');
            setTimeout(() => {
                toastElement.remove();
            }, 500);
        }
    }, 3000);
    
    // Add close button functionality
    const closeButton = toast.querySelector('.btn-close');
    closeButton.addEventListener('click', function() {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 500);
    });
}

// Function to load and initialize cart count
async function initializeCart() {
    const token = localStorage.getItem('ecomm_auth_token');
    if (!token) return;
    
    try {
        const response = await fetch('/api/cart', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            updateCartCount(data.cart.item_count);
        }
    } catch (error) {
        console.error('Error initializing cart:', error);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize cart if user is logged in
    initializeCart();
});