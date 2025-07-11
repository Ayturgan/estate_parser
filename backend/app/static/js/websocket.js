/**
 * WebSocket клиент для real-time обновлений
 */
class WebSocketClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnected = false;
        this.eventHandlers = new Map();
        this.notificationDebounce = {};
        
        // Cлушатель для автоматического подключения
        this.initAuthListener();
    }
    
    // Подключаемся только после успешной аутентификации
    initAuthListener() {
        // Подключаемся при получении токена
        window.addEventListener('auth_token_received', (e) => {
            console.log('🔑 Получен токен, запускаем WebSocket...');
            this.connect(e.detail.token);
        });
        
        // Отключаемся при выходе из системы
        window.addEventListener('auth_logout', () => {
            console.log('🚪 Выход из системы, закрываем WebSocket');
            this.disconnect();
        });
        
        // Проверяем, есть ли уже токен при загрузке страницы
        const existingToken = getAuthToken();
        if (existingToken) {
            console.log('🔑 Найден существующий токен, подключаемся к WebSocket...');
            this.connect(existingToken);
        }
    }
    
    // Система событий
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }
    
    off(eventType, handler) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    emit(eventType, data) {
        if (this.eventHandlers.has(eventType)) {
            this.eventHandlers.get(eventType).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in event handler for ${eventType}:`, error);
                }
            });
        }
    }
    
    connect(token) {
        if (!token) {
            console.error('❌ Попытка подключения WebSocket без токена.');
            return;
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocket уже подключен. Переподключаемся для обновления токена...');
            this.reconnect();
            return;
        }

        console.log('✅ Попытка подключения WebSocket...');
        
        const fullToken = token.startsWith('Bearer ') ? token : `Bearer ${token}`;
        
        // Динамический URL на основе текущего хоста
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(fullToken)}`;
        
        console.log('Подключаемся к WebSocket:', wsUrl);
        
        this.ws = new WebSocket(wsUrl);
            
        this.ws.onopen = () => {
            console.log('✅ WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            // Очищаем дебаунсинг при переподключении
            this.notificationDebounce = {};
            // Очищаем анимации прогресса при переподключении
            this.stopScrapingProgressAnimation();
            this.stopDuplicateProgressAnimation();
            setRealtimeIndicator(true);
            
            // Отправляем запрос на начальные данные
            this.send({
                type: 'request_stats'
            });
            
            // Эмитим событие о подключении
            this.emit('connected', {});
            
            // Запрашиваем статус автоматизации если мы на странице автоматизации
            if (window.location.pathname === '/automation') {
                console.log('🔗 На странице автоматизации, запрашиваем статус...');
                this.send({
                    type: 'request_automation_status'
                });
                
                // Запрашиваем источники парсинга
                this.send({
                    type: 'request_scraping_sources'
                });
            }
        };
        
        this.ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.ws.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code);
            this.isConnected = false;
            setRealtimeIndicator(false);
            
            if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnect();
            }
        };
    }
    
    reconnect() {
        if (this.ws) {
            this.ws.onclose = null; // Убираем обработчик, чтобы избежать зацикливания
            this.ws.close();
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Переподключение через ${delay}ms (попытка ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            const token = getAuthToken(); // Получаем свежий токен
            if (token) {
                this.connect(token);
            } else {
                console.error("Не удалось получить токен для переподключения.");
            }
        }, delay);
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close(1000);
        }
        
        // Очищаем все анимации прогресса
        this.stopScrapingProgressAnimation();
        this.stopDuplicateProgressAnimation();
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    handleMessage(data) {
        const { type, event_type, data: eventData } = data;
        
        if (type === 'event') {
            this.handleEvent(event_type, eventData);
        } else if (type === 'initial_stats') {
            this.handleInitialStats(eventData);
        } else if (type === 'connection_established') {
            console.log('🔗 WebSocket connection established:', eventData);
        } else if (type === 'pong') {
            // Pong для проверки соединения
            console.log('🏓 Pong received');
        } else {
            console.log('Unknown message type:', type);
        }
    }
    
    handleEvent(eventType, data) {
        console.log(`📡 Event received: ${eventType}`, data);
        
        // Эмитим событие для внешних обработчиков
        this.emit(eventType, data);
        
        // Внутренняя обработка событий
        switch (eventType) {
            case 'connected':
                // Событие подключения уже обработано в onopen
                break;
            case 'stats_update':
                this.updateDashboardStats(data);
                break;
                
            case 'automation_status':
                this.updateAutomationStatus(data);
                break;
                
            case 'automation_completed':
                this.handleAutomationCompleted(data);
                break;
                
            case 'automation_error':
                this.handleAutomationError(data);
                break;
                
            case 'scraping_progress':
                this.updateScrapingProgress(data);
                break;
                
            case 'scraping_started':
                this.handleScrapingStarted(data);
                break;
                
            case 'scraping_completed':
                this.handleScrapingCompleted(data);
                break;
                
            case 'scraping_error':
                this.handleScrapingError(data);
                break;
                
            case 'scraping_sources_update':
                this.updateScrapingSources(data);
                break;
                
            case 'duplicate_processing_progress':
                this.updateDuplicateProgress(data);
                break;
                
            case 'duplicate_processing_completed':
                this.handleDuplicateCompleted(data);
                break;
                
            case 'system_status':
                this.updateSystemStatus(data);
                break;
                
            case 'new_ad_created':
                this.handleNewAd(data);
                break;
                
            case 'duplicate_detected':
                this.handleDuplicateDetected(data);
                break;
                
            case 'realtor_detected':
                this.handleRealtorDetected(data);
                break;
                
            case 'success':
            case 'error':
            case 'warning':
            case 'info':
                this.showNotification(eventType, data);
                break;
                
            default:
                console.log(`Unhandled event type: ${eventType}`);
        }
    }
    
    handleInitialStats(data) {
        console.log('📊 Initial stats received:', data);
        
        // Обновляем статистику дашборда
        if (data.duplicate_stats) {
            this.updateDashboardStats(data.duplicate_stats);
        }
        
        // Обновляем статус системы
        this.updateSystemStatus({
            status: 'healthy',
            connections: data.websocket_connections
        });
    }
    
    // Обработчики для различных типов событий
    
    updateDashboardStats(stats) {
        // Обновляем карточки статистики
        this.updateStatCard('total-unique-ads', stats.total_unique_ads);
        this.updateStatCard('total-ads', stats.total_original_ads);
        this.updateStatCard('duplicates', stats.total_duplicates);
        this.updateStatCard('realtor-ads', stats.realtor_ads);
        
        // Обновляем ratio
        const ratioElement = document.getElementById('deduplication-ratio');
        if (ratioElement && stats.deduplication_ratio !== undefined) {
            ratioElement.textContent = `${stats.deduplication_ratio.toFixed(1)}%`;
        }
        
        // Обновляем графики если они есть
        this.updateDashboardCharts(stats);
    }
    
    updateStatCard(elementId, newValue) {
        const element = document.getElementById(elementId);
        if (element && element.textContent !== newValue.toString()) {
            element.textContent = newValue.toLocaleString();
            element.parentElement.classList.add('highlight-new');
            setTimeout(() => {
                element.parentElement.classList.remove('highlight-new');
            }, 3000);
        }
    }
    
    updateDashboardCharts(stats) {
        // Обновляем графики если они есть на странице
        if (window.dashboardCharts) {
            // Обновляем график дедупликации
            if (window.dashboardCharts.deduplicationChart) {
                window.dashboardCharts.deduplicationChart.data.datasets[0].data = [
                    stats.total_unique_ads, 
                    stats.total_duplicates
                ];
                window.dashboardCharts.deduplicationChart.update();
            }
        }
    }
    
    updateAutomationStatus(data) {
        // Обновляем статус автоматизации
        if (window.automationManager) {
            window.automationManager.updateUI(data);
        }
    }
    
    handleAutomationCompleted(data) {
        console.log('✅ Пайплайн автоматизации завершен успешно');
        if (window.automationManager) {
            window.automationManager.showNotification('✅ Пайплайн завершен успешно!', 'success');
            window.automationManager.loadStatus();
        }
    }
    
    handleAutomationError(data) {
        console.log('❌ Пайплайн автоматизации завершен с ошибками:', data.error);
        if (window.automationManager) {
            window.automationManager.showNotification('❌ Пайплайн завершен с ошибками', 'error');
            window.automationManager.loadStatus();
        }
    }
    
    updateScrapingProgress(data) {
        const { progress, total, completed, active } = data;
        const container = document.getElementById('scraping-progress-container');
        const progressBar = document.getElementById('scraping-progress');
        const progressText = document.getElementById('scraping-progress-text');
        
        if (container && progressBar && progressText) {
            if (active > 0) {
                // Показываем контейнер прогресса
                container.style.display = 'block';
                
                // Запускаем анимацию прогресса
                this.startScrapingProgressAnimation(progressBar, progressText);
                
                // Обновляем текст
                progressText.textContent = `Парсинг: ${completed}/${total} завершено, ${active} активно`;
            } else {
                // Скрываем контейнер прогресса
                container.style.display = 'none';
                this.stopScrapingProgressAnimation();
            }
        }
    }
    
    startScrapingProgressAnimation(progressBar, progressText) {
        if (!progressBar) return;
        
        // Очищаем предыдущую анимацию
        this.stopScrapingProgressAnimation();
        
        // Устанавливаем начальное состояние
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', '0');
        progressBar.classList.add('progress-bar-animated');
        
        const duration = 30000; // 30 секунд для парсинга
        const startTime = Date.now();
        
        // Сохраняем ID анимации
        this.scrapingProgressAnimation = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min((elapsed / duration) * 100, 85); // Максимум 85% для имитации
            
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', Math.round(progress));
            
            // Останавливаем анимацию если достигли максимума
            if (progress >= 85) {
                this.stopScrapingProgressAnimation();
            }
        }, 100);
    }
    
    stopScrapingProgressAnimation() {
        if (this.scrapingProgressAnimation) {
            clearInterval(this.scrapingProgressAnimation);
            this.scrapingProgressAnimation = null;
        }
        
        const progressBar = document.getElementById('scraping-progress');
        if (progressBar) {
            progressBar.classList.remove('progress-bar-animated');
        }
    }
    
    handleScrapingStarted(data) {
        const { job_id, config } = data;
        console.log(`🚀 Парсинг запущен: ${config} (${job_id})`);
        
        // Добавляем новую задачу в список если он есть
        this.addScrapingJob({
            id: job_id,
            config: config,
            status: 'выполняется',
            created_at: new Date().toISOString()
        });
        
        // Создаем уникальный ключ для предотвращения дублирования
        const notificationKey = `scraping_started:${job_id}`;
        
        // Проверяем не показывается ли уже уведомление для этой задачи
        if (window.activeNotifications && window.activeNotifications.has(notificationKey)) {
            console.log('Дублирующее уведомление о запуске парсинга заблокировано:', config);
            return;
        }
        
        this.showNotification('success', {
            title: 'Парсинг запущен',
            message: `Задача ${config} успешно запущена`
        });
        
        // Добавляем в реестр активных уведомлений
        if (window.activeNotifications) {
            window.activeNotifications.add(notificationKey);
            // Удаляем через 10 секунд
            setTimeout(() => {
                window.activeNotifications.delete(notificationKey);
            }, 10000);
        }
    }
    
    handleScrapingCompleted(data) {
        const { job_id, config, stats } = data;
        console.log(`✅ Парсинг завершен: ${config} (${job_id})`);
        
        // Обновляем статус задачи
        this.updateScrapingJobStatus(job_id, 'завершено');
        
        // Создаем уникальный ключ для предотвращения дублирования
        const notificationKey = `scraping_completed:${job_id}`;
        
        // Проверяем не показывается ли уже уведомление для этой задачи
        if (window.activeNotifications && window.activeNotifications.has(notificationKey)) {
            console.log('Дублирующее уведомление о завершении парсинга заблокировано:', config);
            return;
        }
        
        this.showNotification('success', {
            title: 'Парсинг завершен',
            message: `Задача ${config} завершена успешно. Обработано: ${stats?.scraped_items || 0} объявлений`
        });
        
        // Добавляем в реестр активных уведомлений
        if (window.activeNotifications) {
            window.activeNotifications.add(notificationKey);
            // Удаляем через 10 секунд
            setTimeout(() => {
                window.activeNotifications.delete(notificationKey);
            }, 10000);
        }
    }
    
    handleScrapingError(data) {
        const { job_id, config, error } = data;
        console.log(`❌ Ошибка парсинга: ${config} (${job_id}) - ${error}`);
        
        // Обновляем статус задачи
        this.updateScrapingJobStatus(job_id, 'ошибка');
        
        // Создаем уникальный ключ для предотвращения дублирования
        const notificationKey = `scraping_error:${job_id}`;
        
        // Проверяем не показывается ли уже уведомление для этой задачи
        if (window.activeNotifications && window.activeNotifications.has(notificationKey)) {
            console.log('Дублирующее уведомление об ошибке парсинга заблокировано:', config);
            return;
        }
        
        this.showNotification('error', {
            title: 'Ошибка парсинга',
            message: `Задача ${config} завершена с ошибкой: ${error}`
        });
        
        // Добавляем в реестр активных уведомлений
        if (window.activeNotifications) {
            window.activeNotifications.add(notificationKey);
            // Удаляем через 10 секунд
            setTimeout(() => {
                window.activeNotifications.delete(notificationKey);
            }, 10000);
        }
    }
    
    updateDuplicateProgress(data) {
        const { progress, total, processed, active } = data;
        const container = document.getElementById('duplicate-progress-container');
        const progressBar = document.getElementById('duplicate-progress');
        const progressText = document.getElementById('duplicate-progress-text');
        
        if (container && progressBar && progressText) {
            if (active > 0) {
                // Показываем контейнер прогресса
                container.style.display = 'block';
                
                // Запускаем анимацию прогресса
                this.startDuplicateProgressAnimation(progressBar, progressText);
                
                // Обновляем текст
                progressText.textContent = `Обработка дубликатов: ${processed}/${total} обработано, ${active} активно`;
            } else {
                // Скрываем контейнер прогресса
                container.style.display = 'none';
                this.stopDuplicateProgressAnimation();
            }
        }
    }
    
    startDuplicateProgressAnimation(progressBar, progressText) {
        if (!progressBar) return;
        
        // Очищаем предыдущую анимацию
        this.stopDuplicateProgressAnimation();
        
        // Устанавливаем начальное состояние
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', '0');
        progressBar.classList.add('progress-bar-animated');
        
        const duration = 25000; // 25 секунд для обработки дубликатов
        const startTime = Date.now();
        
        // Сохраняем ID анимации
        this.duplicateProgressAnimation = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min((elapsed / duration) * 100, 80); // Максимум 80% для имитации
            
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', Math.round(progress));
            
            // Останавливаем анимацию если достигли максимума
            if (progress >= 80) {
                this.stopDuplicateProgressAnimation();
            }
        }, 100);
    }
    
    stopDuplicateProgressAnimation() {
        if (this.duplicateProgressAnimation) {
            clearInterval(this.duplicateProgressAnimation);
            this.duplicateProgressAnimation = null;
        }
        
        const progressBar = document.getElementById('duplicate-progress');
        if (progressBar) {
            progressBar.classList.remove('progress-bar-animated');
        }
    }
    
    handleDuplicateCompleted(data) {
        console.log('✅ Обработка дубликатов завершена:', data);
        
        this.showNotification('success', {
            title: 'Обработка завершена',
            message: 'Обработка дубликатов завершена успешно'
        });
    }
    
    updateSystemStatus(data) {
        const { status, connections } = data;
        
        const indicator = document.getElementById('status-indicator');
        const text = document.getElementById('status-text');
        
        if (indicator && text) {
            if (status === 'healthy') {
                indicator.className = 'bi bi-circle-fill text-success';
                text.textContent = 'Система работает';
                indicator.title = `Система работает нормально. WebSocket соединений: ${connections || 0}`;
            } else {
                indicator.className = 'bi bi-circle-fill text-danger';
                text.textContent = 'Ошибка системы';
                indicator.title = data.error || 'Ошибка системы';
            }
        }
    }
    
    handleNewAd(data) {
        const { ad_id, title, source } = data;
        console.log(`🏠 Новое объявление: ${title} (${source})`);
        
        // Обновляем счетчики
        this.updateStatCard('total-ads', 
            parseInt(document.getElementById('total-ads')?.textContent || '0') + 1
        );
    }
    
    handleDuplicateDetected(data) {
        const { ad_id, unique_ad_id, similarity } = data;
        console.log(`🔍 Дубликат обнаружен: ${ad_id} -> ${unique_ad_id} (${similarity.toFixed(2)})`);
        
        // Обновляем счетчики
        this.updateStatCard('duplicates', 
            parseInt(document.getElementById('duplicates')?.textContent || '0') + 1
        );
    }
    
    handleRealtorDetected(data) {
        const { phone, ads_count } = data;
        console.log(`👤 Риэлтор обнаружен: ${phone} (${ads_count} объявлений)`);
        
        // Обновляем счетчики
        this.updateStatCard('realtor-ads', 
            parseInt(document.getElementById('realtor-ads')?.textContent || '0') + ads_count
        );
    }
    
    showNotification(type, data) {
        const { title, message } = data;
        const fullMessage = title ? `${title}: ${message}` : message;
        
        // Проверяем, не является ли это уведомлением о завершении обработки дубликатов
        // и не находимся ли мы на странице, где это уведомление не нужно
        if (fullMessage.includes('Обработка дубликатов') || fullMessage.includes('Обработка завершена')) {
            const currentPath = window.location.pathname;
            // Показываем уведомления о дубликатах только на страницах дашборда и автоматизации
            if (!['/dashboard', '/automation', '/'].includes(currentPath)) {
                console.log('Уведомление о дубликатах скрыто на странице:', currentPath);
                return;
            }
        }
        
        // Дебаунсинг для предотвращения спама уведомлений
        const debounceKey = `${type}:${fullMessage}`;
        if (this.notificationDebounce && this.notificationDebounce[debounceKey]) {
            console.log('Уведомление заблокировано дебаунсингом:', fullMessage);
            return;
        }
        
        // Устанавливаем дебаунсинг на 3 секунды
        if (!this.notificationDebounce) {
            this.notificationDebounce = {};
        }
        this.notificationDebounce[debounceKey] = true;
        setTimeout(() => {
            delete this.notificationDebounce[debounceKey];
        }, 3000);
        
        // Используем существующую функцию показа уведомлений
        if (window.showNotification) {
            window.showNotification(type, fullMessage);
        } else {
            // Fallback уведомление с защитой от дублирования
            window.activeNotifications = window.activeNotifications || new Set();
            
            // Создаем уникальный ключ для сообщения
            const notificationKey = `${type}:${fullMessage}`;
            
            // Проверяем не показывается ли уже такое же уведомление
            if (window.activeNotifications.has(notificationKey)) {
                console.log('Дублирующее уведомление заблокировано (websocket.js):', fullMessage);
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
                    ${fullMessage}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', alertHtml);
            
            // Обработчик для удаления из реестра при закрытии
            const notificationElement = document.getElementById(notificationId);
            if (notificationElement) {
                const closeButton = notificationElement.querySelector('.btn-close');
                if (closeButton) {
                    closeButton.addEventListener('click', () => {
                        window.activeNotifications.delete(notificationKey);
                    });
                }
            }
            
            // Автоматически убираем уведомление через 5 секунд
            setTimeout(() => {
                const notification = document.getElementById(notificationId);
                if (notification) {
                    // Удаляем из реестра
                    window.activeNotifications.delete(notificationKey);
                    
                    notification.style.transform = 'translateX(100%)';
                    notification.style.opacity = '0';
                    setTimeout(() => {
                        notification.remove();
                    }, 300);
                }
            }, 5000);
        }
    }
    
    // Вспомогательные методы для обновления UI
    
    addScrapingJob(job) {
        const container = document.getElementById('scraping-jobs-container');
        if (container && window.createJobElement) {
            const jobElement = window.createJobElement(job);
            container.insertBefore(jobElement, container.firstChild);
        }
    }
    
    updateScrapingJobStatus(jobId, status) {
        const jobElement = document.querySelector(`[data-job-id="${jobId}"]`);
        if (jobElement) {
            const statusBadge = jobElement.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.textContent = status;
                statusBadge.className = `badge ${this.getStatusClass(status)} status-badge`;
            }
        }
    }
    
    getStatusClass(status) {
        const statusMap = {
            'ожидание': 'bg-secondary',
            'выполняется': 'bg-warning',
            'завершено': 'bg-success',
            'ошибка': 'bg-danger',
            'остановлено': 'bg-info'
        };
        return statusMap[status] || 'bg-secondary';
    }
    
    updateScrapingStatus() {
        // Обновляем общий статус парсинга если есть такая функция
        if (window.updateScrapingStatus) {
            window.updateScrapingStatus();
        }
    }
    
    updateScrapingSources(data) {
        // Обновляем источники парсинга
        if (window.automationManager) {
            window.automationManager.updateScrapingSources(data.jobs || [], data.sources || []);
        }
    }
}

// Функция для управления индикатором real-time соединения
function setRealtimeIndicator(connected) {
    const indicator = document.getElementById('realtime-indicator');
    if (indicator) {
        if (connected) {
            indicator.classList.remove('disconnected');
            indicator.classList.add('connected');
            indicator.title = 'WebSocket соединение активно';
        } else {
            indicator.classList.remove('connected');
            indicator.classList.add('disconnected');
            indicator.title = 'Нет WebSocket соединения';
        }
    }
} 