// Main JavaScript for E-commerce Homepage

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initializeCart();
    setupProductInteractions();
    setupNewsletterForm();
    
    // Enable Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Shopping Cart Functionality
function initializeCart() {
    // Get cart from localStorage or initialize empty cart
    let cart = JSON.parse(localStorage.getItem('e-shop-cart')) || { items: [], total: 0 };
    
    // Update cart count in header
    updateCartCount(cart);
    
    // Setup add to cart buttons
    const addToCartButtons = document.querySelectorAll('.add-to-cart');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.getAttribute('data-product-id');
            addItemToCart(productId);
        });
    });
    
    // Setup cart page if it exists
    const cartContainer = document.getElementById('cart-items-container');
    if (cartContainer) {
        renderCartItems(cartContainer, cart);
    }
}

function addItemToCart(productId) {
    // Fetch product details from API
    fetch(`/api/products/${productId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.data && data.data.length > 0) {
                const product = data.data[0];
                
                // Get current cart
                let cart = JSON.parse(localStorage.getItem('e-shop-cart')) || { items: [], total: 0 };
                
                // Check if product already in cart
                const existingItemIndex = cart.items.findIndex(item => item.product_id === productId);
                
                if (existingItemIndex >= 0) {
                    // Increase quantity
                    cart.items[existingItemIndex].quantity += 1;
                } else {
                    // Add new item
                    cart.items.push({
                        product_id: product.product_id,
                        name: product.name,
                        price: product.price,
                        image_url: product.image_url || '',
                        quantity: 1
                    });
                }
                
                // Recalculate total
                cart.total = calculateCartTotal(cart.items);
                
                // Save to localStorage
                localStorage.setItem('e-shop-cart', JSON.stringify(cart));
                
                // Update UI
                updateCartCount(cart);
                showToast('Product added to cart!', 'success');
            } else {
                showToast('Failed to add product to cart', 'danger');
            }
        })
        .catch(error => {
            console.error('Error adding to cart:', error);
            showToast('Failed to add product to cart', 'danger');
        });
}

function calculateCartTotal(items) {
    return items.reduce((total, item) => total + (item.price * item.quantity), 0);
}

function updateCartCount(cart) {
    const cartCountElements = document.querySelectorAll('.cart-count');
    const itemCount = cart.items.reduce((count, item) => count + item.quantity, 0);
    
    cartCountElements.forEach(element => {
        element.textContent = itemCount;
    });
}

function renderCartItems(container, cart) {
    if (cart.items.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Your cart is empty</div>';
        document.getElementById('checkout-button').classList.add('disabled');
        document.getElementById('cart-summary').classList.add('d-none');
        return;
    }
    
    // Clear container
    container.innerHTML = '';
    
    // Render each cart item
    cart.items.forEach(item => {
        const cartItemElement = document.createElement('div');
        cartItemElement.className = 'cart-item d-flex align-items-center';
        cartItemElement.innerHTML = `
            <div class="me-3">
                <img src="${item.image_url || '/static/images/placeholder.png'}" alt="${item.name}" class="rounded">
            </div>
            <div class="flex-grow-1">
                <h5 class="mb-1">${item.name}</h5>
                <p class="mb-0 text-muted">${item.price.toFixed(2)} each</p>
            </div>
            <div class="quantity-controls d-flex align-items-center me-3">
                <button class="btn btn-sm btn-outline-secondary decrease-quantity" data-product-id="${item.product_id}">-</button>
                <span class="mx-2">${item.quantity}</span>
                <button class="btn btn-sm btn-outline-secondary increase-quantity" data-product-id="${item.product_id}">+</button>
            </div>
            <div class="item-total me-3">
                <strong>${(item.price * item.quantity).toFixed(2)}</strong>
            </div>
            <div>
                <button class="btn btn-sm btn-danger remove-item" data-product-id="${item.product_id}">✕</button>
            </div>
        `;
        container.appendChild(cartItemElement);
    });
    
    // Setup event listeners for cart item controls
    setupCartItemControls();
    
    // Update total
    const cartTotalElement = document.getElementById('cart-total');
    if (cartTotalElement) {
        cartTotalElement.textContent = `${cart.total.toFixed(2)}`;
    }
    
    // Enable checkout button
    document.getElementById('checkout-button').classList.remove('disabled');
    document.getElementById('cart-summary').classList.remove('d-none');
}