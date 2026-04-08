window.UnifiedNutritionStorage = {
    storageKey: 'unified_nutrition_data',
    
    getDefaultData: function() {
        return {
            date: new Date().toDateString(),
            currentCategory: 'breakfast',
            mealData: {
                breakfast: { 
                    calories: 0, protein: 0, carbs: 0, fat: 0,
                    vitamin_a: 0, vitamin_c: 0, calcium: 0, iron: 0, water: 0,
                    items: []
                },
                lunch: { 
                    calories: 0, protein: 0, carbs: 0, fat: 0,
                    vitamin_a: 0, vitamin_c: 0, calcium: 0, iron: 0, water: 0,
                    items: []
                },
                dinner: { 
                    calories: 0, protein: 0, carbs: 0, fat: 0,
                    vitamin_a: 0, vitamin_c: 0, calcium: 0, iron: 0, water: 0,
                    items: []
                }
            },
            timestamp: Date.now()
        };
    },
    
    save: function() {
        try {
            const dataToSave = {
                date: new Date().toDateString(),
                currentCategory: window.currentMealCategory || 'breakfast',
                mealData: window.mealNutritionData || this.getDefaultData().mealData,
                timestamp: Date.now()
            };
            
            localStorage.setItem(this.storageKey, JSON.stringify(dataToSave));
            console.log(' Unified data saved successfully');
            return true;
        } catch (error) {
            console.error(' Error saving unified data:', error);
            return false;
        }
    },
    
    load: function() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            const today = new Date().toDateString();
            
            if (!saved) {
                console.log(' No saved data found, using defaults');
                return this.getDefaultData();
            }
            
            const data = JSON.parse(saved);
            
            if (data.date === today) {
                console.log(' Loaded data for today');
                return data;
            } else {
                console.log(' Data from different day, resetting');
                return this.getDefaultData();
            }
        } catch (error) {
            console.error(' Error loading data:', error);
            return this.getDefaultData();
        }
    },
    
    clearOldData: function() {
        localStorage.removeItem(this.storageKey);
        console.log(' Old data cleared');
    }
};

window.FixedMealCategorySystem = {
    currentCategory: 'breakfast',
    
    setCategory: function(category) {
        console.log(` Setting meal category to: ${category}`);
        
        if (!['breakfast', 'lunch', 'dinner'].includes(category)) {
            console.warn(' Invalid category, using breakfast');
            category = 'breakfast';
        }
        
        this.currentCategory = category;
        window.currentMealCategory = category;
        
        this.updateCategoryTabs(category);
        
        this.updateSectionHeader(category);
        
        window.UnifiedNutritionStorage.save();
        
        console.log(` Category set to: ${category}`);
        return category;
    },
    
    updateCategoryTabs: function(category) {

        document.querySelectorAll('.category-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        
        const activeTab = document.querySelector(`[data-category="${category}"]`);
        if (activeTab) {
            activeTab.classList.add('active');
            console.log(` Visual tab updated: ${category}`);
        }
    },
    
    updateSectionHeader: function(category) {
        const categoryNames = {
            breakfast: 'Sarapan',
            lunch: 'Makan Siang', 
            dinner: 'Makan Malam'
        };
        
        const header = document.querySelector('#analyzeSection .section-header h1');
        if (header) {
            header.innerHTML = `<i class="fas fa-camera"></i> Analisis ${categoryNames[category]}`;
        }
    },
    
    getCurrentCategory: function() {
        return this.currentCategory;
    }
};

window.FixedAccumulationSystem = {
    
    accumulateToMeal: function(nutritionData, customCategory = null) {
        try {
            const targetCategory = customCategory || window.FixedMealCategorySystem.getCurrentCategory();
            
            console.log(` Accumulating to: ${targetCategory}`);
            console.log(' Nutrition data:', nutritionData);
            
            if (!window.mealNutritionData) {
                window.mealNutritionData = window.UnifiedNutritionStorage.getDefaultData().mealData;
            }
            
            if (!window.mealNutritionData[targetCategory]) {
                window.mealNutritionData[targetCategory] = {
                    calories: 0, protein: 0, carbs: 0, fat: 0,
                    vitamin_a: 0, vitamin_c: 0, calcium: 0, iron: 0, water: 0,
                    items: []
                };
            }
            
            const currentMeal = window.mealNutritionData[targetCategory];
            
            currentMeal.calories += nutritionData.calories || 0;
            currentMeal.protein += nutritionData.protein || 0;
            currentMeal.carbs += nutritionData.carbs || 0;
            currentMeal.fat += nutritionData.fat || 0;
            currentMeal.vitamin_a += nutritionData.vitamin_a || 0;
            currentMeal.vitamin_c += nutritionData.vitamin_c || 0;
            currentMeal.calcium += nutritionData.calcium || 0;
            currentMeal.iron += nutritionData.iron || 0;
            currentMeal.water += nutritionData.water || 0;
            
            if (!currentMeal.items) {
                currentMeal.items = [];
            }
            
            const foodItem = {
                id: Date.now(),
                description: nutritionData.food_description || 'Makanan',
                calories: nutritionData.calories || 0,
                timestamp: new Date().toISOString()
            };
            
            currentMeal.items.push(foodItem);
            
            console.log(` Added to ${targetCategory}:`, {
                calories: Math.round(currentMeal.calories),
                items: currentMeal.items.length
            });
            
            this.updateAllDisplays();
            
            window.UnifiedNutritionStorage.save();
            
            this.showSuccessNotification(targetCategory, nutritionData.food_description, currentMeal.items.length);
            
            return foodItem.id;
            
        } catch (error) {
            console.error('Error in accumulation:', error);
            return null;
        }
    },
    
    updateAllDisplays: function() {
        console.log(' Updating all meal displays...');
        
        ['breakfast', 'lunch', 'dinner'].forEach(meal => {
            if (window.mealNutritionData && window.mealNutritionData[meal]) {
                const data = window.mealNutritionData[meal];
                
                this.updateMacronutrients(meal, data);
                
                this.updateMicronutrients(meal, data);
            }
        });
        
        this.updateDashboardProgress();
        
        console.log(' All displays updated');
    },
    
    updateMacronutrients: function(meal, data) {
        const elements = {
            calories: document.getElementById(`${meal}Calories`),
            protein: document.getElementById(`${meal}Protein`),
            carbs: document.getElementById(`${meal}Carbs`),
            fat: document.getElementById(`${meal}Fat`)
        };
        
        if (elements.calories) elements.calories.textContent = Math.round(data.calories);
        if (elements.protein) elements.protein.textContent = Math.round(data.protein) + 'g';
        if (elements.carbs) elements.carbs.textContent = Math.round(data.carbs) + 'g';
        if (elements.fat) elements.fat.textContent = Math.round(data.fat) + 'g';
    },
    
    updateMicronutrients: function(meal, data) {
        const micronutrients = {
            vitamin_a: { target: 900, unit: 'mcg' },
            vitamin_c: { target: 90, unit: 'mg' },
            calcium: { target: 1000, unit: 'mg' },
            iron: { target: 18, unit: 'mg' },
            water: { target: 2000, unit: 'ml' }
        };
        
        Object.keys(micronutrients).forEach(nutrient => {
            const current = data[nutrient] || 0;
            const config = micronutrients[nutrient];
            const percentage = Math.min((current / config.target) * 100, 100);
            
            // Update value display
            const valueId = `${meal}${nutrient.split('_').map(word => 
                word.charAt(0).toUpperCase() + word.slice(1)
            ).join('')}`;
            
            const valueElement = document.getElementById(valueId);
            if (valueElement) {
                valueElement.textContent = `${Math.round(current)} / ${config.target} ${config.unit}`;
            }
            
            // Update progress bar
            const barId = `${meal}${nutrient.split('_').map(word => 
                word.charAt(0).toUpperCase() + word.slice(1)
            ).join('')}Bar`;
            
            const barElement = document.getElementById(barId);
            if (barElement) {
                barElement.style.width = `${percentage}%`;
            }
        });
    },
    
    // Update dashboard progress (Total Today)
    updateDashboardProgress: function() {
        if (!window.mealNutritionData) return;
        
        // Calculate totals
        const totals = {
            calories: 0, protein: 0, carbs: 0, fat: 0,
            vitamin_a: 0, vitamin_c: 0, calcium: 0, iron: 0, water: 0
        };
        
        ['breakfast', 'lunch', 'dinner'].forEach(meal => {
            const data = window.mealNutritionData[meal];
            if (data) {
                Object.keys(totals).forEach(nutrient => {
                    totals[nutrient] += data[nutrient] || 0;
                });
            }
        });
        
        // Update dashboard displays
        this.updateDashboardElements(totals);
    },
    
    // Update dashboard elements
    updateDashboardElements: function(totals) {
        // Targets
        const targets = {
            calories: 2000, protein: 50, carbs: 250, fat: 65,
            vitamin_a: 900, vitamin_c: 90, calcium: 1000, iron: 18, water: 2000
        };
        
        // Update progress bars and values
        Object.keys(totals).forEach(nutrient => {
            const current = totals[nutrient];
            const target = targets[nutrient];
            const percentage = target > 0 ? (current / target) * 100 : 0;
            
            // Progress value
            const valueElement = document.getElementById(`progress${nutrient.charAt(0).toUpperCase() + nutrient.slice(1)}`);
            if (valueElement) {
                valueElement.textContent = `${Math.round(current)} / ${target}`;
            }
            
            // Progress bar
            const barElement = document.getElementById(`progress${nutrient.charAt(0).toUpperCase() + nutrient.slice(1)}Bar`);
            if (barElement) {
                barElement.style.width = `${Math.min(percentage, 100)}%`;
            }
        });
    },
    
    // Show success notification
    showSuccessNotification: function(category, foodDescription, totalItems) {
        const categoryNames = {
            breakfast: 'Sarapan',
            lunch: 'Makan Siang',
            dinner: 'Makan Malam'
        };
        
        const message = `✅ ${foodDescription || 'Makanan'} ditambahkan ke ${categoryNames[category]} (${totalItems} items total)`;
        
        // Remove existing notification
        const existing = document.getElementById('nutrition-success-notification');
        if (existing) existing.remove();
        
        // Create notification
        const notification = document.createElement('div');
        notification.id = 'nutrition-success-notification';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #10b981;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: bold;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 99999;
            max-width: 300px;
            font-size: 14px;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
};

// 4. INITIALIZATION & EVENT HANDLERS
window.InitializeNutritionFix = function() {
    console.log('🚀 Initializing Nutrition Fix System...');
    
    // Load saved data
    const savedData = window.UnifiedNutritionStorage.load();
    
    // Apply loaded data
    window.mealNutritionData = savedData.mealData;
    window.currentMealCategory = savedData.currentCategory;
    
    // Set initial category
    window.FixedMealCategorySystem.setCategory(savedData.currentCategory);
    
    // Update all displays
    window.FixedAccumulationSystem.updateAllDisplays();
    
    // Setup category tab handlers
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            const category = this.getAttribute('data-category');
            if (category) {
                window.FixedMealCategorySystem.setCategory(category);
            }
        });
    });
    
    // Auto-save every 30 seconds
    setInterval(() => {
        window.UnifiedNutritionStorage.save();
    }, 30000);
    
    console.log('✅ Nutrition Fix System initialized successfully!');
    console.log('📊 Current category:', window.currentMealCategory);
    console.log('🍽️ Meal data loaded:', Object.keys(window.mealNutritionData || {}));
};

// 5. REPLACE EXISTING FUNCTIONS
window.accumulateToCurrentMeal = function(nutritionData) {
    return window.FixedAccumulationSystem.accumulateToMeal(nutritionData);
};

window.updateMealDisplays = function() {
    window.FixedAccumulationSystem.updateAllDisplays();
};

// 6. CLEAR MEAL FUNCTION
window.clearCurrentMeal = function() {
    const category = window.FixedMealCategorySystem.getCurrentCategory();
    const categoryNames = {
        breakfast: 'Sarapan',
        lunch: 'Makan Siang',
        dinner: 'Makan Malam'
    };
    
    if (!window.mealNutritionData || !window.mealNutritionData[category]) {
        alert(`${categoryNames[category]} sudah kosong!`);
        return;
    }
    
    const currentData = window.mealNutritionData[category];
    const itemCount = currentData.items ? currentData.items.length : 0;
    
    if (itemCount === 0) {
        alert(`${categoryNames[category]} sudah kosong!`);
        return;
    }
    
    const confirmation = confirm(
        `Hapus semua makanan dari ${categoryNames[category]}?\n\nTerdapat ${itemCount} items dengan total ${Math.round(currentData.calories)} kalori.`
    );
    
    if (!confirmation) return;
    
    // Reset all nutrition values
    const nutrients = ['calories', 'protein', 'carbs', 'fat', 'vitamin_a', 'vitamin_c', 'calcium', 'iron', 'water'];
    nutrients.forEach(nutrient => {
        currentData[nutrient] = 0;
    });
    
    // Clear items array
    currentData.items = [];
    
    // Update displays and save
    window.FixedAccumulationSystem.updateAllDisplays();
    window.UnifiedNutritionStorage.save();
    
    // Show success notification
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed; top: 20px; right: 20px;
        background: #ef4444; color: white; padding: 12px 20px;
        border-radius: 8px; font-weight: bold; z-index: 99999;
    `;
    notification.textContent = `🗑️ ${categoryNames[category]} dikosongkan!`;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) notification.parentNode.removeChild(notification);
    }, 2000);
    
    console.log(`✅ Cleared ${category}`);
};

// 7. AUTO-INITIALIZATION
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            window.InitializeNutritionFix();
        }, 1000);
    });
} else {
    setTimeout(() => {
        window.InitializeNutritionFix();
    }, 1000);
}

console.log('🔧 =====================================');
console.log('🔧 NUTRITION FIX SYSTEM LOADED');
console.log('🔧 =====================================');
console.log('✅ Unified storage system');
console.log('✅ Fixed meal category system'); 
console.log('✅ Fixed accumulation system');
console.log('✅ Progress persistence after refresh');
console.log('✅ Correct meal category targeting');
console.log('');
console.log('🎯 Functions available:');
console.log('- window.FixedMealCategorySystem.setCategory("breakfast")');
console.log('- window.clearCurrentMeal()');
console.log('- window.UnifiedNutritionStorage.save()');
console.log('');
console.log('🍽️ System will automatically handle all nutrition tracking!');