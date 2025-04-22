import React, { useState, useEffect } from 'react';
import './App.css';

// API URL configuration
const API_URL = "http://localhost:5000/api";

const App = () => {
  const [view, setView] = useState('login');
  const [notification, setNotification] = useState(null);

  // Display notification with auto-dismiss
  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  // Render the appropriate component based on current view
  const renderView = () => {
    switch(view) {
      case 'login':
        return <LoginForm setView={setView} showNotification={showNotification} />;
      case 'register':
        return <RegisterForm setView={setView} showNotification={showNotification} />;
      default:
        return <LoginForm setView={setView} showNotification={showNotification} />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <a href="/" className="text-2xl font-bold text-blue-600 flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 mr-2" viewBox="0 0 20 20" fill="currentColor">
              <path d="M3 1a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 11.846 4.632 14 6.414 14H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 3H6.28l-.31-1.243A1 1 0 005 1H3zM16 16.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zM6.5 18a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
            </svg>
            GGMrBeast
          </a>
          
          <div className="flex gap-6">
            <button 
              onClick={() => setView('login')}
              className={`text-sm font-medium transition-colors ${view === 'login' ? 'text-blue-600' : 'text-gray-600 hover:text-blue-500'}`}
            >
              Login
            </button>
            <button 
              onClick={() => setView('register')}
              className={`text-sm font-medium transition-colors ${view === 'register' ? 'text-blue-600' : 'text-gray-600 hover:text-blue-500'}`}
            >
              Register
            </button>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="flex-grow flex items-center justify-center p-6">
        {/* Notification Banner */}
        {notification && (
          <div className={`fixed top-20 right-4 max-w-sm p-4 rounded-lg shadow-lg ${
            notification.type === 'success' ? 'bg-green-100 text-green-800 border-l-4 border-green-500' : 
            notification.type === 'error' ? 'bg-red-100 text-red-800 border-l-4 border-red-500' : 
            'bg-blue-100 text-blue-800 border-l-4 border-blue-500'
          } transition-all duration-500 ease-in-out`}>
            {notification.message}
          </div>
        )}
        
        <div className="w-full max-w-md">
          {renderView()}
        </div>
      </main>
      
      {/* Footer */}
      <footer className="bg-white shadow-inner py-6 border-t">
        <div className="container mx-auto px-6 text-center text-gray-500 text-sm">
          &copy; {new Date().getFullYear()} GGMrBeast. All rights reserved.
        </div>
      </footer>
    </div>
  );
};

// Login Form Component
const LoginForm = ({ setView, showNotification }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch(`${API_URL}/customers/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        localStorage.setItem('token', data.token);
        window.location.href = '/dashboard'; // Redirect to dashboard
        showNotification('Login successful', 'success');
      } else {
        if (data.verification_required) {
          setView('verify-email');
          showNotification('Please verify your email to continue', 'warning');
        } else {
          showNotification(data.message || 'Login failed', 'error');
        }
      }
    } catch (error) {
      console.error('Login error:', error);
      showNotification('An error occurred during login', 'error');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="bg-white p-8 rounded-lg shadow-lg border border-gray-200">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Welcome Back</h2>
        <p className="text-gray-600 mt-1">Sign in to your account</p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            placeholder="your@email.com"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
            <a href="#forgot" className="text-xs text-blue-600 hover:text-blue-800">Forgot password?</a>
          </div>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            placeholder="••••••••"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
          />
        </div>
        
        <div className="flex items-center">
          <input
            id="remember-me"
            name="remember-me"
            type="checkbox"
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-700">
            Remember me
          </label>
        </div>
        
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:opacity-50 transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Logging in...
            </span>
          ) : 'Sign in'}
        </button>
      </form>
      
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-600">
          Don't have an account?{' '}
          <button 
            onClick={() => setView('register')}
            className="text-blue-600 hover:underline font-medium"
          >
            Create account
          </button>
        </p>
      </div>
    </div>
  );
};

// Registration Form Component
const RegisterForm = ({ setView, showNotification }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: '',
    address: ''
  });
  const [loading, setLoading] = useState(false);
  const [emailChecking, setEmailChecking] = useState(false);
  const [emailExists, setEmailExists] = useState(false);
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Check if email already exists
    if (name === 'email' && value.includes('@')) {
      checkEmailExists(value);
    }
  };
  
  // Check if email is already registered
  const checkEmailExists = async (email) => {
    if (!email || !email.includes('@')) return;
    
    setEmailChecking(true);
    try {
      const response = await fetch(`${API_URL}/customers/${encodeURIComponent(email)}/exists`);
      const data = await response.json();
      setEmailExists(data.exists);
    } catch (error) {
      console.error('Email check error:', error);
    } finally {
      setEmailChecking(false);
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (emailExists) {
      showNotification('This email is already registered', 'error');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await fetch(`${API_URL}/customers/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setView('login');
        showNotification('Registration successful! Please check your email to verify your account', 'success');
      } else {
        showNotification(data.message || 'Registration failed', 'error');
      }
    } catch (error) {
      console.error('Registration error:', error);
      showNotification('An error occurred during registration', 'error');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="bg-white p-8 rounded-lg shadow-lg border border-gray-200">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Create Account</h2>
        <p className="text-gray-600 mt-1">Join our shopping community</p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="first_name" className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
            <input
              type="text"
              id="first_name"
              name="first_name"
              value={formData.first_name}
              onChange={handleChange}
              required
              placeholder="John"
              className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          
          <div>
            <label htmlFor="last_name" className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
            <input
              type="text"
              id="last_name"
              name="last_name"
              value={formData.last_name}
              onChange={handleChange}
              required
              placeholder="Doe"
              className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
        
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <div className="relative">
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              placeholder="your@email.com"
              className={`w-full px-4 py-2 rounded-lg border ${
                emailExists ? 'border-red-500 pr-24' : 'border-gray-300'
              } focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
            />
            {emailChecking && (
              <span className="absolute right-3 top-2 text-gray-400 text-sm">Checking...</span>
            )}
            {emailExists && (
              <p className="text-red-500 text-xs mt-1">This email is already registered</p>
            )}
          </div>
        </div>
        
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            minLength="6"
            placeholder="••••••••"
            className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <p className="text-xs text-gray-500 mt-1">Password must be at least 6 characters</p>
        </div>
        
        <div>
          <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">Phone (optional)</label>
          <input
            type="tel"
            id="phone"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            placeholder="(123) 456-7890"
            className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        
        <div>
          <label htmlFor="address" className="block text-sm font-medium text-gray-700 mb-1">Address (optional)</label>
          <textarea
            id="address"
            name="address"
            value={formData.address}
            onChange={handleChange}
            rows="2"
            placeholder="Your shipping address"
            className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          ></textarea>
        </div>
        
        <div className="flex items-center mt-4">
          <input
            id="terms"
            name="terms"
            type="checkbox"
            required
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <label htmlFor="terms" className="ml-2 block text-sm text-gray-700">
            I agree to the <a href="#terms" className="text-blue-600 hover:underline">Terms and Conditions</a>
          </label>
        </div>
        
        <button
          type="submit"
          disabled={loading || emailExists}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:opacity-50 mt-4"
        >
          {loading ? 'Creating Account...' : 'Create Account'}
        </button>
      </form>
      
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-600">
          Already have an account?{' '}
          <button 
            onClick={() => setView('login')}
            className="text-blue-600 hover:underline font-medium"
          >
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
};

export default App;