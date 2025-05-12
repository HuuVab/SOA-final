// auth.js - Customer Authentication Functionality

// Configuration
const CUSTOMER_SERVICE_URL = '/api/customers';  // This will use the frontend proxy

// Local storage keys
const TOKEN_KEY = 'ecomm_auth_token';
const USER_KEY = 'ecomm_user_data';

// Bootstrap Modal instances
let loginModal, registerModal, verificationModal, profileModal, passwordModal;

// Current authenticated user
let currentUser = null;

// Initialize the authentication system
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap modals
    loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
    registerModal = new bootstrap.Modal(document.getElementById('registerModal'));
    verificationModal = new bootstrap.Modal(document.getElementById('verificationModal'));
    profileModal = new bootstrap.Modal(document.getElementById('profileModal'));
    passwordModal = new bootstrap.Modal(document.getElementById('changePasswordModal'));
    
    // Initialize form event listeners
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('registerForm').addEventListener('submit', handleRegister);
    document.getElementById('verificationForm').addEventListener('submit', handleVerification);
    document.getElementById('profileForm').addEventListener('submit', handleProfileUpdate);
    document.getElementById('passwordForm').addEventListener('submit', handlePasswordChange);
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    document.getElementById('resendCodeBtn').addEventListener('click', handleResendCode);
    
    // Check if user is already logged in
    checkAuthStatus();
});

// Check authentication status on page load
async function checkAuthStatus() {
    const token = localStorage.getItem(TOKEN_KEY);
    
    if (!token) {
        updateUIForGuest();
        return;
    }
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/validate-token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token })
        });
        
        const data = await response.json();
        
        if (response.ok && data.valid) {
            // Token is valid, user is authenticated
            currentUser = data.customer;
            localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
            updateUIForUser(currentUser);
        } else if (data.verification_required) {
            // Email verification required
            showVerificationModal(data.email);
        } else {
            // Token invalid or expired
            logout();
        }
    } catch (error) {
        console.error('Error validating token:', error);
        logout();
    }
}

// Handle login form submission
async function handleLogin(event) {
    event.preventDefault();
    
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const alertElement = document.getElementById('loginAlert');
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Login successful
            loginSuccess(data);
        } else if (response.status === 403 && data.verification_required) {
            // Email verification required
            loginModal.hide();
            showVerificationModal(data.email);
        } else {
            // Login failed
            showAlert(alertElement, data.message || 'Login failed. Please check your credentials.');
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert(alertElement, 'An error occurred. Please try again later.');
    }
}

// Handle register form submission
async function handleRegister(event) {
    event.preventDefault();
    
    const firstName = document.getElementById('registerFirstName').value;
    const lastName = document.getElementById('registerLastName').value;
    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;
    const phone = document.getElementById('registerPhone').value;
    const alertElement = document.getElementById('registerAlert');
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                first_name: firstName,
                last_name: lastName,
                email,
                password,
                phone
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Registration successful
            registerModal.hide();
            
            // Store token but show verification modal
            localStorage.setItem(TOKEN_KEY, data.token);
            showVerificationModal(data.customer.email);
        } else {
            // Registration failed
            showAlert(alertElement, data.message || 'Registration failed. Please try again.');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showAlert(alertElement, 'An error occurred. Please try again later.');
    }
}

// Handle verification form submission
async function handleVerification(event) {
    event.preventDefault();
    
    const email = document.getElementById('verificationEmail').value;
    const code = document.getElementById('verificationCode').value;
    const alertElement = document.getElementById('verificationAlert');
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/verify-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, code })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Verification successful
            verificationModal.hide();
            
            // Update token and check auth status
            localStorage.setItem(TOKEN_KEY, data.token);
            checkAuthStatus();
            
            // Show success message
            alert('Email verified successfully. You are now logged in.');
        } else {
            // Verification failed
            showAlert(alertElement, data.message || 'Verification failed. Please check the code and try again.');
        }
    } catch (error) {
        console.error('Verification error:', error);
        showAlert(alertElement, 'An error occurred. Please try again later.');
    }
}

// Handle profile form submission
async function handleProfileUpdate(event) {
    event.preventDefault();
    
    const firstName = document.getElementById('profileFirstName').value;
    const lastName = document.getElementById('profileLastName').value;
    const phone = document.getElementById('profilePhone').value;
    const address = document.getElementById('profileAddress').value;
    const alertElement = document.getElementById('profileAlert');
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/profile`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem(TOKEN_KEY)}`
            },
            body: JSON.stringify({
                first_name: firstName,
                last_name: lastName,
                phone,
                address
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Profile update successful
            currentUser = data.customer;
            localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
            updateUIForUser(currentUser);
            
            // Show success message
            showAlert(alertElement, 'Profile updated successfully!', 'success');
            
            // Hide alert after 3 seconds
            setTimeout(() => {
                alertElement.classList.add('d-none');
            }, 3000);
        } else {
            // Profile update failed
            showAlert(alertElement, data.message || 'Failed to update profile. Please try again.');
        }
    } catch (error) {
        console.error('Profile update error:', error);
        showAlert(alertElement, 'An error occurred. Please try again later.');
    }
}

// Handle password change form submission
async function handlePasswordChange(event) {
    event.preventDefault();
    
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const alertElement = document.getElementById('passwordAlert');
    
    // Check if passwords match
    if (newPassword !== confirmPassword) {
        showAlert(alertElement, 'New passwords do not match.');
        return;
    }
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/password`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem(TOKEN_KEY)}`
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Password change successful
            passwordModal.hide();
            
            // Update token
            localStorage.setItem(TOKEN_KEY, data.token);
            
            // Show success message
            alert('Password changed successfully.');
        } else {
            // Password change failed
            showAlert(alertElement, data.message || 'Failed to change password. Please try again.');
        }
    } catch (error) {
        console.error('Password change error:', error);
        showAlert(alertElement, 'An error occurred. Please try again later.');
    }
}

// Handle logout button click
async function handleLogout() {
    try {
        // Call logout API
        await fetch(`${CUSTOMER_SERVICE_URL}/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem(TOKEN_KEY)}`
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // Always logout locally even if API call fails
        logout();
        profileModal.hide();
    }
}

// Handle resend verification code
async function handleResendCode() {
    const email = document.getElementById('verificationEmail').value;
    const alertElement = document.getElementById('verificationAlert');
    
    try {
        const response = await fetch(`${CUSTOMER_SERVICE_URL}/resend-verification`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Code resent successfully
            showAlert(alertElement, 'Verification code resent. Please check your email.', 'success');
        } else {
            // Failed to resend code
            showAlert(alertElement, data.message || 'Failed to resend code. Please try again.');
        }
    } catch (error) {
        console.error('Resend code error:', error);
        showAlert(alertElement, 'An error occurred. Please try again later.');
    }
}

// Login success handler
function loginSuccess(data) {
    // Store authentication data
    localStorage.setItem(TOKEN_KEY, data.token);
    currentUser = data.customer;
    localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
    
    // Update UI
    updateUIForUser(currentUser);
    
    // Close login modal
    loginModal.hide();
    window.location.reload();
}

// Logout function
function logout() {
    // Clear authentication data
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    currentUser = null;
    
    // Update UI
    updateUIForGuest();
}

// Show verification modal
function showVerificationModal(email) {
    document.getElementById('verificationEmail').value = email;
    document.getElementById('verificationAlert').classList.add('d-none');
    verificationModal.show();
}

// Update UI for authenticated user
function updateUIForUser(user) {
    // Update account dropdown
    const accountText = document.getElementById('accountText');
    const accountMenu = document.getElementById('accountMenu');
    
    accountText.textContent = `${user.first_name}`;
    accountMenu.innerHTML = `
        <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#profileModal">My Profile</a></li>
        <li><a class="dropdown-item" href="/orders">My Orders</a></li>
        <li><hr class="dropdown-divider"></li>
        <li><a class="dropdown-item" href="#" id="navLogoutBtn">Logout</a></li>
    `;
    
    // Add event listener to the nav logout button
    document.getElementById('navLogoutBtn').addEventListener('click', handleLogout);
    
    // Populate profile form
    document.getElementById('profileFirstName').value = user.first_name || '';
    document.getElementById('profileLastName').value = user.last_name || '';
    document.getElementById('profileEmail').value = user.email || '';
    document.getElementById('profilePhone').value = user.phone || '';
    document.getElementById('profileAddress').value = user.address || '';
}

// Update UI for guest (not logged in)
function updateUIForGuest() {
    // Update account dropdown
    const accountText = document.getElementById('accountText');
    const accountMenu = document.getElementById('accountMenu');
    
    accountText.textContent = 'Account';
    accountMenu.innerHTML = `
        <li><a class="dropdown-item" href="#" id="loginBtn" data-bs-toggle="modal" data-bs-target="#loginModal">Login</a></li>
        <li><a class="dropdown-item" href="#" id="registerBtn" data-bs-toggle="modal" data-bs-target="#registerModal">Register</a></li>
    `;
}

// Helper to show alert messages
function showAlert(element, message, type = 'danger') {
    element.textContent = message;
    element.className = `alert alert-${type}`;
    element.classList.remove('d-none');
}