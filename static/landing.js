let currentGuestImage = null;
let guestSessionId = generateSessionId();
let hasUsedGuestTrial = false;

function generateSessionId() {
    return 'guest_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function checkGuestTrialStatus() {
    const used = localStorage.getItem('guest_trial_used');
    if (used) {
        hasUsedGuestTrial = true;
    }
}

async function handleLogin(event) {
    event.preventDefault();
    
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const authLoading = document.getElementById('authLoading');
    const loginForm = document.getElementById('loginForm');
    
    if (!email || !password) {
        showAlert('Please fill in all fields', 'error');
        return;
    }
    
    loginForm.style.display = 'none';
    authLoading.style.display = 'block';
    
    try {
        console.log('Attempting login for:', email);
        
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        console.log('Login response:', data);
        
        if (data.success) {
            showAlert('Login successful! Redirecting to app...', 'success');
            closeAuthModal();
            
            console.log('Login successful, waiting before redirect...');

            await new Promise(resolve => setTimeout(resolve, 1000));
            
            let authVerified = false;
            for (let i = 0; i < 3; i++) {
                try {
                    console.log(`Verifying auth... attempt ${i + 1}`);
                    
                    const authCheck = await fetch('/api/auth/status', {
                        credentials: 'same-origin',
                        cache: 'no-cache'
                    });
                    
                    const authData = await authCheck.json();
                    console.log('Auth verification:', authData);
                    
                    if (authData.authenticated && !authData.user.is_guest) {
                        authVerified = true;
                        console.log('Auth verified successfully');
                        break;
                    }
                } catch (error) {
                    console.error(`Auth verification attempt ${i + 1} failed:`, error);
                }
                
                if (i < 2) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            if (authVerified) {
                console.log('Redirecting to /app...');
                window.location.href = '/app?from_login=true';
            } else {
                console.error('Auth verification failed, redirecting anyway');
                showAlert('Login berhasil, tapi mohon refresh jika halaman tidak beralih.', 'warning');
                setTimeout(() => {
                    window.location.href = '/app?from_login=true&retry=true';
                }, 2000);
            }
        } else {
            console.error('Login failed:', data.message);
            showAlert(data.message || 'Login failed', 'error');
            loginForm.style.display = 'block';
            authLoading.style.display = 'none';
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert('Login failed. Please try again.', 'error');
        loginForm.style.display = 'block';
        authLoading.style.display = 'none';
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const formData = {
        name: document.getElementById('registerName').value,
        email: document.getElementById('registerEmail').value,
        password: document.getElementById('registerPassword').value
    };
    
    const authLoading = document.getElementById('authLoading');
    const registerForm = document.getElementById('registerForm');
    
    if (!formData.name || !formData.email || !formData.password) {
        showAlert('Please fill in all required fields', 'error');
        return;
    }
    
    if (formData.password.length < 6) {
        showAlert('Password must be at least 6 characters', 'error');
        return;
    }
    
    registerForm.style.display = 'none';
    authLoading.style.display = 'block';
    
    try {
        console.log('Attempting registration for:', formData.email);
        
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        console.log('Register response:', data);
        
        if (data.success) {
            showAlert('Account created successfully! Redirecting to dashboard...', 'success');
            closeAuthModal();
            
            console.log('Registration successful, waiting before redirect...');
            
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            let authVerified = false;
            for (let i = 0; i < 3; i++) {
                try {
                    console.log(`Verifying auth after registration... attempt ${i + 1}`);
                    
                    const authCheck = await fetch('/api/auth/status', {
                        credentials: 'same-origin',
                        cache: 'no-cache'
                    });
                    
                    const authData = await authCheck.json();
                    console.log('Auth verification:', authData);
                    
                    if (authData.authenticated && !authData.user.is_guest) {
                        authVerified = true;
                        console.log('Auth verified successfully');
                        break;
                    }
                } catch (error) {
                    console.error(`Auth verification attempt ${i + 1} failed:`, error);
                }
                
                if (i < 2) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            if (authVerified) {
                console.log('Redirecting to /app...');
                window.location.href = '/app?from_login=true';
            } else {
                console.error('Auth verification failed after registration');
                showAlert('Akun berhasil dibuat, tapi mohon refresh jika halaman tidak beralih.', 'warning');
                setTimeout(() => {
                    window.location.href = '/app?from_login=true&retry=true';
                }, 2000);
            }
        } else {
            console.error('Registration failed:', data.message);
            showAlert(data.message || 'Registration failed', 'error');
            registerForm.style.display = 'block';
            authLoading.style.display = 'none';
        }
    } catch (error) {
        console.error('Registration error:', error);
        showAlert('Registration failed. Please try again.', 'error');
        registerForm.style.display = 'block';
        authLoading.style.display = 'none';
    }
}

function showAuthModal(mode = 'login') {
    const overlay = document.getElementById('authModalOverlay');
    const title = document.getElementById('authModalTitle');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const authLoading = document.getElementById('authLoading');
    
    loginForm.reset();
    registerForm.reset();
    authLoading.style.display = 'none';
    
    if (mode === 'login') {
        title.textContent = 'Welcome Back';
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    } else {
        title.textContent = 'Start Your Free Trial';
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    }
    
    overlay.classList.add('active');
}

function closeAuthModal() {
    const overlay = document.getElementById('authModalOverlay');
    overlay.classList.remove('active');
}

function switchAuthMode(mode) {
    const title = document.getElementById('authModalTitle');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (mode === 'login') {
        title.textContent = 'Welcome Back';
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    } else {
        title.textContent = 'Start Your Free Trial';
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    }
}

function setupGuestUpload() {
    const fileInputDemo = document.getElementById('fileInputDemo');
    const uploadAreaDemo = document.getElementById('uploadAreaDemo');
    
    if (!fileInputDemo || !uploadAreaDemo) return;
    
    fileInputDemo.addEventListener('change', handleGuestFileSelect);
    
    uploadAreaDemo.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadAreaDemo.classList.add('dragover');
    });
    
    uploadAreaDemo.addEventListener('dragleave', () => {
        uploadAreaDemo.classList.remove('dragover');
    });
    
    uploadAreaDemo.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadAreaDemo.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
            currentGuestImage = files[0];
            displayGuestImagePreview(files[0]);
        }
    });
}

function handleGuestFileSelect(event) {
    const file = event.target.files[0];
    if (file && file.type.startsWith('image/')) {
        currentGuestImage = file;
        displayGuestImagePreview(file);
    } else {
        showAlert('Please select an image file!', 'error');
    }
}

function displayGuestImagePreview(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        const imagePreviewDemo = document.getElementById('imagePreviewDemo');
        if (imagePreviewDemo) {
            imagePreviewDemo.innerHTML = `
                <img src="${e.target.result}" class="preview-image-demo" alt="Food Preview">
                <div style="text-align: center; margin-top: 20px;">
                    <button class="btn btn-primary" onclick="analyzeGuestMeal()">
                        <i class="fas fa-brain"></i>
                        Analyze This Meal
                    </button>
                    <button class="btn btn-hero-outline" onclick="resetGuestAnalysis()" style="margin-left: 12px;">
                        <i class="fas fa-times"></i>
                        Clear
                    </button>
                </div>
            `;
        }
    };
    reader.readAsDataURL(file);
}

async function analyzeGuestMeal() {
    if (!currentGuestImage) {
        showAlert('Please select a food photo!', 'error');
        return;
    }
    if (hasUsedGuestTrial) {
        showGuestLimitReached();
        return;
    }
    
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('active');
    }
    
    try {
        console.log('Starting guest meal analysis...');
        
        const formData = new FormData();
        formData.append('image', currentGuestImage);
        formData.append('meal_type', 'guest_trial');
        
        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Session-ID': guestSessionId,
                'X-Landing-Guest': 'true'
            }
        });
        
        const result = await response.json();
        console.log('Guest analysis result:', result);
        
        if (response.ok) {
            displayGuestResults(result);
            showAlert('Analysis completed! This was your free trial.', 'success');
            
            hasUsedGuestTrial = true;
            localStorage.setItem('guest_trial_used', 'true');
            
            setTimeout(() => {
                const upgradePrompt = document.getElementById('upgradePrompt');
                if (upgradePrompt) {
                    upgradePrompt.style.display = 'block';
                }
            }, 2000);
        } else {
            if (response.status === 403 && result.guest_limit_reached) {
                showGuestLimitReached();
            } else {
                throw new Error(result.error || 'Analysis failed');
            }
        }
        
    } catch (error) {
        console.error('Guest analysis error:', error);
        showAlert(`Error: ${error.message}`, 'error');
    } finally {
        if (loadingOverlay) {
            loadingOverlay.classList.remove('active');
        }
    }
}

function displayGuestResults(data) {
    const resultsDiv = document.getElementById('guestResults');
    if (!resultsDiv) return;
    
    resultsDiv.innerHTML = `
        <div class="guest-result-header">
            <h3 style="color: var(--primary-color); margin-bottom: 8px;">
                <i class="fas fa-check-circle"></i>
                Analysis Complete!
            </h3>
            <p style="color: var(--text-secondary);">${data.meal_description}</p>
        </div>
        
        <div class="guest-nutrition-grid">
            <div class="guest-nutrition-item">
                <div class="guest-nutrition-value">${Math.round(data.total_nutrition.calories)}</div>
                <div class="guest-nutrition-label">Calories</div>
            </div>
            <div class="guest-nutrition-item">
                <div class="guest-nutrition-value">${data.total_nutrition.protein.toFixed(1)}g</div>
                <div class="guest-nutrition-label">Protein</div>
            </div>
            <div class="guest-nutrition-item">
                <div class="guest-nutrition-value">${data.total_nutrition.carbs.toFixed(1)}g</div>
                <div class="guest-nutrition-label">Carbs</div>
            </div>
            <div class="guest-nutrition-item">
                <div class="guest-nutrition-value">${data.health_score}/100</div>
                <div class="guest-nutrition-label">Health Score</div>
            </div>
        </div>
        
        <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border: 1px solid #0284c7; border-radius: 12px; padding: 16px; margin-top: 16px;">
            <h4 style="color: #0c4a6e; margin-bottom: 8px;">
                <i class="fas fa-lightbulb"></i>
                Quick Insights
            </h4>
            <p style="color: #075985; margin: 0; font-size: 0.9rem;">
                ${data.recommendations[0] || 'Great meal! Keep tracking for more insights.'}
            </p>
        </div>
        
        <div style="text-align: center; margin-top: 20px;">
            <button class="btn btn-primary" onclick="showAuthModal('register')">
                <i class="fas fa-rocket"></i>
                Unlock Full Analysis
            </button>
        </div>
    `;
    
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function showGuestLimitReached() {
    const resultsDiv = document.getElementById('guestResults');
    if (!resultsDiv) return;
    
    resultsDiv.innerHTML = `
        <div style="text-align: center; padding: 40px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #f59e0b; border-radius: 16px;">
            <div style="font-size: 3rem; margin-bottom: 16px;">🔒</div>
            <h3 style="color: #92400e; margin-bottom: 8px;">Free Trial Used</h3>
            <p style="color: #a16207; margin-bottom: 24px;">
                You've already used your free analysis! Register to get unlimited access and track your nutrition progress.
            </p>
            <button class="btn btn-primary" onclick="showAuthModal('register')" style="margin-right: 12px;">
                <i class="fas fa-user-plus"></i>
                Register Free
            </button>
            <button class="btn btn-hero-outline" onclick="showAuthModal('login')">
                <i class="fas fa-sign-in-alt"></i>
                Login
            </button>
        </div>
    `;
    
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function resetGuestAnalysis() {
    const imagePreviewDemo = document.getElementById('imagePreviewDemo');
    const guestResults = document.getElementById('guestResults');
    const fileInputDemo = document.getElementById('fileInputDemo');
    
    if (imagePreviewDemo) imagePreviewDemo.innerHTML = '';
    if (guestResults) {
        guestResults.innerHTML = '';
        guestResults.style.display = 'none';
    }
    if (fileInputDemo) fileInputDemo.value = '';
    
    currentGuestImage = null;
}

async function checkGuestStatus() {
    try {
        console.log('Checking guest trial status...');
        
        const response = await fetch('/api/guest/check-limit');
        const data = await response.json();
        
        console.log('Guest status:', data);
        
        if (!data.can_use_trial) {
            const uploadDemo = document.getElementById('uploadDemo');
            if (uploadDemo) {
                uploadDemo.innerHTML = `
                    <i class="fas fa-lock"></i>
                    <h4>Free Trial Used</h4>
                    <p>You've already tried our analysis. Register for unlimited access!</p>
                    <button class="btn" onclick="showAuthModal('register')" style="margin-top: 16px;">
                        <i class="fas fa-user-plus"></i>
                        Register Now
                    </button>
                `;
            }
            hasUsedGuestTrial = true;
        }
    } catch (error) {
        console.error('Error checking guest status:', error);
    }
}

function scrollToTrySection() {
    const trySection = document.getElementById('try-section');
    if (trySection) {
        trySection.scrollIntoView({ behavior: 'smooth' });
    }
}

function toggleMobileNav() {
    const navMenu = document.querySelector('.nav-menu');
    const navToggle = document.querySelector('.nav-toggle');
    
    if (navMenu && navToggle) {
        navMenu.classList.toggle('active');
        navToggle.classList.toggle('active');
    }
}

function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

function setupNavbarScroll() {
    window.addEventListener('scroll', () => {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            if (window.scrollY > 50) {
                navbar.style.background = 'rgba(255, 255, 255, 0.98)';
                navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
            } else {
                navbar.style.background = 'rgba(255, 255, 255, 0.95)';
                navbar.style.boxShadow = 'none';
            }
        }
    });
}

function setupAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    document.querySelectorAll('.feature-card, .testimonial-card, .step').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

async function checkAuthStatus() {
    try {
        console.log('Checking auth status on landing page...');
        
        const response = await fetch('/api/auth/status', {
            credentials: 'same-origin'
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Auth status result:', data);
            
            if (data.authenticated && !data.user.is_guest) {
                const navButtons = document.querySelector('.nav-buttons');
                if (navButtons) {
                    navButtons.innerHTML = `
                        <a href="/app" class="btn">
                            <i class="fas fa-chart-line"></i>
                            Go to Dashboard
                        </a>
                        <button class="btn btn-outline" onclick="logoutUser()">
                            <i class="fas fa-sign-out-alt"></i>
                            Logout
                        </button>
                    `;
                }
            }
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
    }
}

async function logoutUser() {
    try {
        console.log('Logging out user from landing page...');
        
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        console.log('Logout response status:', response.status);
        
        if (response.ok) {
            const data = await response.json();
            console.log('Logout response data:', data);
            
            if (data.success) {
                showAlert('Logged out successfully', 'success');
                
                setTimeout(() => {
                    location.reload(); 
                }, 1000);
            } else {
                showAlert(data.message || 'Logout failed', 'error');
            }
        } else {
            let errorMessage = 'Logout failed';
            try {
                const errorData = await response.json();
                errorMessage = errorData.message || errorMessage;
            } catch (e) {
                console.error('Failed to parse error response:', e);
            }
            
            console.error('Logout request failed:', response.status, errorMessage);
            showAlert(errorMessage, 'error');
        }
    } catch (error) {
        console.error('Logout error:', error);
        showAlert('Network error during logout. Please refresh the page.', 'error');
    }
}

function showAlert(message, type) {
    const alertContainer = document.getElementById('alertContainer');
    if (!alertContainer) return;
    
    const alertId = 'alert_' + Date.now();
    
    const icon = type === 'success' ? 'fas fa-check-circle' : 
                 type === 'warning' ? 'fas fa-exclamation-triangle' : 
                 'fas fa-exclamation-circle';
    
    alertContainer.innerHTML = `
        <div id="${alertId}" class="alert alert-${type}">
            <i class="${icon}"></i>
            ${message}
        </div>
    `;
    
    setTimeout(() => {
        const alertElement = document.getElementById(alertId);
        if (alertElement) {
            alertElement.remove();
        }
    }, 5000);
}

async function loadDynamicStats() {
    try {
        console.log('Loading dynamic stats...');
        
        const response = await fetch('/api/health');
        if (response.ok) {
            const data = await response.json();
            console.log('Health data:', data);
            
            const statNumbers = document.querySelectorAll('.stat-number');
            if (statNumbers.length >= 3) {
                statNumbers[0].textContent = formatNumber(data.total_analyses) + '+';
            }
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Landing page DOM loaded, initializing...');
    
    checkGuestTrialStatus();
    checkAuthStatus();
    setupGuestUpload();
    setupSmoothScroll();
    setupNavbarScroll();
    setupAnimations();
    
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
    
    const authModalOverlay = document.getElementById('authModalOverlay');
    if (authModalOverlay) {
        authModalOverlay.addEventListener('click', function(e) {
            if (e.target === this) {
                closeAuthModal();
            }
        });
    }
    
    const navToggle = document.getElementById('navToggle');
    if (navToggle) {
        navToggle.addEventListener('click', toggleMobileNav);
    }
    
    setTimeout(checkGuestStatus, 1000);
    setTimeout(loadDynamicStats, 1000);
    
    console.log('Landing page initialization completed');
});

window.addEventListener('scroll', function() {
    const navbar = document.getElementById('navbar');
    if (navbar) {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    }
});

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

console.log('Landing.js loaded successfully');