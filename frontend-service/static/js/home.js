// home.js - Specific JavaScript for the homepage

// Function to load and create category grid with icons
function loadCategoryGrid() {
    fetch('/api/frontend/categories')
        .then(response => response.json())
        .then(data => {
            const categoryGrid = document.getElementById('categoryGrid');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                categoryGrid.innerHTML = '';
                
                data.data.forEach(category => {
                    // Create category card with icon
                    const categoryCol = document.createElement('div');
                    categoryCol.className = 'col-lg-2 col-md-3 col-sm-4 col-6 mb-4';
                    
                    // Generate icon name based on category (simple logic)
                    let iconClass = 'bi-box';
                    if (category.toLowerCase().includes('electronics')) iconClass = 'bi-laptop';
                    else if (category.toLowerCase().includes('cloth')) iconClass = 'bi-bag';
                    else if (category.toLowerCase().includes('home')) iconClass = 'bi-house';
                    else if (category.toLowerCase().includes('book')) iconClass = 'bi-book';
                    else if (category.toLowerCase().includes('toy')) iconClass = 'bi-controller';
                    else if (category.toLowerCase().includes('sport')) iconClass = 'bi-bicycle';
                    else if (category.toLowerCase().includes('beauty')) iconClass = 'bi-droplet';
                    else if (category.toLowerCase().includes('food')) iconClass = 'bi-cup-hot';
                    
                    categoryCol.innerHTML = `
                        <a href="/products?category=${encodeURIComponent(category)}" class="text-decoration-none text-dark">
                            <div class="card h-100 text-center category-card border-0">
                                <div class="card-body">
                                    <div class="category-icon-wrapper mb-3">
                                        <i class="bi ${iconClass} display-4"></i>
                                    </div>
                                    <h6 class="card-title">${category}</h6>
                                </div>
                            </div>
                        </a>
                    `;
                    
                    categoryGrid.appendChild(categoryCol);
                });
            } else {
                categoryGrid.innerHTML = '<div class="col-12 text-center">No categories available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading categories:', error);
            document.getElementById('categoryGrid').innerHTML = 
                '<div class="col-12 text-center">Failed to load categories. Please try again later.</div>';
        });
}

// Function to load combined news and articles for the tech news grid
function loadTechNewsGrid() {
    // First, try to get latest news
    fetch('/api/frontend/latest-news?limit=2')
        .then(response => response.json())
        .then(newsData => {
            let newsItems = [];
            if (newsData.status === 'success' && newsData.data && newsData.data.length > 0) {
                newsItems = newsData.data.map(item => {
                    return {
                        ...item,
                        type: 'news'
                    };
                });
            }
            
            // Then get featured articles
            fetch('/api/frontend/featured-articles?limit=2')
                .then(response => response.json())
                .then(articlesData => {
                    let articleItems = [];
                    if (articlesData.status === 'success' && articlesData.data && articlesData.data.length > 0) {
                        articleItems = articlesData.data.map(item => {
                            return {
                                ...item,
                                type: 'article'
                            };
                        });
                    }
                    
                    // Combine news and articles
                    const combinedItems = [...newsItems, ...articleItems];
                    
                    // Display in grid
                    displayTechNewsGrid(combinedItems);
                })
                .catch(error => {
                    console.error('Error loading articles:', error);
                    // Still try to display news items if we have them
                    displayTechNewsGrid(newsItems);
                });
        })
        .catch(error => {
            console.error('Error loading news:', error);
            document.getElementById('techNewsGrid').innerHTML = 
                '<div class="col-12 text-center">Failed to load news content. Please try again later.</div>';
        });
}

// Function to display the tech news grid
function displayTechNewsGrid(items) {
    const techNewsGrid = document.getElementById('techNewsGrid');
    
    if (items && items.length > 0) {
        techNewsGrid.innerHTML = '';
        
        // Only show up to 4 items in the grid
        const itemsToShow = items.slice(0, 4);
        
        itemsToShow.forEach(item => {
            // Get the image URL if available
            let imageUrl = 'https://placehold.co/600x400?text=No+Image';
            if (item.featured_image && item.featured_image.path) {
                imageUrl = `/api/media/serve/${item.featured_image.path}`;
            }
            
            // Format the date
            const publishedDate = item.published_date ? new Date(item.published_date).toLocaleDateString() : '';
            
            // Create the card
            const col = document.createElement('div');
            col.className = 'col-lg-3 col-md-6 mb-4';
            
            col.innerHTML = `
                <div class="card h-100 news-card">
                    <img src="${imageUrl}" class="card-img-top news-thumbnail" alt="${item.title || 'News image'}">
                    <div class="card-body">
                        <h5 class="card-title text-truncate">${item.title || 'Untitled'}</h5>
                        <p class="card-text news-excerpt">${item.summary || ''}</p>
                    </div>
                    <div class="card-footer bg-white border-0 d-flex justify-content-between align-items-center">
                        <small class="text-muted">${publishedDate}</small>
                        <span class="badge bg-${item.type === 'news' ? 'info' : 'primary'}">${item.type}</span>
                    </div>
                    <a href="/articles/${item.article_id}" class="stretched-link"></a>
                </div>
            `;
            
            techNewsGrid.appendChild(col);
        });
        
        // If we have less than 4 items, fill with placeholders
        if (itemsToShow.length < 2) {
            const placeholdersNeeded = 4 - itemsToShow.length;
            for (let i = 0; i < placeholdersNeeded; i++) {
                const placeholderCol = document.createElement('div');
                placeholderCol.className = 'col-lg-3 col-md-6 mb-4';
                
                placeholderCol.innerHTML = `
                    <div class="card h-100 news-card">
                        <div class="bg-light placeholder-glow" style="height: 180px;">
                            <span class="placeholder col-12 h-100"></span>
                        </div>
                        <div class="card-body">
                            <h5 class="card-title placeholder-glow">
                                <span class="placeholder col-6"></span>
                            </h5>
                            <p class="card-text placeholder-glow">
                                <span class="placeholder col-7"></span>
                                <span class="placeholder col-4"></span>
                                <span class="placeholder col-4"></span>
                                <span class="placeholder col-6"></span>
                            </p>
                        </div>
                        <div class="card-footer bg-white border-0">
                            <span class="placeholder col-3"></span>
                        </div>
                    </div>
                `;
                
                techNewsGrid.appendChild(placeholderCol);
            }
        }
    } else {
        // No items available
        techNewsGrid.innerHTML = `
            <div class="col-12 text-center">
                <p class="mb-0">No news or articles available at this time.</p>
                <p class="mt-2 mb-0">Check back later for updates!</p>
            </div>
        `;
    }
}

// Function to load featured products
function loadFeaturedProducts() {
    fetch('/api/frontend/featured-products?limit=8')
        .then(response => response.json())
        .then(data => {
            const productsContainer = document.getElementById('featuredProducts');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                productsContainer.innerHTML = '';
                
                data.data.forEach(product => {
                    const productCard = createProductCard(product);
                    productsContainer.appendChild(productCard);
                });
            } else {
                productsContainer.innerHTML = '<div class="col-12 text-center">No featured products available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading featured products:', error);
            document.getElementById('featuredProducts').innerHTML = 
                '<div class="col-12 text-center">Failed to load featured products. Please try again later.</div>';
        });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize cart if user is logged in
    initializeCart();
    
    // Load category grid
    loadCategoryGrid();
    
    // Load featured products
    loadFeaturedProducts();
    
    // Load tech news grid (combined news and articles)
    loadTechNewsGrid();
});