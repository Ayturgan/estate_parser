// Основной JavaScript файл для Estate Parser Web Interface

// Глобальные переменные
let statusCheckInterval;
let realTimeUpdates = {};

// Функции для работы с токенами авторизации
function setAuthToken(token) {
    console.log('🔑 setAuthToken вызван с:', token ? '✅ Токен получен' : '❌ Токен пустой');
    console.log('🔑 Домен:', window.location.host);
    console.log('🔑 Протокол:', window.location.protocol);
    
    localStorage.setItem('auth_token', token);
    console.log('🔑 Токен сохранен в localStorage');
    
    // Также устанавливаем в cookie для совместимости
    document.cookie = `ws_token=${token}; path=/; samesite=strict`;
    console.log('🔑 Токен сохранен в cookie');
    
    // Отправляем событие для WebSocket клиента с токеном
    window.dispatchEvent(new CustomEvent('auth_token_received', { detail: { token } }));
    console.log('🔑 Событие auth_token_received отправлено');
}

function getAuthToken() {
    // Единственный источник правды - localStorage
    const token = localStorage.getItem('auth_token');
    console.log('🔑 getAuthToken вызван:', token ? '✅ Токен найден' : '❌ Токен НЕ найден');
    console.log('🔑 localStorage auth_token:', token);
    return token;
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }
    return null;
}

function removeAuthToken() {
    localStorage.removeItem('auth_token');
    // Удаляем WebSocket token cookie
    document.cookie = 'ws_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    // Отправляем событие для WebSocket клиента
    window.dispatchEvent(new Event('auth_logout'));
}

// Экспортируем функцию для WebSocket клиента
window.getAuthToken = getAuthToken;

function setAuthHeaders(headers = {}) {
    const token = getAuthToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Принудительно устанавливаем светлую тему
    document.documentElement.setAttribute('data-bs-theme', 'light');
    document.body.setAttribute('data-bs-theme', 'light');
    
    initializeStatusCheck();
    initializeTooltips();
    initializeModals();
    initializeSearchAutocomplete();
    
    // WebSocket инициализируется автоматически в websocket.js
});

// Проверка статуса системы (только при загрузке страницы)
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
    // Проверяем статус только один раз при загрузке
    // Дальнейшие обновления через WebSocket
    checkSystemStatus();
}

// Управление парсингом
async function startScraping(source) {
    try {
        const response = await fetch('/api/scraping/start', {
            method: 'POST',
            headers: setAuthHeaders({'Content-Type': 'application/json'}),
            body: JSON.stringify({ source: source })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Убираем уведомление - WebSocket уже покажет его
            console.log(`Парсинг ${source} запущен через API`);
        } else {
            showNotification('error', result.message || 'Ошибка запуска парсинга');
        }
    } catch (error) {
        console.error('Error starting scraping:', error);
        showNotification('error', 'Ошибка запуска парсинга');
    }
}

async function stopScraping(jobId) {
    try {
        const response = await fetch(`/api/scraping/stop/${jobId}`, {
            method: 'POST',
            headers: setAuthHeaders()
        });
        
        if (response.ok) {
            showNotification('info', 'Парсинг остановлен');
        } else {
            showNotification('error', 'Ошибка остановки парсинга');
        }
    } catch (error) {
        console.error('Error stopping scraping:', error);
        showNotification('error', 'Ошибка остановки парсинга');
    }
}

// Функция для создания элемента задачи (используется WebSocket клиентом)
function createJobElement(job) {
    const jobElement = document.createElement('div');
    jobElement.className = 'job-item card mb-2';
    jobElement.setAttribute('data-job-id', job.id);
    
    const statusClass = getStatusClass(job.status);
    const statusText = getStatusText(job.status);
    
    jobElement.innerHTML = `
        <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">${job.config}</h6>
                    <small class="text-muted">ID: ${job.id}</small>
                </div>
                <span class="badge ${statusClass} status-badge">${statusText}</span>
            </div>
            <div class="progress mt-2" style="height: 4px;">
                <div class="progress-bar" role="progressbar" style="width: 0%"></div>
            </div>
            <div class="d-flex justify-content-between align-items-center mt-2">
                <small class="text-muted">Создано: ${formatDateTime(job.created_at)}</small>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-sm" onclick="showJobLogs('${job.id}')">
                        <i class="bi bi-file-text"></i> Логи
                    </button>
                    ${job.status === 'выполняется' ? 
                        `<button class="btn btn-outline-danger btn-sm" onclick="stopScraping('${job.id}')">
                            <i class="bi bi-stop-circle"></i> Остановить
                        </button>` : ''
                    }
                </div>
            </div>
        </div>
    `;
    
    return jobElement;
}

function getStatusClass(status) {
    const statusMap = {
        'ожидание': 'bg-secondary',
        'выполняется': 'bg-warning',
        'завершено': 'bg-success',
        'ошибка': 'bg-danger',
        'остановлено': 'bg-info'
    };
    return statusMap[status] || 'bg-secondary';
}

function getStatusText(status) {
    const statusMap = {
        'ожидание': 'Ожидание',
        'выполняется': 'Выполняется',
        'завершено': 'Завершено',
        'ошибка': 'Ошибка',
        'остановлено': 'Остановлено'
    };
    return statusMap[status] || status;
}

// Экспортируем функцию для WebSocket клиента
window.createJobElement = createJobElement;

async function startProcessing(type) {
    try {
        const response = await fetch('/api/processing/start', {
            method: 'POST',
            headers: setAuthHeaders({'Content-Type': 'application/json'}),
            body: JSON.stringify({ type: type })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('success', `Обработка ${type} запущена`);
        } else {
            showNotification('error', result.message || 'Ошибка запуска обработки');
        }
    } catch (error) {
        console.error('Error starting processing:', error);
        showNotification('error', 'Ошибка запуска обработки');
    }
}

async function showJobLogs(jobId) {
    try {
        const response = await fetch(`/api/scraping/log/${jobId}`, {
            headers: setAuthHeaders()
        });
        
        if (response.ok) {
            const logs = await response.json();
            
            const modal = new bootstrap.Modal(document.getElementById('logsModal'));
            const modalBody = document.getElementById('logsModalBody');
            
            // Добавляем заголовок с информацией о задаче
            modalBody.innerHTML = `
                <div class="log-header mb-3">
                    <h6>Логи парсинга</h6>
                    <small class="text-muted">Job ID: ${jobId}</small>
                </div>
            `;
            
            // Добавляем логи
            modalBody.innerHTML += logs.log.map(logLine => {
                // Парсим строку лога для извлечения timestamp, level и message
                const logMatch = logLine.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] (.+)$/);
                if (logMatch) {
                    const [, timestamp, level, message] = logMatch;
                    return `<div class="log-entry">
                        <small class="log-timestamp">${timestamp}</small>
                        <span class="log-level log-${level.toLowerCase()}">${level.toUpperCase()}</span>
                        <span class="log-message">${escapeHtml(message)}</span>
                    </div>`;
                } else {
                    return `<div class="log-entry">
                        <span class="log-message">${escapeHtml(logLine)}</span>
                    </div>`;
                }
            }).join('');
            
            modal.show();
        } else {
            showNotification('error', 'Ошибка загрузки логов');
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        showNotification('error', 'Ошибка загрузки логов');
    }
}

// Функции фильтрации и поиска
function applyFilters() {
    const form = document.getElementById('filters-form');
    if (form) {
        form.submit();
    }
}

function clearFilters() {
    const form = document.getElementById('filters-form');
    if (form) {
        form.reset();
        form.submit();
    }
}

function clearSearch() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = '';
        applyFilters();
    }
}

// Функции для работы с историей поиска
function saveSearchHistory(query) {
    if (!query || query.trim().length < 2) return;
    
    let history = JSON.parse(localStorage.getItem('search_history') || '[]');
    history = history.filter(item => item !== query);
    history.unshift(query);
    history = history.slice(0, 10); // Максимум 10 записей
    
    localStorage.setItem('search_history', JSON.stringify(history));
}

function loadSearchHistory() {
    return JSON.parse(localStorage.getItem('search_history') || '[]');
}

function initializeSearchAutocomplete() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    
    let suggestionsContainer = null;
    
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();
        
        if (suggestionsContainer) {
            suggestionsContainer.remove();
            suggestionsContainer = null;
        }
        
        if (query.length < 2) return;
        
        const history = loadSearchHistory();
        const filteredHistory = history.filter(item => 
            item.toLowerCase().includes(query.toLowerCase())
        );
        
        if (filteredHistory.length > 0) {
            suggestionsContainer = document.createElement('div');
            suggestionsContainer.className = 'search-suggestions';
            suggestionsContainer.style.cssText = `
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
            `;
            
            showSearchSuggestions(suggestionsContainer, filteredHistory);
            this.parentElement.style.position = 'relative';
            this.parentElement.appendChild(suggestionsContainer);
        }
    });
    
    searchInput.addEventListener('blur', function() {
        setTimeout(() => {
            if (suggestionsContainer) {
                suggestionsContainer.remove();
                suggestionsContainer = null;
            }
        }, 200);
    });
    
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            saveSearchHistory(this.value.trim());
        }
    });
}

function showSearchSuggestions(container, suggestions) {
    container.innerHTML = suggestions.map(suggestion => `
        <div class="suggestion-item" style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #eee;">
            <i class="bi bi-clock-history me-2"></i>
            ${escapeHtml(suggestion)}
        </div>
    `).join('');
    
    container.addEventListener('click', function(e) {
        if (e.target.classList.contains('suggestion-item')) {
            const query = e.target.textContent.trim();
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.value = query;
                applyFiltersWithHistory();
            }
            this.remove();
        }
    });
}

function selectSearchSuggestion(query) {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = query;
        applyFiltersWithHistory();
    }
}

function applyFiltersWithHistory() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        saveSearchHistory(searchInput.value.trim());
    }
    applyFilters();
}

// Функции для работы с модальными окнами объявлений
function showAdModal(adId) {
    fetch(`/api/ads/${adId}`, {
        headers: setAuthHeaders()
    })
    .then(response => response.json())
    .then(ad => {
        populateAdModal(ad);
        const modal = new bootstrap.Modal(document.getElementById('adModal'));
        modal.show();
    })
    .catch(error => {
        console.error('Error loading ad:', error);
        showNotification('error', 'Ошибка загрузки объявления');
    });
}

function populateAdModal(ad) {
    const modalTitle = document.getElementById('adModalTitle');
    const modalBody = document.getElementById('adModalBody');
    
    if (modalTitle) {
        modalTitle.textContent = ad.title || 'Объявление';
    }
    
    if (modalBody) {
        modalBody.innerHTML = `
            <div class="row">
                <div class="col-md-8">
                    <h5>${escapeHtml(ad.title || '')}</h5>
                    <p class="text-muted">${escapeHtml(ad.description || '')}</p>
                    
                    <div class="row mb-3">
                        <div class="col-6">
                            <strong>Цена:</strong> ${ad.price ? `${ad.price.toLocaleString()} ₸` : 'Не указана'}
                        </div>
                        <div class="col-6">
                            <strong>Площадь:</strong> ${ad.area ? `${ad.area} м²` : 'Не указана'}
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-6">
                            <strong>Комнаты:</strong> ${ad.rooms || 'Не указано'}
                        </div>
                        <div class="col-6">
                            <strong>Этаж:</strong> ${ad.floor || 'Не указан'}
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <strong>Адрес:</strong> ${escapeHtml(ad.address || 'Не указан')}
                    </div>
                    
                    <div class="mb-3">
                        <strong>Телефон:</strong> 
                        <a href="tel:${ad.phone || ''}">${escapeHtml(ad.phone || 'Не указан')}</a>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h6 class="mb-0">Информация</h6>
                        </div>
                        <div class="card-body">
                            <p><strong>Источник:</strong> ${escapeHtml(ad.source || '')}</p>
                            <p><strong>Дата создания:</strong> ${formatDateTime(ad.created_at)}</p>
                            <p><strong>Статус:</strong> 
                                <span class="badge ${ad.is_duplicate ? 'bg-warning' : 'bg-success'}">
                                    ${ad.is_duplicate ? 'Дубликат' : 'Уникальное'}
                                </span>
                            </p>
                            ${ad.unique_ad_id ? `
                                <p><strong>Оригинал:</strong> 
                                    <a href="#" onclick="showAdModal(${ad.unique_ad_id})">ID ${ad.unique_ad_id}</a>
                                </p>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
            
            ${ad.photos && ad.photos.length > 0 ? `
                <div class="mt-3">
                    <h6>Фотографии (${ad.photos.length})</h6>
                    <div class="row">
                        ${ad.photos.map(photo => `
                            <div class="col-md-3 mb-2">
                                <img src="${photo.url}" class="img-fluid rounded" alt="Фото объявления">
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        `;
    }
}

// Вспомогательные функции
function formatDateTime(dateString) {
    if (!dateString) return 'Не указано';
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Глобальный реестр активных уведомлений для предотвращения дублирования
window.activeNotifications = window.activeNotifications || new Set();

// Очистка реестра при загрузке страницы (на случай если остались "призраки")
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем реестр уведомлений
    window.activeNotifications = window.activeNotifications || new Set();
    window.activeNotifications.clear();
    console.log('Реестр уведомлений очищен при загрузке страницы');
    
    // Показываем серверные сообщения через единую систему уведомлений
    setTimeout(() => {
        showServerMessages();
    }, 100); // Небольшая задержка для гарантии загрузки всех скриптов
});

function showNotification(type, message) {
    // Создаем уникальный ключ для сообщения
    const notificationKey = `${type}:${message}`;
    
    // Проверяем не показывается ли уже такое же уведомление
    if (window.activeNotifications.has(notificationKey)) {
        console.log('Дублирующее уведомление заблокировано:', message);
        return; // Не показываем дублирующее уведомление
    }
    
    // Добавляем в реестр активных уведомлений
    window.activeNotifications.add(notificationKey);
    
    const alertClass = type === 'error' ? 'danger' : type;
    const notificationId = 'notification-' + Date.now() + Math.random().toString(36).substr(2, 9);
    
    const alertHtml = `
        <div id="${notificationId}" class="alert alert-${alertClass} alert-dismissible fade show position-fixed notification-alert" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 400px;" 
             role="alert" data-notification-key="${notificationKey}">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
        </div>
    `;
    
    // Добавляем уведомление в конец body, но с правильным позиционированием
    document.body.insertAdjacentHTML('beforeend', alertHtml);
    
    // Сдвигаем существующие уведомления вниз
    repositionNotifications();
    
    // Обработчик для удаления из реестра при закрытии
    const notificationElement = document.getElementById(notificationId);
    if (notificationElement) {
        // Обработчик для кнопки закрытия
        const closeButton = notificationElement.querySelector('.btn-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                window.activeNotifications.delete(notificationKey);
                repositionNotifications();
            });
        }
        
        // Обработчик для Bootstrap alert close событий (например, при нажатии Escape)
        notificationElement.addEventListener('closed.bs.alert', () => {
            window.activeNotifications.delete(notificationKey);
            repositionNotifications();
        });
    }
    
    // Автоматически убираем уведомление через 5 секунд
    setTimeout(() => {
        const notification = document.getElementById(notificationId);
        if (notification) {
            // Удаляем из реестра
            window.activeNotifications.delete(notificationKey);
            
            // Плавно скрываем
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => {
                notification.remove();
                repositionNotifications();
            }, 300);
        }
    }, 5000);
}

// Функция для показа серверных сообщений через единую систему
function showServerMessages() {
    const serverMessages = document.querySelectorAll('.alert:not(.notification-alert)');
    console.log(`Найдено ${serverMessages.length} серверных сообщений для преобразования`);
    
    serverMessages.forEach((alert, index) => {
        const message = alert.textContent.trim();
        const alertClass = alert.className;
        let type = 'info';
        
        if (alertClass.includes('alert-danger')) type = 'error';
        else if (alertClass.includes('alert-success')) type = 'success';
        else if (alertClass.includes('alert-warning')) type = 'warning';
        
        console.log(`Преобразуем серверное сообщение ${index + 1}: ${type} - ${message}`);
        
        // Показываем через единую систему и удаляем оригинальное уведомление
        showNotification(type, message);
        alert.remove();
    });
}

// Функция для правильного позиционирования уведомлений
function repositionNotifications() {
    const notifications = document.querySelectorAll('.notification-alert');
    notifications.forEach((notification, index) => {
        const topOffset = 20 + (index * 80); // 80px между уведомлениями
        notification.style.top = topOffset + 'px';
        notification.style.transition = 'all 0.3s ease';
    });
}

// Экспортируем функции для использования в других скриптах
window.showNotification = showNotification;
window.repositionNotifications = repositionNotifications;
window.showServerMessages = showServerMessages;

// Функция для отладки - проверка состояния реестра уведомлений
window.debugNotifications = function() {
    console.log('=== ДИАГНОСТИКА УВЕДОМЛЕНИЙ ===');
    console.log('Активные уведомления в реестре:', Array.from(window.activeNotifications));
    console.log('Уведомления в DOM:', document.querySelectorAll('.notification-alert').length);
    console.log('Серверные сообщения:', document.querySelectorAll('.alert:not(.notification-alert)').length);
    console.log('Всего alert элементов:', document.querySelectorAll('.alert').length);
    
    // Проверяем на дубликаты
    const allMessages = Array.from(window.activeNotifications);
    const duplicates = allMessages.filter((item, index) => allMessages.indexOf(item) !== index);
    if (duplicates.length > 0) {
        console.warn('⚠️ Найдены дубликаты в реестре:', duplicates);
    }
    
    return {
        active: Array.from(window.activeNotifications),
        inDOM: document.querySelectorAll('.notification-alert').length,
        serverMessages: document.querySelectorAll('.alert:not(.notification-alert)').length,
        duplicates: duplicates
    };
};

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function initializeModals() {
    // Инициализация модальных окон Bootstrap
    const modalTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="modal"]'));
    modalTriggerList.map(function (modalTriggerEl) {
        return new bootstrap.Modal(modalTriggerEl);
    });
}

// Функции для работы с графиками
function createChart(canvasId, type, data, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    
    const ctx = canvas.getContext('2d');
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom'
            }
        }
    };
    
    return new Chart(ctx, {
        type: type,
        data: data,
        options: { ...defaultOptions, ...options }
    });
} 