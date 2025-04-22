// src/config.js
const config = {
    development: {
      API_URL: "http://localhost:5000/api"
    },
    production: {
      API_URL: "/api"
    }
  };
  
  const environment = process.env.NODE_ENV === 'production' ? 'production' : 'development';
  
  export default {
    API_URL: config[environment].API_URL
  };