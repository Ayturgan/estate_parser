// JavaScript функции для дашборда

// Создание графиков для дашборда
function initializeDashboardCharts(statsData) {
    // График источников
    if (document.getElementById('sourcesChart')) {
        createSourcesChart(statsData.sources_stats);
    }
    
    // График активности по времени
    if (document.getElementById('activityChart')) {
        createActivityChart(statsData.activity_stats);
    }
    
    // График дедупликации
    if (document.getElementById('deduplicationChart')) {
        createDeduplicationChart(statsData);
    }
}

function createSourcesChart(sourcesData) {
    const ctx = document.getElementById('sourcesChart');
    if (!ctx || !sourcesData) return;
    
    // Обновление данных графика
    if (window.dashboardCharts && window.dashboardCharts.sourcesChart) {
        const chart = window.dashboardCharts.sourcesChart;
        chart.data.labels = sourcesData.map(s => s.source_name);
        chart.data.datasets[0].data = sourcesData.map(s => s.count);
        chart.update();
        return;
    }
    
    // Создание графика
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: sourcesData.map(s => s.source_name),
            datasets: [{
                data: sourcesData.map(s => s.count),
                backgroundColor: [
                    '#0d6efd',
                    '#198754', 
                    '#ffc107',
                    '#dc3545',
                    '#0dcaf0'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    if (chart) {
        window.dashboardCharts.sourcesChart = chart;
    }
}

function createActivityChart(activityData) {
    const ctx = document.getElementById('activityChart');
    if (!ctx || !activityData) return;
    
    // Обновление данных графика
    if (window.dashboardCharts && window.dashboardCharts.activityChart) {
        const chart = window.dashboardCharts.activityChart;
        chart.data.labels = activityData.map(d => d.date);
        chart.data.datasets[0].data = activityData.map(d => d.new_ads);
        chart.update();
        return;
    }
    
    // Создание графика
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: activityData.map(d => d.date),
            datasets: [{
                label: 'Новые объявления',
                data: activityData.map(d => d.new_ads),
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    if (chart) {
        window.dashboardCharts.activityChart = chart;
    }
}

function createDeduplicationChart(statsData) {
    const ctx = document.getElementById('deduplicationChart');
    if (!ctx) return;
    
    // Обновление данных графика
    if (window.dashboardCharts && window.dashboardCharts.deduplicationChart) {
        const chart = window.dashboardCharts.deduplicationChart;
        chart.data.datasets[0].data = [statsData.total_unique_ads, statsData.total_duplicates];
        chart.update();
        return;
    }

    // Создание графика
    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Уникальные', 'Дубликаты'],
            datasets: [{
                data: [statsData.total_unique_ads, statsData.total_duplicates],
                backgroundColor: ['#198754', '#ffc107']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });

    if (chart) {
        window.dashboardCharts.deduplicationChart = chart;
    }
}

// Инициализация дашборда при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, что мы на странице дашборда
    if (document.querySelector('h1.text-gradient span i.bi-speedometer2')) {
        
        // Глобальный объект для хранения инстансов графиков
        window.dashboardCharts = {
            sourcesChart: null,
            activityChart: null,
            deduplicationChart: null
        };

        // Инициализируем графики с начальными данными, переданными с сервера
        if (window.statsData) {
            initializeDashboardCharts(window.statsData);
        } else {
            console.error("Статистические данные (window.statsData) не найдены.");
        }
        
        // Настройка WebSocket событий для дашборда
        if (window.realtimeClient) { 
            console.log("Подписываемся на события WebSocket для дашборда...");
            
            window.realtimeClient.on('stats_update', function(data) {
                console.log("📊 Получено обновление статистики через WebSocket:", data);
                if (data.sources_stats) {
                    createSourcesChart(data.sources_stats);
                }
                if (data.activity_stats) {
                    createActivityChart(data.activity_stats);
                }
                // Для графика дедупликации нужны общие цифры
                createDeduplicationChart(data);
            });
        }
    }
}); 