class AutomationManager {
    constructor() {
        this.refreshInterval = null;
        this.logsInterval = null;
        this.currentStatus = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.startAutoRefresh();
        this.loadStatus();
        this.loadScrapingSources();
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
    
    // Функция pausePipeline удалена
    
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
        const statusInfo = this.getStatusInfo(status.pipeline_status);
        statusElement.innerHTML = `<i class="bi ${statusInfo.icon}"></i> ${statusInfo.text}`;
        statusElement.className = `badge ${statusInfo.class} ${statusInfo.animation}`;
        
        // Обновляем кнопки управления
        this.updateControlButtons(status.pipeline_status);
        
        // Обновляем конфигурацию системы
        this.updateConfigInfo(status);
        
        // Обновляем временную информацию
        this.updateTimeInfo(status);
        
        // Обновляем текущий этап
        this.updateCurrentStage(status);
        
        // Детали этапов теперь отображаются в разделе "Статус пайплайна"
    }
    
    getStatusInfo(status) {
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
        return statusMap[status] || { text: status.toUpperCase(), class: 'bg-secondary', icon: 'bi-question-circle-fill', animation: '' };
    }
    
    updateControlButtons(status) {
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (status === 'running') {
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }
    
    updateConfigInfo(status) {
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
        
        if (stagesElement) {
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
    }
    
    updateTimeInfo(status) {
        const lastRunStart = document.getElementById('last-run-start');
        const lastRunEnd = document.getElementById('last-run-end');
        const nextRun = document.getElementById('next-run');
        
        if (lastRunStart) {
            lastRunStart.textContent = status.last_run_start 
                ? this.formatDateTime(status.last_run_start) 
                : '—';
        }
        
        if (lastRunEnd) {
            lastRunEnd.textContent = status.last_run_end 
                ? this.formatDateTime(status.last_run_end) 
                : '—';
        }
        
        if (nextRun) {
            nextRun.textContent = status.next_run_scheduled 
                ? this.formatDateTime(status.next_run_scheduled) 
                : '—';
        }
    }
    
    updateCurrentStage(status) {
        const currentStageDiv = document.getElementById('current-stage');
        const currentStageName = document.getElementById('current-stage-name');
        const currentProgress = document.getElementById('current-progress');
        const currentStageDetails = document.getElementById('current-stage-details');
        
        if (status.pipeline_status === 'running' && status.current_stage) {
            currentStageDiv.style.display = 'block';
            
            const stageNames = {
                'scraping': 'Парсинг сайтов',
                'photo_processing': 'Обработка фотографий',
                'duplicate_processing': 'Обработка дубликатов',
                'realtor_detection': 'Определение риэлторов',
                'elasticsearch_reindex': 'Переиндексация поиска'
            };
            
            currentStageName.textContent = stageNames[status.current_stage] || status.current_stage;
            
            // Получаем детали текущего этапа
            const stageInfo = status.stage_details && status.stage_details[status.current_stage];
            if (stageInfo) {
                // Рассчитываем прогресс для текущего этапа
                let progressPercent = 0;
                const stageKey = status.current_stage;
                
                // Проверяем статус этапа
                if (stageInfo.status === 'completed') {
                    progressPercent = 100; // Завершенный этап = 100%
                } else if (stageInfo.status === 'running') {
                    // Для выполняющихся этапов пытаемся рассчитать точный прогресс
                    if (stageKey === 'scraping') {
                        const progress = stageInfo.progress || {};
                        const total = progress.total || 0;
                        const completed = progress.sources_completed || 0;
                        progressPercent = total > 0 ? Math.round((completed / total) * 100) : 10;
                    } else if (stageKey === 'photo_processing') {
                        const progress = stageInfo.progress || {};
                        const total = progress.total || 0;
                        const processed = progress.processed || 0;
                        progressPercent = total > 0 ? Math.round((processed / total) * 100) : 10;
                    } else if (stageKey === 'duplicate_processing') {
                        const progress = stageInfo.progress || {};
                        const processed = progress.processed || 0;
                        const remaining = progress.remaining || 0;
                        const total = processed + remaining;
                        progressPercent = total > 0 ? Math.round((processed / total) * 100) : 10;
                    } else if (stageKey === 'realtor_detection') {
                        const progress = stageInfo.progress || {};
                        const processed = progress.processed || 0;
                        const total = progress.total || 0;
                        progressPercent = total > 0 ? Math.round((processed / total) * 100) : 10;
                    } else if (stageKey === 'elasticsearch_reindex') {
                        const progress = stageInfo.progress || {};
                        const indexed = progress.indexed || 0;
                        const total = progress.total || 0;
                        progressPercent = total > 0 ? Math.round((indexed / total) * 100) : 10;
                    } else {
                        // Для неизвестных этапов начинаем с 10%
                        progressPercent = 10;
                    }
                    
                    // Минимум 5% для выполняющихся этапов, максимум 95%
                    if (progressPercent < 5) {
                        progressPercent = 5;
                    } else if (progressPercent > 95) {
                        progressPercent = 95;
                    }
                } else {
                    progressPercent = 0; // Idle или error = 0%
                }
                
                currentProgress.style.width = `${progressPercent}%`;
                currentProgress.setAttribute('aria-valuenow', progressPercent);
                
                // Убираем детали этапа - показываем только название
                currentStageDetails.innerHTML = '';
            }
        } else {
            currentStageDiv.style.display = 'none';
        }
        
        // Обновляем общую статистику
        this.updatePipelineStats(status);
    }
    
    updatePipelineStats(status) {
        // Используем статистику из API
        const stats = status.stats || {};
        
        // Обновляем элементы статистики
        const newAdsElement = document.getElementById('stat-new-ads');
        const processedAdsElement = document.getElementById('stat-processed-ads');
        const duplicatesElement = document.getElementById('stat-duplicates');
        const realtorsElement = document.getElementById('stat-realtors');
        
        if (newAdsElement) newAdsElement.textContent = (stats.new_ads || 0).toLocaleString();
        if (processedAdsElement) processedAdsElement.textContent = (stats.processed_ads || 0).toLocaleString();
        if (duplicatesElement) duplicatesElement.textContent = (stats.duplicates_found || 0).toLocaleString();
        if (realtorsElement) realtorsElement.textContent = (stats.realtors_found || 0).toLocaleString();
    }
    
    // Функция updateStageDetails удалена - этапы теперь отображаются в разделе "Статус пайплайна"
    
    getProgressText(stageKey, stageInfo) {
        if (stageKey === 'scraping') {
            const progress = stageInfo.progress || {};
            const active = progress.sources_active || 0;
            const completed = progress.sources_completed || 0;
            const total = progress.total || 0;
            const newAds = progress.new_ads || 0;
            const processedAds = progress.processed_ads || 0;
            
            if (total === 0) return 'Подготовка...';
            
            let statusText = `Источников: ${completed}/${total} завершено`;
            if (active > 0) statusText += `, ${active} активных`;
            if (newAds > 0) statusText += `<br/>📈 Новых объявлений: ${newAds}`;
            if (processedAds > 0) statusText += `<br/>✅ Обработано: ${processedAds}`;
            
            return statusText;
            
        } else if (stageKey === 'photo_processing') {
            const progress = stageInfo.progress || {};
            const downloaded = progress.photos_downloaded || 0;
            const optimized = progress.photos_optimized || 0;
            const processed = progress.processed || 0;
            const total = progress.total || 0;
            
            if (total === 0) return 'Подсчет фотографий...';
            
            let statusText = `Обработано: ${processed}/${total}`;
            if (downloaded > 0) statusText += `<br/>📥 Загружено: ${downloaded}`;
            if (optimized > 0) statusText += `<br/>🎨 Оптимизировано: ${optimized}`;
            
            return statusText;
            
        } else if (stageKey === 'duplicate_processing') {
            const progress = stageInfo.progress || {};
            const found = progress.duplicates_found || 0;
            const processed = progress.processed || 0;
            const remaining = progress.remaining || 0;
            const groups = progress.groups_created || 0;
            
            let statusText = `Обработано: ${processed}`;
            if (remaining > 0) statusText += `, осталось: ${remaining}`;
            statusText += `<br/>🔍 Найдено дубликатов: ${found}`;
            if (groups > 0) statusText += `<br/>📂 Создано групп: ${groups}`;
            
            return statusText;
            
        } else if (stageKey === 'realtor_detection') {
            const progress = stageInfo.progress || {};
            const processed = progress.processed || 0;
            const detected = progress.detected || 0;
            const total = progress.total || 0;
            
            let statusText = total > 0 ? `Обработано: ${processed}/${total}` : `Обработано: ${processed}`;
            statusText += `<br/>👤 Найдено риэлторов: ${detected}`;
            
            return statusText;
            
        } else if (stageKey === 'elasticsearch_reindex') {
            const progress = stageInfo.progress || {};
            const indexed = progress.indexed || 0;
            const total = progress.total || 0;
            
            return total > 0 ? `Индексировано: ${indexed}/${total} записей` : 'Подготовка индекса...';
        }
        
        return stageInfo.message || 'Выполняется...';
    }
    
    formatDateTime(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleString('ru-RU', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateString;
        }
    }
    
    showNotification(message, type = 'info') {
        // Создаем простое уведомление
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;
        
        document.body.appendChild(toast);
        
        // Автоматически удаляем через 5 секунд
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }
    
    startAutoRefresh() {
        // Обновляем статус каждые 3 секунды
        this.refreshInterval = setInterval(() => {
            this.loadStatus();
            this.loadScrapingSources();
        }, 3000);
    }
    
    // Функция emergencyStop удалена
    
    async loadScrapingSources() {
        try {
            const [jobsResponse, statusResponse] = await Promise.all([
                fetch('/api/scraping/jobs'),
                fetch('/api/automation/status')
            ]);
            
            const jobs = await jobsResponse.json();
            const status = await statusResponse.json();
            
            this.updateScrapingSources(jobs, status.scraping_sources || []);
        } catch (error) {
            console.error('Error loading scraping sources:', error);
        }
    }
    
    updateScrapingSources(jobs, sources) {
        const container = document.getElementById('scraping-sources');
        container.innerHTML = '';
        
        const sourceIcons = {
            'house': 'bi-house',
            'lalafo': 'bi-shop',
            'stroka': 'bi-building'
        };
        
        sources.forEach(source => {
            // Найти последние задачи для этого источника
            const sourceJobs = jobs.filter(job => job.config === source).sort((a, b) => 
                new Date(b.created_at) - new Date(a.created_at)
            );
            
            const lastJob = sourceJobs[0];
            const isRunning = lastJob && lastJob.status === 'выполняется';
            
            const colDiv = document.createElement('div');
            colDiv.className = 'col-md-4 mb-3';
            
            let statusBadge = '';
            let statusClass = '';
            let progressInfo = '';
            
            if (isRunning) {
                statusBadge = '<span class="badge bg-warning pulse">Выполняется</span>';
                statusClass = 'border-warning';
                progressInfo = `
                    <div class="progress mb-2" style="height: 8px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated bg-warning" 
                             style="width: 50%" role="progressbar"></div>
                    </div>
                    <small class="text-muted">Собирает данные...</small>
                `;
            } else {
                const lastStatus = lastJob ? lastJob.status : 'не запущен';
                if (lastStatus === 'завершено') {
                    statusBadge = '<span class="badge bg-success">Завершен</span>';
                    statusClass = 'border-success';
                    progressInfo = `
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-success" style="width: 100%" role="progressbar"></div>
                        </div>
                        <small class="text-success">Парсинг завершен</small>
                    `;
                } else if (lastStatus === 'ошибка') {
                    statusBadge = '<span class="badge bg-danger">Ошибка</span>';
                    statusClass = 'border-danger';
                    progressInfo = `
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-danger" style="width: 0%" role="progressbar"></div>
                        </div>
                        <small class="text-danger">Произошла ошибка</small>
                    `;
                } else {
                    statusBadge = '<span class="badge bg-secondary">Готов</span>';
                    statusClass = '';
                    progressInfo = `
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-secondary" style="width: 0%" role="progressbar"></div>
                        </div>
                        <small class="text-muted">Ожидает запуска</small>
                    `;
                }
            }
            
            colDiv.innerHTML = `
                <div class="card h-100 ${statusClass}">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi ${sourceIcons[source] || 'bi-globe'} me-2"></i>
                            <strong>${source.toUpperCase()}</strong>
                        </div>
                        ${statusBadge}
                    </div>
                    <div class="card-body">
                        ${progressInfo}
                        ${lastJob ? `<div class="mt-2 small text-muted">
                            <i class="bi bi-clock"></i> Последний запуск: ${this.formatDateTime(lastJob.created_at)}
                        </div>` : ''}
                    </div>
                </div>
            `;
            
            container.appendChild(colDiv);
        });
    }
    
    async startSource(source) {
        try {
            const response = await fetch(`/api/scraping/start/${source}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showNotification(`🚀 Парсинг ${source} запущен!`, 'success');
            } else {
                this.showNotification(`❌ Ошибка запуска ${source}: ${result.message}`, 'error');
            }
            
            this.loadScrapingSources();
        } catch (error) {
            this.showNotification(`❌ Ошибка запуска ${source}`, 'error');
            console.error(`Error starting ${source}:`, error);
        }
    }
    
    async stopSource(source, jobId) {
        try {
            const response = await fetch(`/api/scraping/stop/${jobId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            if (response.ok) {
                this.showNotification(`🛑 Парсинг ${source} остановлен!`, 'warning');
            } else {
                this.showNotification(`❌ Ошибка остановки ${source}`, 'error');
            }
            
            this.loadScrapingSources();
        } catch (error) {
            this.showNotification(`❌ Ошибка остановки ${source}`, 'error');
            console.error(`Error stopping ${source}:`, error);
        }
    }
    
    async startAllSources() {
        try {
            const response = await fetch('/api/scraping/start-all', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            if (response.ok) {
                this.showNotification('🚀 Все источники запущены!', 'success');
            } else {
                this.showNotification('❌ Ошибка запуска источников', 'error');
            }
            
            this.loadScrapingSources();
        } catch (error) {
            this.showNotification('❌ Ошибка запуска всех источников', 'error');
            console.error('Error starting all sources:', error);
        }
    }
    
    async stopAllSources() {
        try {
            const jobsResponse = await fetch('/api/scraping/jobs');
            const jobs = await jobsResponse.json();
            
            const runningJobs = jobs.filter(job => job.status === 'выполняется');
            
            if (runningJobs.length === 0) {
                this.showNotification('ℹ️ Нет активных задач парсинга', 'info');
                return;
            }
            
            const stopPromises = runningJobs.map(job => 
                fetch(`/api/scraping/stop/${job.id}`, { method: 'POST' })
            );
            
            await Promise.all(stopPromises);
            
            this.showNotification(`🛑 Остановлено ${runningJobs.length} задач парсинга`, 'warning');
            this.loadScrapingSources();
        } catch (error) {
            this.showNotification('❌ Ошибка остановки источников', 'error');
            console.error('Error stopping all sources:', error);
        }
    }
    
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        if (this.logsInterval) {
            clearInterval(this.logsInterval);
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    window.automationManager = new AutomationManager();
});

// Очистка при выходе со страницы
window.addEventListener('beforeunload', function() {
    if (window.automationManager) {
        window.automationManager.destroy();
    }
});
