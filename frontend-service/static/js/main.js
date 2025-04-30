// Helper function to format price
function formatPrice(price) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(price);
}

// Function to load featured products
function loadFeaturedProducts() {
    fetch('/api/frontend/featured-products?limit=6')
        .then(response => response.json())
        .then(data => {
            const featuredContainer = document.getElementById('featuredProducts');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                featuredContainer.innerHTML = '';
                
                data.data.forEach(product => {
                    const productCard = createProductCard(product);
                    featuredContainer.appendChild(productCard);
                });
            } else {
                featuredContainer.innerHTML = '<div class="col-12 text-center">No featured products available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading featured products:', error);
            document.getElementById('featuredProducts').innerHTML = 
                '<div class="col-12 text-center">Failed to load featured products. Please try again later.</div>';
        });
}

// Function to load all promotional products
function loadPromotedProducts() {
    // Get all products with active promotions
    fetch('/api/frontend/products')
        .then(response => response.json())
        .then(data => {
            const promotedContainer = document.getElementById('promotedProducts');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                // Filter to only products with promotions
                const promotedProducts = data.data.filter(product => product.has_promotion);
                
                if (promotedProducts.length > 0) {
                    promotedContainer.innerHTML = '';
                    
                    // Limit to 4 promoted products
                    promotedProducts.slice(0, 4).forEach(product => {
                        const productCard = createProductCard(product);
                        promotedContainer.appendChild(productCard);
                    });
                } else {
                    promotedContainer.innerHTML = '<div class="col-12 text-center">No special offers available.</div>';
                }
            } else {
                promotedContainer.innerHTML = '<div class="col-12 text-center">No special offers available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading promoted products:', error);
            document.getElementById('promotedProducts').innerHTML = 
                '<div class="col-12 text-center">Failed to load special offers. Please try again later.</div>';
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

// Function to create a product card
function createProductCard(product) {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6';
    
    // Determine if there's a promotion and format prices
    const hasPromotion = product.has_promotion;
    const regularPrice = formatPrice(product.price);
    const discountedPrice = hasPromotion ? formatPrice(product.discounted_price) : '';
    
    // Get product image URL or use a placeholder
    const imageUrl = product.image_url 
        ? `/api/storage/serve/${product.image_url}` 
        : 'https://placehold.co/300x300?text=No+Image';
    
    col.innerHTML = `
        <div class="card h-100 product-card">
            <div class="position-relative">
                <img src="${imageUrl}" class="card-img-top" alt="${product.name}">
                ${hasPromotion ? `<div class="badge bg-danger position-absolute top-0 end-0 m-2">SALE</div>` : ''}
            </div>
            <div class="card-body">
                <h5 class="card-title">${product.name}</h5>
                <p class="card-text text-truncate">${product.description}</p>
                <div class="d-flex justify-content-between align-items-center">
                    <div class="price-container">
                        ${hasPromotion ? `
                            <span class="text-muted text-decoration-line-through">${regularPrice}</span>
                            <span class="text-danger fw-bold ms-2">${discountedPrice}</span>
                        ` : `
                            <span class="fw-bold">${regularPrice}</span>
                        `}
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline-primary">Add to Cart</button>
                    </div>
                </div>
            </div>
            <div class="card-footer bg-white">
                <small class="text-muted">Category: ${product.category || 'Uncategorized'}</small>
            </div>
        </div>
    `;
    
    return col;
}