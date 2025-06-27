// JavaScript функции для дашборда

// Обновление статистики дашборда
async function updateDashboardStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        updateStatCard('total-unique-ads', stats.total_unique_ads);
        updateStatCard('total-ads', stats.total_original_ads);
        updateStatCard('duplicates', stats.total_duplicates);
        updateStatCard('realtor-ads', stats.realtor_ads);
        
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
    
    return new Chart(ctx, {
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
}

function createActivityChart(activityData) {
    const ctx = document.getElementById('activityChart');
    if (!ctx || !activityData) return;
    
    return new Chart(ctx, {
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
}

function createDeduplicationChart(statsData) {
    const ctx = document.getElementById('deduplicationChart');
    if (!ctx) return;
    
    return new Chart(ctx, {
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
} 