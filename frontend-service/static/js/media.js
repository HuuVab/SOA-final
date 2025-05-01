// media.js - Functions for loading and displaying news and articles

// Function to load featured articles for the homepage
function loadFeaturedArticles() {
    fetch('/api/frontend/featured-articles?limit=3')
        .then(response => response.json())
        .then(data => {
            const articlesContainer = document.getElementById('featuredArticles');
            
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
            document.getElementById('featuredArticles').innerHTML = 
                '<div class="col-12 text-center">Failed to load featured articles. Please try again later.</div>';
        });
}

// Function to load latest news for the homepage
function loadLatestNews() {
    fetch('/api/frontend/latest-news?limit=3')
        .then(response => response.json())
        .then(data => {
            const newsContainer = document.getElementById('latestNews');
            
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
            document.getElementById('latestNews').innerHTML = 
                '<div class="col-12 text-center">Failed to load latest news. Please try again later.</div>';
        });
}

// Function to create an article card
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
                <p class="card-text text-truncate">${article.summary || ''}</p>
            </div>
            <div class="card-footer bg-white d-flex justify-content-between align-items-center">
                <small class="text-muted">Published: ${publishedDate}</small>
                <a href="/articles/${article.article_id}" class="btn btn-sm btn-primary">Read More</a>
            </div>
        </div>
    `;
    
    return col;
}

// Function to create a news card
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
        <div class="card h-100 news-card">
            <div class="card-header bg-primary text-white">Latest News</div>
            <img src="${imageUrl}" class="card-img-top" alt="${newsItem.title || 'News image'}">
            <div class="card-body">
                <h5 class="card-title">${newsItem.title || 'Untitled News'}</h5>
                <p class="card-text text-truncate">${newsItem.summary || ''}</p>
            </div>
            <div class="card-footer bg-white d-flex justify-content-between align-items-center">
                <small class="text-muted">Published: ${publishedDate}</small>
                <a href="/articles/${newsItem.article_id}" class="btn btn-sm btn-outline-primary">Read More</a>
            </div>
        </div>
    `;
    
    return col;
}

// Load all articles for the articles page
function loadAllArticles() {
    fetch('/api/media/articles?type=article&status=published&limit=12')
        .then(response => response.json())
        .then(data => {
            const articlesContainer = document.getElementById('allArticles');
            
            if (data.status === 'success' && data.data && data.data.length > 0) {
                articlesContainer.innerHTML = '';
                
                data.data.forEach(article => {
                    const articleCard = createArticleCard(article);
                    articlesContainer.appendChild(articleCard);
                });
            } else {
                articlesContainer.innerHTML = '<div class="col-12 text-center">No articles available.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading articles:', error);
            document.getElementById('allArticles').innerHTML = 
                '<div class="col-12 text-center">Failed to load articles. Please try again later.</div>';
        });
}

// Load all news for the news page
function loadAllNews() {
    fetch('/api/media/articles?type=news&status=published&limit=12')
        .then(response => response.json())
        .then(data => {
            const newsContainer = document.getElementById('allNews');
            
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
            console.error('Error loading news:', error);
            document.getElementById('allNews').innerHTML = 
                '<div class="col-12 text-center">Failed to load news. Please try again later.</div>';
        });
}

// Load article details for the article detail page
function loadArticleDetails(articleId) {
    fetch(`/api/media/articles/${articleId}`)
        .then(response => response.json())
        .then(data => {
            const articleContainer = document.getElementById('articleDetail');
            
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
            } else {
                articleContainer.innerHTML = '<div class="alert alert-danger">Article not found or unavailable.</div>';
            }
        })
        .catch(error => {
            console.error('Error loading article details:', error);
            document.getElementById('articleDetail').innerHTML = 
                '<div class="alert alert-danger">Failed to load article. Please try again later.</div>';
        });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Homepage sections
    const featuredArticlesContainer = document.getElementById('featuredArticles');
    const latestNewsContainer = document.getElementById('latestNews');
    
    // Load featured articles if container exists (homepage)
    if (featuredArticlesContainer) {
        loadFeaturedArticles();
    }
    
    // Load latest news if container exists (homepage)
    if (latestNewsContainer) {
        loadLatestNews();
    }
    
    // All articles page
    const allArticlesContainer = document.getElementById('allArticles');
    if (allArticlesContainer) {
        loadAllArticles();
    }
    
    // All news page
    const allNewsContainer = document.getElementById('allNews');
    if (allNewsContainer) {
        loadAllNews();
    }
    
    // Article detail page
    const articleDetailContainer = document.getElementById('articleDetail');
    if (articleDetailContainer) {
        // Get article ID from URL or data attribute
        const articleId = articleDetailContainer.dataset.articleId;
        if (articleId) {
            loadArticleDetails(articleId);
        }
    }
});