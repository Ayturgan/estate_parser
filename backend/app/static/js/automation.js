class AutomationManager {
    constructor() {
        console.log('🔧 Создание AutomationManager...');
        this.currentStatus = null;
        this.refreshInterval = null;
        
        this.init();
        console.log('✅ AutomationManager инициализирован');
    }
    
    init() {
        console.log('🔧 Инициализация AutomationManager...');
        this.bindEvents();
        this.startAutoRefresh();
        this.loadStatus();
        this.loadScrapingSources();
        this.setupWebSocketHandlers();
        console.log('✅ Инициализация AutomationManager завершена');
    }
    
    bindEvents() {
        // Кнопки управления пайплайна
        document.getElementById('start-btn').addEventListener('click', () => this.startPipeline());
        document.getElementById('stop-btn').addEventListener('click', () => this.stopPipeline());
        document.getElementById('refresh-btn').addEventListener('click', () => this.loadStatus());
        
        // Кнопки управления источниками убраны - только мониторинг
    }
    
    async startPipeline() {
        try {
            const response = await fetch('/api/automation/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('🚀 Пайплайн запущен!', 'success');
                this.loadStatus();
            } else {
                this.showNotification(result.message, 'warning');
            }
        } catch (error) {
            this.showNotification('❌ Ошибка запуска пайплайна', 'error');
            console.error('Error starting pipeline:', error);
        }
    }
    
    async stopPipeline() {
        try {
            const response = await fetch('/api/automation/stop', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            if (response.ok) {
                this.showNotification('🛑 Пайплайн остановлен', 'info');
                this.loadStatus();
            }
        } catch (error) {
            this.showNotification('❌ Ошибка остановки пайплайна', 'error');
            console.error('Error stopping pipeline:', error);
        }
    }
    
    async loadStatus() {
        try {
            const response = await fetch('/api/automation/status');
            const status = await response.json();
            
            this.currentStatus = status;
            this.updateUI(status);
        } catch (error) {
            console.error('Error loading status:', error);
            this.showNotification('❌ Ошибка загрузки статуса', 'error');
        }
    }
    
    updateUI(status) {
        try {
            // Проверяем что status не undefined
            if (!status) {
                console.warn('❌ Получен undefined status в updateUI');
                return;
            }
            
            // Проверяем изменение статуса для уведомлений
            if (this.currentStatus && this.currentStatus.pipeline_status !== status.pipeline_status) {
                if (this.currentStatus.pipeline_status === 'running' && status.pipeline_status === 'completed') {
                    this.showNotification('✅ Пайплайн завершен успешно!', 'success');
                } else if (this.currentStatus.pipeline_status === 'running' && status.pipeline_status === 'error') {
                    this.showNotification('❌ Пайплайн завершен с ошибками', 'error');
                }
            }
            
            // Обновляем статус пайплайна
            const statusElement = document.getElementById('pipeline-status');
            if (statusElement) {
                const statusInfo = this.getStatusInfo(status.pipeline_status);
                statusElement.innerHTML = `<i class="bi ${statusInfo.icon}"></i> ${statusInfo.text}`;
                statusElement.className = `badge ${statusInfo.class} ${statusInfo.animation}`;
            }
            
            // Обновляем кнопки управления
            this.updateControlButtons(status.pipeline_status);
            
            // Обновляем конфигурацию системы
            this.updateConfigInfo(status);
            
            // Обновляем временную информацию
            this.updateTimeInfo(status);
            
            // Обновляем текущий этап
            this.updateCurrentStage(status);
            
            // Обновляем статистику пайплайна
            this.updatePipelineStats(status);
            
            // Детали этапов теперь отображаются в разделе "Статус пайплайна"
        } catch (error) {
            console.error('❌ Ошибка обновления UI:', error);
        }
    }
    
    getStatusInfo(status) {
        // Проверяем что status не undefined или null
        if (!status) {
            return { text: 'Неизвестно', class: 'bg-secondary', icon: 'bi-question-circle-fill', animation: '' };
        }
        
        const statusMap = {
            'idle': { 
                text: 'Готов', 
                class: 'bg-success', 
                icon: 'bi-circle-fill',
                animation: ''
            },
            'running': { 
                text: 'Выполняется', 
                class: 'bg-warning', 
                icon: 'bi-arrow-clockwise',
                animation: 'pulse'
            },
            'completed': { 
                text: 'Завершен', 
                class: 'bg-info', 
                icon: 'bi-check-circle-fill',
                animation: ''
            },
            'error': { 
                text: 'Ошибка', 
                class: 'bg-danger', 
                icon: 'bi-exclamation-triangle-fill',
                animation: ''
            },
            // Статус "paused" удален
        };
        return statusMap[status] || { text: status.toString().toUpperCase(), class: 'bg-secondary', icon: 'bi-question-circle-fill', animation: '' };
    }
    
    updateControlButtons(status) {
        try {
            const startBtn = document.getElementById('start-btn');
            const stopBtn = document.getElementById('stop-btn');
            
            if (startBtn && stopBtn) {
                if (status === 'running') {
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                } else {
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                }
            }
        } catch (error) {
            console.error('❌ Ошибка обновления кнопок управления:', error);
        }
    }
    
    updateConfigInfo(status) {
        try {
            // Проверяем что status не undefined
            if (!status) {
                console.warn('❌ Получен undefined status в updateConfigInfo');
                return;
            }
            
            // Обновляем информацию о конфигурации (только для чтения)
            const autoModeElement = document.getElementById('config-auto-mode');
            const intervalElement = document.getElementById('config-interval');
            const sourcesElement = document.getElementById('config-sources');
            const stagesElement = document.getElementById('config-stages');
            
            if (autoModeElement) {
                autoModeElement.className = status.is_auto_mode ? 'badge bg-success' : 'badge bg-danger';
                autoModeElement.innerHTML = status.is_auto_mode ? '<i class="bi bi-check-circle"></i> Включен' : '<i class="bi bi-x-circle"></i> Отключен';
            }
            
            if (intervalElement) {
                intervalElement.className = 'badge bg-primary';
                // Отображаем минуты если интервал меньше часа, иначе часы
                if (status.interval_minutes && status.interval_minutes < 60) {
                    intervalElement.innerHTML = `<i class="bi bi-clock"></i> ${status.interval_minutes} мин.`;
                } else {
                    intervalElement.innerHTML = `<i class="bi bi-clock"></i> ${status.interval_hours} час.`;
                }
            }
            
            if (sourcesElement) {
                sourcesElement.className = 'badge bg-info';
                const sourcesText = status.scraping_sources ? status.scraping_sources.join(', ') : 'Не настроен';
                sourcesElement.innerHTML = `<i class="bi bi-list"></i> ${sourcesText}`;
            }
            
            if (stagesElement && status.enabled_stages) {
                stagesElement.innerHTML = '';
                const stageNames = {
                    'scraping': 'Парсинг',
                    'photo_processing': 'Фото',
                    'duplicate_processing': 'Дубликаты',
                    'realtor_detection': 'Риэлторы',
                    'elasticsearch_reindex': 'Поиск'
                };
                
                Object.entries(status.enabled_stages).forEach(([stageKey, enabled]) => {
                    const stageBadge = document.createElement('span');
                    stageBadge.className = `badge ${enabled ? 'bg-success' : 'bg-secondary'} me-1`;
                    stageBadge.innerHTML = `
                        <i class="bi ${enabled ? 'bi-check-circle' : 'bi-x-circle'}"></i>
                        ${stageNames[stageKey] || stageKey}
                    `;
                    stagesElement.appendChild(stageBadge);
                });
            }
        } catch (error) {
            console.error('❌ Ошибка обновления конфигурации:', error);
        }
    }
    
    updateTimeInfo(status) {
        try {
            // Проверяем что status не undefined
            if (!status) {
                console.warn('❌ Получен undefined status в updateTimeInfo');
                return;
            }
            
            // Обновляем информацию о времени
            const lastRunStartElement = document.getElementById('last-run-start');
            const lastRunEndElement = document.getElementById('last-run-end');
            const nextRunElement = document.getElementById('next-run');
            
            if (lastRunStartElement) {
                if (status.last_run_start) {
                    lastRunStartElement.textContent = this.formatDateTime(status.last_run_start);
                    lastRunStartElement.className = 'text-success';
                } else {
                    lastRunStartElement.textContent = '—';
                    lastRunStartElement.className = 'text-muted';
                }
            }
            
            if (lastRunEndElement) {
                if (status.last_run_end) {
                    lastRunEndElement.textContent = this.formatDateTime(status.last_run_end);
                    lastRunEndElement.className = 'text-info';
                } else {
                    lastRunEndElement.textContent = '—';
                    lastRunEndElement.className = 'text-muted';
                }
            }
            
            if (nextRunElement) {
                if (status.next_run_scheduled && status.is_auto_mode) {
                    nextRunElement.textContent = this.formatDateTime(status.next_run_scheduled);
                    nextRunElement.className = 'text-primary';
                } else {
                    nextRunElement.textContent = '—';
                    nextRunElement.className = 'text-muted';
                }
            }
        } catch (error) {
            console.error('❌ Ошибка обновления временной информации:', error);
        }
    }
    
    updateCurrentStage(status) {
        try {
            const currentStageElement = document.getElementById('current-stage');
            const currentStageNameElement = document.getElementById('current-stage-name');
            const currentProgressElement = document.getElementById('current-progress');
            const currentStageDetailsElement = document.getElementById('current-stage-details');
            
            if (!currentStageElement || !currentStageNameElement) return;
            
            if (status.current_stage && status.pipeline_status === 'running') {
                const stageNames = {
                    'scraping': 'Парсинг сайтов',
                    'photo_processing': 'Обработка фотографий',
                    'duplicate_processing': 'Обработка дубликатов',
                    'realtor_detection': 'Определение риэлторов',
                    'elasticsearch_reindex': 'Переиндексация поиска'
                };
                
                const stageName = stageNames[status.current_stage] || status.current_stage;
                currentStageNameElement.textContent = stageName;
                
                // Показываем блок текущего этапа
                currentStageElement.style.display = 'block';
                
                // Убираем прогресс-бар, оставляем только текст
                if (currentProgressElement) {
                    currentProgressElement.parentElement.style.display = 'none';
                }
                
                // Добавляем детали этапа
                if (currentStageDetailsElement) {
                    const stageDetails = status.stage_details?.[status.current_stage];
                    if (stageDetails) {
                        let detailsText = '';
                        if (stageDetails.status === 'running') {
                            detailsText = 'Выполняется...';
                        } else if (stageDetails.status === 'completed') {
                            detailsText = 'Завершен';
                        } else if (stageDetails.status === 'error') {
                            detailsText = `Ошибка: ${stageDetails.error || 'Неизвестная ошибка'}`;
                        }
                        currentStageDetailsElement.textContent = detailsText;
                    }
                }
            } else {
                // Скрываем блок текущего этапа
                currentStageElement.style.display = 'none';
            }
        } catch (error) {
            console.error('❌ Ошибка обновления текущего этапа:', error);
        }
    }
    
    updatePipelineStats(status) {
        try {
            // Убираем обновление статистики новых объявлений
            // Блок статистики удален из шаблона
        } catch (error) {
            console.error('❌ Ошибка обновления статистики пайплайна:', error);
        }
    }
    
    updateSimpleStats(status) {
        try {
            // Убираем обновление статистики новых объявлений
            // Блок статистики удален из шаблона
        } catch (error) {
            console.error('❌ Ошибка обновления простой статистики:', error);
        }
    }
    
    getProgressText(stageKey, stageInfo) {
        switch (stageKey) {
            case 'scraping':
                return `Обработано: ${stageInfo.processed || 0} объявлений`;
            case 'photo_processing':
                return `Обработано: ${stageInfo.processed || 0} фото`;
            case 'duplicate_processing':
                return `Найдено: ${stageInfo.duplicates || 0} дубликатов`;
            case 'realtor_detection':
                return `Обнаружено: ${stageInfo.realtors || 0} риэлторов`;
            case 'elasticsearch_reindex':
                return `Индексировано: ${stageInfo.indexed || 0} документов`;
            default:
                return `Прогресс: ${stageInfo.progress || 0}%`;
        }
    }
    
    formatDateTime(dateString) {
        if (!dateString) return 'Не указано';
            const date = new Date(dateString);
        return date.toLocaleString('ru-RU');
    }
    
    showNotification(message, type = 'info') {
        // Используем глобальную функцию уведомлений
        if (window.showNotification) {
            window.showNotification(type, message);
        } else {
            // Fallback уведомление с защитой от дублирования
            window.activeNotifications = window.activeNotifications || new Set();
            
            // Создаем уникальный ключ для сообщения
            const notificationKey = `${type}:${message}`;
            
            // Проверяем не показывается ли уже такое же уведомление
            if (window.activeNotifications.has(notificationKey)) {
                console.log('Дублирующее уведомление заблокировано (automation.js):', message);
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
    
    async loadScrapingSources() {
        try {
            const response = await fetch('/api/scraping/sources');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.updateScrapingSources(data.jobs || [], data.sources || []);
        } catch (error) {
            console.error('❌ Ошибка загрузки источников парсинга:', error);
            // Показываем ошибку пользователю
            const container = document.getElementById('scraping-sources');
            if (container) {
                container.innerHTML = `
                    <div class="col-12 text-center">
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle"></i>
                            Ошибка загрузки источников парсинга: ${error.message}
                        </div>
                    </div>
                `;
            }
        }
    }
    
    updateScrapingSources(jobs, sources) {
        try {
            const container = document.getElementById('scraping-sources');
            if (!container) {
                console.error('❌ Элемент scraping-sources не найден');
                return;
            }
            
            container.innerHTML = '';
            
            if (!sources || sources.length === 0) {
                container.innerHTML = `
                    <div class="col-12 text-center">
                        <div class="alert alert-warning">
                            <i class="bi bi-exclamation-triangle"></i>
                            Нет настроенных источников парсинга
                        </div>
                    </div>
                `;
                return;
            }
            
            sources.forEach(source => {
                // Находим последнюю задачу для этого источника
                const sourceJobs = jobs.filter(j => j.config === source);
                let latestJob = null;
                
                if (sourceJobs.length > 0) {
                    // Сортируем по времени создания и берем последнюю
                    sourceJobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                    latestJob = sourceJobs[0];
                }
                
                const sourceCard = this.createSourceCard(source, latestJob);
                container.appendChild(sourceCard);
            });
        } catch (error) {
            console.error('❌ Ошибка обновления источников парсинга:', error);
        }
    }
    
    createSourceCard(source, job) {
        try {
            const card = document.createElement('div');
            card.className = 'col-md-6 col-lg-4 mb-3';
                
            let status = 'idle';
            let statusClass = 'bg-secondary';
            let statusIcon = 'bi-circle-fill';
            let statusText = 'Не запущен';
            let animation = '';
                
            if (job) {
                status = job.status;
                switch (job.status) {
                    case 'выполняется':
                        statusClass = 'bg-warning';
                        statusIcon = 'bi-arrow-clockwise';
                        statusText = 'Выполняется';
                        animation = 'pulse';
                        break;
                    case 'завершено':
                        statusClass = 'bg-success';
                        statusIcon = 'bi-check-circle-fill';
                        statusText = 'Завершен';
                        break;
                    case 'ошибка':
                        statusClass = 'bg-danger';
                        statusIcon = 'bi-exclamation-triangle-fill';
                        statusText = 'Ошибка';
                        break;
                    case 'остановлено':
                        statusClass = 'bg-info';
                        statusIcon = 'bi-stop-circle-fill';
                        statusText = 'Остановлен';
                        break;
                    case 'pending':
                        statusClass = 'bg-primary';
                        statusIcon = 'bi-hourglass-split';
                        statusText = 'Ожидает';
                        break;
                    default:
                        statusClass = 'bg-secondary';
                        statusIcon = 'bi-question-circle-fill';
                        statusText = job.status || 'Неизвестно';
                }
            }
            
            card.innerHTML = `
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h6 class="card-title mb-0">${source}</h6>
                            <span class="badge ${statusClass} ${animation}">
                                <i class="bi ${statusIcon}"></i> ${statusText}
                            </span>
                        </div>
                        
                        ${job ? `
                            <small class="text-muted">
                                Создан: ${this.formatDateTime(job.created_at)}<br>
                                ${job.started_at ? `Запущен: ${this.formatDateTime(job.started_at)}<br>` : ''}
                                ${job.finished_at ? `Завершен: ${this.formatDateTime(job.finished_at)}` : ''}
                            </small>
                        ` : '<small class="text-muted">Нет активных задач</small>'}
                    </div>
                    
                    <div class="card-footer bg-transparent">
                        <div class="btn-group btn-group-sm w-100">
                            ${!job || job.status !== 'выполняется' ? 
                                `<button class="btn btn-outline-primary" onclick="automationManager.startSource('${source}')">
                                    <i class="bi bi-play"></i> Запустить
                                </button>` : ''
                            }
                            
                            ${job && job.status === 'выполняется' ? 
                                `<button class="btn btn-outline-danger" onclick="automationManager.stopSource('${source}', '${job.id}')">
                                    <i class="bi bi-stop"></i> Остановить
                                </button>` : ''
                            }
                            
                            <button class="btn btn-outline-secondary" onclick="automationManager.showSourceLogs('${source}')">
                                <i class="bi bi-file-text"></i> Логи
                            </button>
                        </div>
                    </div>
                </div>
            `;
                
            return card;
        } catch (error) {
            console.error('❌ Ошибка создания карточки источника:', error);
            // Возвращаем простую карточку с ошибкой
            const errorCard = document.createElement('div');
            errorCard.className = 'col-md-6 col-lg-4 mb-3';
            errorCard.innerHTML = `
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle"></i>
                            Ошибка отображения ${source}
                        </div>
                    </div>
                </div>
            `;
            return errorCard;
        }
    }
    
    async startSource(source) {
        try {
            const response = await fetch(`/api/scraping/start/${source}`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                console.log(`🚀 Парсинг ${source} запущен через API`);
                setTimeout(() => this.loadScrapingSources(), 1000);
            } else {
                this.showNotification(result.detail || 'Ошибка запуска', 'error');
            }
        } catch (error) {
            this.showNotification('❌ Ошибка запуска парсинга', 'error');
            console.error('Error starting source:', error);
        }
    }
    
    async stopSource(source, jobId) {
        try {
            const response = await fetch(`/api/scraping/stop/${jobId}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showNotification(`🛑 Парсинг ${source} остановлен`, 'info');
                setTimeout(() => this.loadScrapingSources(), 1000);
            } else {
                this.showNotification('❌ Ошибка остановки парсинга', 'error');
            }
        } catch (error) {
            this.showNotification('❌ Ошибка остановки парсинга', 'error');
            console.error('Error stopping source:', error);
        }
    }
    
    async startAllSources() {
        try {
            const response = await fetch('/api/scraping/start-all', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('🚀 Все источники запущены!', 'success');
                setTimeout(() => this.loadScrapingSources(), 1000);
            } else {
                this.showNotification(result.message || 'Ошибка запуска', 'error');
            }
        } catch (error) {
            this.showNotification('❌ Ошибка запуска всех источников', 'error');
            console.error('Error starting all sources:', error);
        }
    }
    
    async stopAllSources() {
        try {
            const response = await fetch('/api/scraping/stop-all', {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showNotification('🛑 Все источники остановлены', 'info');
                setTimeout(() => this.loadScrapingSources(), 1000);
            } else {
                this.showNotification('❌ Ошибка остановки всех источников', 'error');
            }
        } catch (error) {
            this.showNotification('❌ Ошибка остановки всех источников', 'error');
            console.error('Error stopping all sources:', error);
            }
    }
    
    async showSourceLogs(source) {
        try {
            // Сначала получаем список задач, чтобы найти job_id для источника
            const jobsResponse = await fetch('/api/scraping/jobs');
            const jobsData = await jobsResponse.json();
            
            // Ищем самую свежую задачу для данного источника
            const sourceJobs = jobsData.filter(j => j.config === source);
            const job = sourceJobs.sort((a, b) => {
                // Сортируем по времени создания (самая свежая первая)
                const dateA = new Date(a.created_at || 0);
                const dateB = new Date(b.created_at || 0);
                return dateB - dateA;
            })[0];
            
            if (!job) {
                this.showNotification('❌ Нет задач для данного источника', 'error');
                return;
            }
            
            console.log(`📋 Показываем логи для ${source} (job_id: ${job.id}, статус: ${job.status})`);
            
            const response = await fetch(`/api/scraping/log/${job.id}`);
            const logs = await response.json();
            
            const modal = new bootstrap.Modal(document.getElementById('logsModal'));
            const modalBody = document.getElementById('logsModalBody');
            
            // Добавляем заголовок с информацией о задаче
            modalBody.innerHTML = `
                <div class="log-header mb-3">
                    <h6>Логи парсинга: ${source}</h6>
                    <small class="text-muted">
                        ID: ${job.id} | Статус: ${job.status} | 
                        Создано: ${this.formatDateTime(job.created_at)}
                    </small>
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
                        <span class="log-message">${message}</span>
                    </div>`;
                } else {
                    return `<div class="log-entry">
                        <span class="log-message">${logLine}</span>
                    </div>`;
                }
            }).join('');
            
            modal.show();
        } catch (error) {
            this.showNotification('❌ Ошибка загрузки логов', 'error');
            console.error('Error loading logs:', error);
        }
    }
    
    destroy() {
        // Очищаем все анимации при уничтожении
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // Отписываемся от WebSocket событий
        if (window.realtimeClient) {
            window.realtimeClient.off('automation_status_update', this.handleStatusUpdate);
            window.realtimeClient.off('automation_completed', this.handleCompleted);
            window.realtimeClient.off('automation_error', this.handleError);
            window.realtimeClient.off('scraping_sources_update', this.handleScrapingSourcesUpdate);
        }
    }

    startAutoRefresh() {
        // Обновляем статус каждые 2 секунды для получения актуальных данных
        this.refreshInterval = setInterval(() => {
            this.loadStatus();
            this.loadScrapingSources();
        }, 2000);
    }

    setupWebSocketHandlers() {
        // Добавляем обработчики WebSocket событий для реального времени
        // Небольшая задержка, чтобы дождаться создания WebSocket клиента
        setTimeout(() => {
            if (window.realtimeClient) {
            window.realtimeClient.on('automation_status', (data) => {
                this.currentStatus = data;
                this.updateUI(data);
            });

                window.realtimeClient.on('automation_completed', (data) => {
                    this.showNotification('✅ Пайплайн завершен успешно!', 'success');
                    this.loadStatus();
                });

                window.realtimeClient.on('automation_error', (data) => {
                    this.showNotification('❌ Пайплайн завершен с ошибками', 'error');
                    this.loadStatus();
                });

            window.realtimeClient.on('automation_progress', (data) => {
                if (data.status) {
                    this.currentStatus = data.status;
                    this.updateUI(data.status);
                }
            });

            window.realtimeClient.on('scraping_started', (data) => {
                    // Убираем дублирующее уведомление - websocket.js уже покажет его
                    console.log('🚀 Парсинг запущен (WebSocket event)');
                this.loadScrapingSources();
            });

            window.realtimeClient.on('scraping_completed', (data) => {
                    // Убираем дублирующее уведомление - websocket.js уже покажет его
                    console.log('✅ Парсинг завершен (WebSocket event)');
                this.loadScrapingSources();
            });

            window.realtimeClient.on('scraping_sources_update', (data) => {
                this.loadScrapingSources();
            });
            } else {
                console.warn('⚠️ WebSocket client не найден, используем только polling');
            }
        }, 100);
    }
}

// Инициализация при загрузке страницы
let automationManager = null;

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('automation-page')) {
        automationManager = new AutomationManager();
        window.automationManager = automationManager;
    }
});