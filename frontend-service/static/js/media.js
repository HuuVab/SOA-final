// media.js - Core functions for loading and displaying news and articles

// Function to load featured articles for dedicated articles page
function loadFeaturedArticles() {
    fetch('/api/frontend/featured-articles?limit=6')
        .then(response => response.json())
        .then(data => {
            const articlesContainer = document.getElementById('featuredArticles');
            if (!articlesContainer) return; // Exit if container doesn't exist
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                articlesContainer.innerHTML = '';
                
                data.data.forEach(article => {
                    const articleCard = createArticleCard(article);
                    articlesContainer.appendChild(articleCard);
                });
            } else {
                articlesContainer.innerHTML = '<div class="col-12 text-center">No featured articles available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading featured articles:', error);
            const container = document.getElementById('featuredArticles');
            if (container) {
                container.innerHTML = '<div class="col-12 text-center">Failed to load featured articles. Please try again later.</div>';
            }
        });
}

// Function to load latest news for the news page
function loadLatestNews() {
    fetch('/api/frontend/latest-news?limit=6')
        .then(response => response.json())
        .then(data => {
            const newsContainer = document.getElementById('latestNews');
            if (!newsContainer) return; // Exit if container doesn't exist
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                newsContainer.innerHTML = '';
                
                data.data.forEach(newsItem => {
                    const newsCard = createNewsCard(newsItem);
                    newsContainer.appendChild(newsCard);
                });
            } else {
                newsContainer.innerHTML = '<div class="col-12 text-center">No news available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading latest news:', error);
            const container = document.getElementById('latestNews');
            if (container) {
                container.innerHTML = '<div class="col-12 text-center">Failed to load latest news. Please try again later.</div>';
            }
        });
}

// Function to create an article card for listing pages
function createArticleCard(article) {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6 mb-4';
    
    // Get the featured image if available
    let imageUrl = 'https://placehold.co/600x400?text=No+Image';
    if (article.featured_image && article.featured_image.path) {
        imageUrl = `/api/media/serve/${article.featured_image.path}`;
    }
    
    // Format the date
    const publishedDate = article.published_date ? new Date(article.published_date).toLocaleDateString() : 'Unpublished';
    
    // Create the card HTML
    col.innerHTML = `
        <div class="card h-100 article-card">
            <img src="${imageUrl}" class="card-img-top" alt="${article.title || 'Article image'}">
            <div class="card-body">
                <h5 class="card-title">${article.title || 'Untitled Article'}</h5>
                <p class="card-text">${article.summary || ''}</p>
            </div>
            <div class="card-footer bg-white d-flex justify-content-between align-items-center">
                <small class="text-muted">${publishedDate}</small>
                <a href="/articles/${article.article_id}" class="btn btn-sm btn-primary">Read More</a>
            </div>
        </div>
    `;
    
    return col;
}

// Function to create a news card for the news page
function createNewsCard(newsItem) {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6 mb-4';
    
    // Get the featured image if available
    let imageUrl = 'https://placehold.co/600x400?text=No+Image';
    if (newsItem.featured_image && newsItem.featured_image.path) {
        imageUrl = `/api/media/serve/${newsItem.featured_image.path}`;
    }
    
    // Format the date
    const publishedDate = newsItem.published_date ? new Date(newsItem.published_date).toLocaleDateString() : 'Unpublished';
    
    // Create the card HTML
    col.innerHTML = `
        <div class="card h-100 news-card-list">
            <div class="card-header bg-info text-white">Latest News</div>
            <img src="${imageUrl}" class="card-img-top" alt="${newsItem.title || 'News image'}">
            <div class="card-body">
                <h5 class="card-title">${newsItem.title || 'Untitled News'}</h5>
                <p class="card-text">${newsItem.summary || ''}</p>
            </div>
            <div class="card-footer bg-white d-flex justify-content-between align-items-center">
                <small class="text-muted">${publishedDate}</small>
                <a href="/articles/${newsItem.article_id}" class="btn btn-sm btn-outline-info">Read More</a>
            </div>
        </div>
    `;
    
    return col;
}

// Load all articles for the articles page
function loadAllArticles() {
    const searchParams = new URLSearchParams(window.location.search);
    const tag = searchParams.get('tag');
    const query = searchParams.get('q');
    
    let url = '/api/media/articles?type=article&status=published&limit=12';
    if (tag) url += `&tag=${encodeURIComponent(tag)}`;
    if (query) url += `&q=${encodeURIComponent(query)}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const articlesContainer = document.getElementById('allArticles');
            if (!articlesContainer) return; // Exit if container doesn't exist
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                articlesContainer.innerHTML = '';
                
                data.data.forEach(article => {
                    const articleCard = createArticleCard(article);
                    articlesContainer.appendChild(articleCard);
                });
                
                // Create pagination if needed
                if (data.total > data.limit) {
                    createPagination('articlesPagination', data.total, data.limit, data.offset);
                }
            } else {
                articlesContainer.innerHTML = '<div class="col-12 text-center">No articles available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading articles:', error);
            const container = document.getElementById('allArticles');
            if (container) {
                container.innerHTML = '<div class="col-12 text-center">Failed to load articles. Please try again later.</div>';
            }
        });
}

// Load all news for the news page
function loadAllNews() {
    const searchParams = new URLSearchParams(window.location.search);
    const query = searchParams.get('q');
    
    let url = '/api/media/articles?type=news&status=published&limit=12';
    if (query) url += `&q=${encodeURIComponent(query)}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const newsContainer = document.getElementById('allNews');
            if (!newsContainer) return; // Exit if container doesn't exist
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                newsContainer.innerHTML = '';
                
                data.data.forEach(newsItem => {
                    const newsCard = createNewsCard(newsItem);
                    newsContainer.appendChild(newsCard);
                });
                
                // Create pagination if needed
                if (data.total > data.limit) {
                    createPagination('newsPagination', data.total, data.limit, data.offset);
                }
            } else {
                newsContainer.innerHTML = '<div class="col-12 text-center">No news available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading news:', error);
            const container = document.getElementById('allNews');
            if (container) {
                container.innerHTML = '<div class="col-12 text-center">Failed to load news. Please try again later.</div>';
            }
        });
}

// Load article details for the article detail page
function loadArticleDetails(articleId) {
    fetch(`/api/media/articles/${articleId}`)
        .then(response => response.json())
        .then(data => {
            const articleContainer = document.getElementById('articleDetail');
            if (!articleContainer) return; // Exit if container doesn't exist
            
            if (data.status === 'success' && data.data) {
                const article = data.data;
                
                // Get the featured image if available
                let imageUrl = '';
                if (article.featured_image && article.featured_image.path) {
                    imageUrl = `/api/media/serve/${article.featured_image.path}`;
                }
                
                // Format the date
                const publishedDate = article.published_date ? new Date(article.published_date).toLocaleDateString() : 'Unpublished';
                
                let tagsHtml = '';
                if (article.tags && article.tags.length > 0) {
                    tagsHtml = '<div class="mt-3"><strong>Tags:</strong> ';
                    article.tags.forEach((tag, index) => {
                        tagsHtml += `<span class="badge bg-secondary me-1">${tag.name}</span>`;
                    });
                    tagsHtml += '</div>';
                }
                
                let imagesHtml = '';
                if (article.images && article.images.length > 1) {
                    imagesHtml = '<div class="mt-4 mb-4"><h5>Gallery</h5><div class="row">';
                    article.images.forEach(image => {
                        if (image.image_id !== article.featured_image_id) {
                            imagesHtml += `
                                <div class="col-md-4 col-sm-6 mb-3">
                                    <img src="/api/media/serve/${image.path}" 
                                         class="img-fluid rounded" 
                                         alt="${image.alt_text || 'Article image'}">
                                    <small class="text-muted d-block mt-1">${image.caption || ''}</small>
                                </div>
                            `;
                        }
                    });
                    imagesHtml += '</div></div>';
                }
                
                articleContainer.innerHTML = `
                    <div class="article-header mb-4">
                        <h1>${article.title || 'Untitled Article'}</h1>
                        <div class="article-meta d-flex justify-content-between align-items-center">
                            <div>
                                <span class="text-muted">By ${article.author || 'Unknown'}</span>
                                <span class="text-muted mx-2">|</span>
                                <span class="text-muted">Published: ${publishedDate}</span>
                            </div>
                            <span class="badge bg-${article.type === 'news' ? 'info' : 'primary'}">${article.type}</span>
                        </div>
                    </div>
                    
                    ${imageUrl ? `
                        <div class="featured-image mb-4">
                            <img src="${imageUrl}" class="img-fluid rounded" alt="${article.title}">
                        </div>
                    ` : ''}
                    
                    <div class="article-summary mb-4">
                        <p class="lead">${article.summary || ''}</p>
                    </div>
                    
                    <div class="article-content mb-4">
                        ${article.content || ''}
                    </div>
                    
                    ${imagesHtml}
                    
                    ${tagsHtml}
                `;
                
                // Also load related articles
                loadRelatedArticles(article.article_id, article.tags);
            } else {
                articleContainer.innerHTML = '<div class="alert alert-danger">Article not found or unavailable.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading article details:', error);
            const container = document.getElementById('articleDetail');
            if (container) {
                container.innerHTML = 
                    '<div class="alert alert-danger">Failed to load article. Please try again later.</div>';
            }
        });
}

// Load related articles based on tags
function loadRelatedArticles(currentArticleId, tags) {
    const relatedContainer = document.getElementById('relatedArticles');
    if (!relatedContainer) return;
    
    // If no tags, show random articles
    if (!tags || tags.length === 0) {
        fetch('/api/frontend/featured-articles?limit=3')
            .then(response => response.json())
            .then(data => {
                displayRelatedArticles(data, currentArticleId);
            })
            .catch(error => {
                console.error('Error loading related articles:', error);
                relatedContainer.innerHTML = '';
            });
        return;
    }
    
    // Use first tag to find related articles
    const tagSlug = tags[0].slug;
    fetch(`/api/media/tags/${tagSlug}/articles?limit=4`)
        .then(response => response.json())
        .then(data => {
            displayRelatedArticles(data, currentArticleId);
        })
        .catch(error => {
            console.error('Error loading related articles:', error);
            relatedContainer.innerHTML = '';
        });
}

// Display related articles
function displayRelatedArticles(data, currentArticleId) {
    const relatedContainer = document.getElementById('relatedArticles');
    if (!relatedContainer) return;
    
    if (data.status === 'success' && data.data && data.data.length > 0) {
        // Filter out the current article
        const filteredArticles = data.data.filter(article => article.article_id !== currentArticleId);
        
        if (filteredArticles.length === 0) {
            relatedContainer.innerHTML = '';
            return;
        }
        
        relatedContainer.innerHTML = '';
        
        // Only show up to 3 related articles
        const articlesToShow = filteredArticles.slice(0, 3);
        
        articlesToShow.forEach(article => {
            const articleCard = createArticleCard(article);
            relatedContainer.appendChild(articleCard);
        });
    } else {
        relatedContainer.innerHTML = '';
    }
}

// Create pagination controls
function createPagination(containerId, total, limit, offset) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const totalPages = Math.ceil(total / limit);
    const currentPage = Math.floor(offset / limit) + 1;
    
    let paginationHtml = '';
    
    // Previous button
    paginationHtml += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage - 1}" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;
    
    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        paginationHtml += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>
        `;
    }
    
    // Next button
    paginationHtml += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage + 1}" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `;
    
    container.innerHTML = paginationHtml;
    
    // Add click event listeners
    const pageLinks = container.querySelectorAll('.page-link');
    pageLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = parseInt(this.dataset.page);
            
            if (isNaN(page) || page < 1 || page > totalPages || page === currentPage) {
                return;
            }
            
            // Update URL and reload content
            const searchParams = new URLSearchParams(window.location.search);
            searchParams.set('offset', (page - 1) * limit);
            window.location.search = searchParams.toString();
        });
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Article detail page
    const articleDetailContainer = document.getElementById('articleDetail');
    if (articleDetailContainer) {
        // Get article ID from URL or data attribute
        const articleId = articleDetailContainer.dataset.articleId;
        if (articleId) {
            loadArticleDetails(articleId);
        }
    }

    // Articles listing page
    const allArticlesContainer = document.getElementById('allArticles');
    if (allArticlesContainer) {
        loadAllArticles();
        
        // Setup search functionality
        const searchBtn = document.getElementById('searchArticlesBtn');
        if (searchBtn) {
            searchBtn.addEventListener('click', function() {
                const searchInput = document.getElementById('articlesSearch');
                if (searchInput && searchInput.value.trim()) {
                    const searchParams = new URLSearchParams(window.location.search);
                    searchParams.set('q', searchInput.value.trim());
                    window.location.search = searchParams.toString();
                }
            });
        }
    }
    
    // News listing page
    const allNewsContainer = document.getElementById('allNews');
    if (allNewsContainer) {
        loadAllNews();
        
        // Setup search functionality
        const searchBtn = document.getElementById('searchNewsBtn');
        if (searchBtn) {
            searchBtn.addEventListener('click', function() {
                const searchInput = document.getElementById('newsSearch');
                if (searchInput && searchInput.value.trim()) {
                    const searchParams = new URLSearchParams(window.location.search);
                    searchParams.set('q', searchInput.value.trim());
                    window.location.search = searchParams.toString();
                }
            });
        }
    }
});