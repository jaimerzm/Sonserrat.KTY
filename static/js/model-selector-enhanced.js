document.addEventListener('DOMContentLoaded', () => {
    const modelSelector = document.getElementById('model-selector');
    const modelNameElements = document.querySelectorAll('#model-name');
    const modelSelectorContainer = document.querySelector('.model-selector-container');
    
    // Create model options with enhanced visual feedback
    const models = [
        { value: 'gemini', name: 'Chat.KTY (VISION)', icon: 'fa-brain', color: '#4285f4' },
        { value: 'groq', name: 'Jaime LLM pro 2.0', icon: 'fa-bolt', color: '#fbbc05' },
        { value: 'gemini-flash', name: 'Gemini 2.0 Flash (Imágenes/Edición)', icon: 'fa-image', color: '#ea4335' }
    ];

    // Set initial model
    let currentModel = models[0];
    
    // Create floating model options menu
    function createModelMenu() {
        // Create the floating menu container
        const modelMenu = document.createElement('div');
        modelMenu.className = 'model-floating-menu';
        
        models.forEach(model => {
            const option = document.createElement('div');
            option.className = 'model-option';
            option.dataset.value = model.value;
            
            const iconContainer = document.createElement('div');
            iconContainer.className = 'model-icon-container';
            iconContainer.style.backgroundColor = `${model.color}15`;
            
            const icon = document.createElement('i');
            icon.className = `fas ${model.icon}`;
            icon.style.color = model.color;
            
            iconContainer.appendChild(icon);
            
            const label = document.createElement('span');
            label.textContent = model.name;
            
            const checkmark = document.createElement('i');
            checkmark.className = 'fas fa-check model-option-check';
            checkmark.style.opacity = '0';
            checkmark.style.color = model.color;
            
            option.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent event bubbling
                
                // Update visual state immediately
                const allOptions = document.querySelectorAll('.model-option');
                allOptions.forEach(opt => {
                    opt.classList.remove('active');
                    const optCheck = opt.querySelector('.model-option-check');
                    const optIcon = opt.querySelector('.model-icon-container');
                    if (optCheck) optCheck.style.opacity = '0';
                    if (optIcon) optIcon.style.transform = 'scale(1)';
                });
                
                // Apply active state to clicked option
                option.classList.add('active');
                checkmark.style.opacity = '1';
                iconContainer.style.transform = 'scale(1.1)';
                
                // Select the model after a short delay for visual feedback
                setTimeout(() => {
                    selectModel(model.value, model.name);
                    toggleMenu(false);
                }, 200);
            });
            
            option.appendChild(iconContainer);
            option.appendChild(label);
            option.appendChild(checkmark);
            modelMenu.appendChild(option);
        });
        
        // Append the menu to the container
        modelSelectorContainer.appendChild(modelMenu);
        return modelMenu;
    }
    
    // Toggle menu visibility with enhanced animation
    function toggleMenu(show) {
        const menu = document.querySelector('.model-floating-menu');
        if (!menu) return;
        
        if (show) {
            menu.classList.add('active');
            menu.style.visibility = 'visible';
            menu.style.opacity = '1';
            menu.style.transform = 'translateY(0) scale(1)';
            menu.style.pointerEvents = 'auto';
            // Update initial active state
            updateActiveState();
        } else {
            menu.classList.remove('active');
            menu.style.visibility = 'hidden';
            menu.style.opacity = '0';
            menu.style.transform = 'translateY(-10px) scale(0.98)';
            menu.style.pointerEvents = 'none';
        }
    }
    
    // Select model function with enhanced feedback
    function selectModel(value, name) {
        // Update the hidden select element
        modelSelector.value = value;
        
        // Update current model reference
        currentModel = models.find(m => m.value === value);
        
        // Update all instances of model-name
        modelNameElements.forEach(el => {
            el.textContent = name;
        });
        
        // Update model selector container style
        const mainIconContainer = modelSelectorContainer.querySelector('.model-icon-container');
        if (mainIconContainer) {
            mainIconContainer.style.backgroundColor = `${currentModel.color}15`;
            const icon = mainIconContainer.querySelector('i');
            if (icon) {
                icon.style.color = currentModel.color;
                // Update icon class based on selected model
                icon.className = `fas ${currentModel.icon}`;
            }
        }
        
        // Trigger change event with bubbles to ensure it propagates up the DOM
        const event = new Event('change', { bubbles: true });
        modelSelector.dispatchEvent(event);
        
        // Log the selection for debugging
        console.log(`Model selected: ${name} (${value})`);
        
        // Update active state in the dropdown
        updateActiveState();
    }
    
    // Update active state with enhanced visual indicators
    function updateActiveState() {
        const options = document.querySelectorAll('.model-option');
        options.forEach(option => {
            const checkmark = option.querySelector('.model-option-check');
            const iconContainer = option.querySelector('.model-icon-container');
            const isActive = option.dataset.value === modelSelector.value;
            const modelValue = option.dataset.value;
            const modelData = models.find(m => m.value === modelValue);
            
            option.classList.toggle('active', isActive);
            if (checkmark) checkmark.style.opacity = isActive ? '1' : '0';
            if (iconContainer) {
                iconContainer.style.transform = isActive ? 'scale(1.05)' : 'scale(1)';
                // Use the correct model color for each option
                if (modelData) {
                    iconContainer.style.backgroundColor = `${modelData.color}15`;
                }
            }
        });
    }
    
    // Initialize the model menu
    const modelMenu = createModelMenu();
    
    // Add click event to container to toggle the menu
    modelSelectorContainer.addEventListener('click', (e) => {
        // Prevent default select behavior
        e.preventDefault();
        e.stopPropagation();
        
        // Toggle menu
        const isActive = modelMenu.classList.contains('active');
        toggleMenu(!isActive);
    });
    
    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!modelSelectorContainer.contains(e.target)) {
            toggleMenu(false);
        }
    });
    
    // Set initial state
    updateActiveState();
});