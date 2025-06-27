// Основной JavaScript файл для Estate Parser Web Interface

// Глобальные переменные
let statusCheckInterval;
let realTimeUpdates = {};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Принудительно устанавливаем светлую тему
    document.documentElement.setAttribute('data-bs-theme', 'light');
    document.body.setAttribute('data-bs-theme', 'light');
    
    initializeStatusCheck();
    initializeRealTimeUpdates();
    initializeTooltips();
    initializeModals();
    initializeSearchAutocomplete();
});

// Проверка статуса системы
async function checkSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        const indicator = document.getElementById('status-indicator');
        const text = document.getElementById('status-text');
        
        if (data.status === 'healthy') {
            indicator.className = 'bi bi-circle-fill text-success';
            text.textContent = 'Система работает';
            indicator.title = 'Система работает нормально';
        } else {
            indicator.className = 'bi bi-circle-fill text-danger';
            text.textContent = 'Ошибка системы';
            indicator.title = data.error || 'Ошибка системы';
        }
    } catch (error) {
        const indicator = document.getElementById('status-indicator');
        const text = document.getElementById('status-text');
        
        indicator.className = 'bi bi-circle-fill text-warning';
        text.textContent = 'Нет связи';
        indicator.title = 'Нет связи с сервером';
    }
}

function initializeStatusCheck() {
    checkSystemStatus();
    statusCheckInterval = setInterval(checkSystemStatus, 30000);
}

// Real-time обновления
function initializeRealTimeUpdates() {
    if (document.querySelector('.stats-card')) {
        setInterval(updateDashboardStats, 60000);
    }
    
    // Логи теперь не отображаются в интерфейсе
    
    if (document.querySelector('.scraping-status')) {
        setInterval(updateScrapingStatus, 10000);
    }
}

// Обновление статистики дашборда
async function updateDashboardStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        // Обновляем карточки статистики
        updateStatCard('total-unique-ads', stats.total_unique_ads);
        updateStatCard('total-ads', stats.total_original_ads);
        updateStatCard('duplicates', stats.total_duplicates);
        updateStatCard('realtor-ads', stats.realtor_ads);
        
        // Обновляем ratio
        const ratioElement = document.getElementById('deduplication-ratio');
        if (ratioElement) {
            ratioElement.textContent = `${(stats.deduplication_ratio * 100).toFixed(1)}%`;
        }
    } catch (error) {
        console.error('Ошибка обновления статистики:', error);
    }
}

function updateStatCard(elementId, newValue) {
    const element = document.getElementById(elementId);
    if (element && element.textContent !== newValue.toString()) {
        element.textContent = newValue.toLocaleString();
        element.parentElement.classList.add('highlight-new');
        setTimeout(() => {
            element.parentElement.classList.remove('highlight-new');
        }, 3000);
    }
}

// Управление парсингом
async function startScraping(source) {
    const button = document.querySelector(`[data-source="${source}"]`);
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="loading-spinner"></span> Запуск...';
    }
    
    try {
        const response = await fetch(`/api/scraping/start/${source}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const data = await response.json();
            showNotification('success', `Парсинг ${source} запущен (ID: ${data.job_id})`);
            setTimeout(() => updateScrapingStatus(), 2000);
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        showNotification('error', `Ошибка запуска парсинга ${source}: ${error.message}`);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="bi bi-play"></i> Запустить';
        }
    }
}

async function stopScraping(jobId) {
    try {
        const response = await fetch(`/api/scraping/stop/${jobId}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('success', 'Парсинг остановлен');
            setTimeout(() => updateScrapingStatus(), 1000);
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        showNotification('error', `Ошибка остановки парсинга: ${error.message}`);
    }
}

// Обновление статуса парсинга
async function updateScrapingStatus() {
    try {
        const response = await fetch('/api/scraping/jobs');
        const jobs = await response.json();
        
        const container = document.getElementById('scraping-jobs');
        if (!container) return;
        
        container.innerHTML = '';
        
        jobs.forEach(job => {
            const jobElement = createJobElement(job);
            container.appendChild(jobElement);
        });
    } catch (error) {
        console.error('Ошибка обновления статуса парсинга:', error);
    }
}

function createJobElement(job) {
    const div = document.createElement('div');
    div.className = 'col-md-4 mb-3';
    
    let statusClass = 'secondary';
    let statusIcon = 'clock';
    
    switch (job.status) {
        case 'выполняется':
            statusClass = 'primary';
            statusIcon = 'arrow-clockwise';
            break;
        case 'завершено':
            statusClass = 'success';
            statusIcon = 'check-circle';
            break;
        case 'ошибка':
            statusClass = 'danger';
            statusIcon = 'x-circle';
            break;
        case 'остановлено':
            statusClass = 'warning';
            statusIcon = 'stop-circle';
            break;
    }
    
    div.innerHTML = `
        <div class="card">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="card-title mb-0">${job.config}</h6>
                    <span class="badge bg-${statusClass}">
                        <i class="bi bi-${statusIcon}"></i> ${job.status}
                    </span>
                </div>
                <p class="card-text small text-muted">
                    ID: ${job.id}<br>
                    Создан: ${formatDateTime(job.created_at)}
                    ${job.started_at ? `<br>Запущен: ${formatDateTime(job.started_at)}` : ''}
                    ${job.finished_at ? `<br>Завершен: ${formatDateTime(job.finished_at)}` : ''}
                </p>
                <div class="btn-group btn-group-sm w-100">
                    <button class="btn btn-outline-primary" onclick="showJobLogs('${job.id}')">
                        <i class="bi bi-journal-text"></i> Логи
                    </button>
                    ${job.status === 'выполняется' ? 
                        `<button class="btn btn-outline-danger" onclick="stopScraping('${job.id}')">
                            <i class="bi bi-stop"></i> Стоп
                        </button>` : ''
                    }
                </div>
            </div>
        </div>
    `;
    
    return div;
}

// Управление обработкой
async function startProcessing(type) {
    const button = document.querySelector(`[data-process="${type}"]`);
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="loading-spinner"></span> Запуск...';
    }
    
    try {
        const response = await fetch(`/api/process/${type}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('success', `Обработка ${type} запущена`);
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (error) {
        showNotification('error', `Ошибка запуска обработки: ${error.message}`);
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = button.getAttribute('data-original-text') || 'Запустить';
        }
    }
}

// Работа с логами
async function showJobLogs(jobId) {
    try {
        const response = await fetch(`/api/scraping/log/${jobId}`);
        const logs = await response.json();
        
        const modal = new bootstrap.Modal(document.getElementById('logsModal'));
        const logsContainer = document.getElementById('modal-logs-content');
        
        logsContainer.innerHTML = logs.map(log => 
            `<div class="log-line">${escapeHtml(log)}</div>`
        ).join('');
        
        modal.show();
    } catch (error) {
        showNotification('error', 'Ошибка загрузки логов');
    }
}

// Фильтрация объявлений
function applyFilters() {
    const form = document.getElementById('filters-form');
    if (!form) return;
    
    const formData = new FormData(form);
    const params = new URLSearchParams();
    
    for (let [key, value] of formData.entries()) {
        if (value.trim()) {
            params.append(key, value);
        }
    }
    
    // Сохраняем текущий offset для пагинации
    const currentOffset = new URLSearchParams(window.location.search).get('offset') || '0';
    params.set('offset', '0'); // Сброс к первой странице при новом поиске
    
    window.location.search = params.toString();
}

function clearFilters() {
    const form = document.getElementById('filters-form');
    if (form) {
        form.reset();
        window.location.search = '';
    }
}

function clearSearch() {
    const searchInput = document.querySelector('input[name="query"]');
    if (searchInput) {
        searchInput.value = '';
        applyFilters();
    }
}

// Сохранение истории поиска
function saveSearchHistory(query) {
    if (!query || query.trim().length < 2) return;
    
    let history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    const cleanQuery = query.trim();
    
    // Удаляем дубликаты и добавляем в начало
    history = history.filter(item => item !== cleanQuery);
    history.unshift(cleanQuery);
    
    // Ограничиваем историю 10 элементами
    history = history.slice(0, 10);
    
    localStorage.setItem('searchHistory', JSON.stringify(history));
}

// Загрузка истории поиска
function loadSearchHistory() {
    return JSON.parse(localStorage.getItem('searchHistory') || '[]');
}

// Инициализация автодополнения поиска
function initializeSearchAutocomplete() {
    const searchInput = document.querySelector('input[name="query"]');
    if (!searchInput) return;
    
    // Создаем контейнер для автодополнения
    const autocompleteContainer = document.createElement('div');
    autocompleteContainer.className = 'search-autocomplete';
    autocompleteContainer.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #ddd;
        border-top: none;
        border-radius: 0 0 4px 4px;
        max-height: 200px;
        overflow-y: auto;
        z-index: 1000;
        display: none;
    `;
    
    // Добавляем контейнер после input-group
    const inputGroup = searchInput.closest('.input-group');
    inputGroup.style.position = 'relative';
    inputGroup.appendChild(autocompleteContainer);
    
    // Обработчик фокуса - показываем историю
    searchInput.addEventListener('focus', function() {
        showSearchHistory(autocompleteContainer);
    });
    
    // Обработчик потери фокуса - скрываем автодополнение
    searchInput.addEventListener('blur', function() {
        setTimeout(() => {
            autocompleteContainer.style.display = 'none';
        }, 200);
    });
    
    // Обработчик ввода
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();
        if (query.length > 0) {
            showSearchSuggestions(autocompleteContainer, query);
        } else {
            showSearchHistory(autocompleteContainer);
        }
    });
}

function showSearchHistory(container) {
    const history = loadSearchHistory();
    if (history.length === 0) {
        container.style.display = 'none';
        return;
    }
    
    container.innerHTML = history.map(item => 
        `<div class="search-suggestion" onclick="selectSearchSuggestion('${item.replace(/'/g, "\\'")}')" 
             style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #eee;">
            <i class="bi bi-clock-history text-muted me-2"></i>${item}
        </div>`
    ).join('');
    
    container.style.display = 'block';
}

function showSearchSuggestions(container, query) {
    const history = loadSearchHistory();
    const filtered = history.filter(item => 
        item.toLowerCase().includes(query.toLowerCase())
    );
    
    if (filtered.length === 0) {
        container.style.display = 'none';
        return;
    }
    
    container.innerHTML = filtered.map(item => 
        `<div class="search-suggestion" onclick="selectSearchSuggestion('${item.replace(/'/g, "\\'")}')" 
             style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #eee;">
            <i class="bi bi-search text-muted me-2"></i>${item}
        </div>`
    ).join('');
    
    container.style.display = 'block';
}

function selectSearchSuggestion(query) {
    const searchInput = document.querySelector('input[name="query"]');
    if (searchInput) {
        searchInput.value = query;
        applyFilters();
    }
}

// Расширенная функция применения фильтров с сохранением истории
function applyFiltersWithHistory() {
    const searchInput = document.querySelector('input[name="query"]');
    if (searchInput && searchInput.value.trim()) {
        saveSearchHistory(searchInput.value.trim());
    }
    applyFilters();
}

// Модальные окна для объявлений
function showAdModal(adId) {
    fetch(`/api/ads/unique/${adId}`)
        .then(response => response.json())
        .then(data => {
            const modal = new bootstrap.Modal(document.getElementById('adModal'));
            populateAdModal(data);
            modal.show();
        })
        .catch(error => {
            showNotification('error', 'Ошибка загрузки объявления');
        });
}

function populateAdModal(ad) {
    document.getElementById('modal-ad-title').textContent = ad.title;
    
    // Цена с правильной валютой
    let priceText = 'Цена не указана';
    if (ad.price) {
        if (ad.currency === 'USD') {
            priceText = `$${ad.price.toLocaleString()}`;
        } else if (ad.currency === 'SOM') {
            priceText = `${ad.price.toLocaleString()} сом`;
        } else if (ad.currency === 'EUR') {
            priceText = `€${ad.price.toLocaleString()}`;
        } else {
            priceText = `${ad.price.toLocaleString()} ${ad.currency || ''}`;
        }
    }
    document.getElementById('modal-ad-price').textContent = priceText;
    
    document.getElementById('modal-ad-description').textContent = 
        ad.description || 'Описание отсутствует';
    
    // Заполняем характеристики
    const characteristics = document.getElementById('modal-ad-characteristics');
    characteristics.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <strong>Площадь:</strong> ${ad.area_sqm ? ad.area_sqm + ' м²' : 'Не указана'}<br>
                <strong>Комнаты:</strong> ${ad.rooms || 'Не указано'}<br>
                <strong>Этаж:</strong> ${ad.floor ? `${ad.floor}/${ad.total_floors || '?'}` : 'Не указан'}
            </div>
            <div class="col-md-6">
                <strong>Состояние:</strong> ${ad.condition || 'Не указано'}<br>
                <strong>Мебель:</strong> ${ad.furniture || 'Не указано'}<br>
                <strong>Риэлтор:</strong> ${ad.is_realtor ? 'Да' : 'Нет'}
            </div>
        </div>
    `;
    
    // Заполняем адрес
    const location = ad.location;
    document.getElementById('modal-ad-location').textContent = 
        location ? `${location.city || ''}, ${location.district || ''}, ${location.address || ''}`.replace(/^,\s*|,\s*$/g, '') : 'Адрес не указан';
    
    // Заполняем фотографии
    const photosContainer = document.getElementById('modal-ad-photos');
    if (ad.photos && ad.photos.length > 0) {
        photosContainer.innerHTML = ad.photos.map((photo, index) => 
            `<div class="col-md-4 mb-2">
                <img src="${photo.url}" class="img-fluid rounded" alt="Фото ${index + 1}" 
                     style="height: 150px; object-fit: cover; cursor: pointer;"
                     onclick="showPhotoModal('${photo.url}')">
            </div>`
        ).join('');
    } else {
        photosContainer.innerHTML = '<p class="text-muted">Фотографии отсутствуют</p>';
    }
    
    // Дубликаты
    const duplicatesInfo = document.getElementById('modal-ad-duplicates');
    duplicatesInfo.innerHTML = `
        <span class="badge bg-${ad.duplicates_count > 0 ? 'warning' : 'success'}">
            ${ad.duplicates_count} дубликатов
        </span>
    `;
}

// Утилиты
function formatDateTime(dateString) {
    if (!dateString) return '';
    return new Date(dateString).toLocaleString('ru-RU');
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

function showNotification(type, message) {
    const alertClass = type === 'error' ? 'danger' : type;
    const alertHTML = `
        <div class="alert alert-${alertClass} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHTML);
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        const alert = document.querySelector('.alert:last-of-type');
        if (alert) {
            bootstrap.Alert.getOrCreateInstance(alert).close();
        }
    }, 5000);
}

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function initializeModals() {
    // Сохранение оригинального текста кнопок
    document.querySelectorAll('button[data-process]').forEach(button => {
        button.setAttribute('data-original-text', button.innerHTML);
    });
}

// Функции для графиков
function createChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            },
        },
        scales: type !== 'doughnut' && type !== 'pie' ? {
            y: {
                beginAtZero: true
            }
        } : {}
    };
    
    return new Chart(ctx, {
        type: type,
        data: data,
        options: { ...defaultOptions, ...options }
    });
}

// Экспорт функций для глобального использования
window.startScraping = startScraping;
window.stopScraping = stopScraping;
window.startProcessing = startProcessing;
window.applyFilters = applyFilters;
window.applyFiltersWithHistory = applyFiltersWithHistory;
window.clearFilters = clearFilters;
window.clearSearch = clearSearch;
window.selectSearchSuggestion = selectSearchSuggestion;
window.showAdModal = showAdModal;
window.showJobLogs = showJobLogs;
window.createChart = createChart;
window.formatDateTime = formatDateTime;
window.escapeHtml = escapeHtml;
window.showNotification = showNotification; 