// Утилиты для веб-интерфейса

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
    // Используем глобальную функцию из main.js если она доступна
    if (window.showNotification && window.showNotification !== showNotification) {
        return window.showNotification(type, message);
    }
    
    // Если основная функция недоступна, используем упрощенную версию с защитой от дублирования
    window.activeNotifications = window.activeNotifications || new Set();
    
    // Создаем уникальный ключ для сообщения
    const notificationKey = `${type}:${message}`;
    
    // Проверяем не показывается ли уже такое же уведомление
    if (window.activeNotifications.has(notificationKey)) {
        console.log('Дублирующее уведомление заблокировано (utils.js):', message);
        return; // Не показываем дублирующее уведомление
    }
    
    // Добавляем в реестр активных уведомлений
    window.activeNotifications.add(notificationKey);
    
    const alertClass = type === 'error' ? 'danger' : type;
    const notificationId = 'notification-' + Date.now() + Math.random().toString(36).substr(2, 9);
    
    const alertHTML = `
        <div id="${notificationId}" class="alert alert-${alertClass} alert-dismissible fade show position-fixed notification-alert" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 400px;" 
             role="alert" data-notification-key="${notificationKey}">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHTML);
    
    // Сдвигаем существующие уведомления вниз
    repositionNotifications();
    
    // Обработчик для удаления из реестра при закрытии
    const notificationElement = document.getElementById(notificationId);
    if (notificationElement) {
        const closeButton = notificationElement.querySelector('.btn-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                window.activeNotifications.delete(notificationKey);
                repositionNotifications();
            });
        }
    }
    
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

// Функция для правильного позиционирования уведомлений (если не определена в main.js)
function repositionNotifications() {
    if (window.repositionNotifications && window.repositionNotifications !== repositionNotifications) {
        return window.repositionNotifications();
    }
    
    const notifications = document.querySelectorAll('.notification-alert');
    notifications.forEach((notification, index) => {
        const topOffset = 20 + (index * 80); // 80px между уведомлениями
        notification.style.top = topOffset + 'px';
        notification.style.transition = 'all 0.3s ease';
    });
}

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function initializeModals() {
    document.querySelectorAll('button[data-process]').forEach(button => {
        button.setAttribute('data-original-text', button.innerHTML);
    });
}

// Отображение объявлений
function displayAds(data) {
    const container = document.getElementById('ads-container');
    const pagination = document.getElementById('pagination');
    const totalInfo = document.getElementById('total-info');
    
    if (!container) {
        console.error('Контейнер ads-container не найден');
        return;
    }
    
    // Обновляем информацию о количестве
    if (totalInfo) {
        totalInfo.textContent = `Найдено ${data.total} объявлений`;
    }
    
    // Очищаем контейнер
    container.innerHTML = '';
    
    if (data.items && data.items.length > 0) {
        data.items.forEach(ad => {
            const adCard = createAdCard(ad);
            container.appendChild(adCard);
        });
    } else {
        container.innerHTML = `
            <div class="col-12">
                <div class="text-center text-muted py-5">
                    <i class="bi bi-inbox display-4 d-block mb-3"></i>
                    <h5>Объявления не найдены</h5>
                    <p>Попробуйте изменить параметры поиска</p>
                </div>
            </div>
        `;
    }
    
    // Обновляем пагинацию
    updatePagination(data, pagination);
}

function createAdCard(ad) {
    const card = document.createElement('div');
    card.className = 'col-lg-6 col-xl-4 mb-4';
    
    const location = ad.location ? `${ad.location.city || ''}, ${ad.location.district || ''}`.replace(/^,\s*|,\s*$/g, '') : '';
    const photo = ad.photos && ad.photos.length > 0 ? ad.photos[0].url : '/static/images/no-photo.jpg';
    
    // Правильное отображение цены с валютой
    let price = 'Цена не указана';
    if (ad.price) {
        if (ad.currency === 'USD') {
            price = `$${ad.price.toLocaleString()}`;
        } else if (ad.currency === 'SOM') {
            price = `${ad.price.toLocaleString()} сом`;
        } else if (ad.currency === 'EUR') {
            price = `€${ad.price.toLocaleString()}`;
        } else {
            price = `${ad.price.toLocaleString()} ${ad.currency || ''}`;
        }
    }
    
    card.innerHTML = `
        <div class="card h-100 shadow-sm">
            <div class="position-relative">
                <img src="${photo}" class="card-img-top" alt="Фото объявления" 
                     style="height: 200px; object-fit: cover;"
                     onerror="this.src='/static/images/no-photo.jpg'">
                ${(ad.realtor_id || ad.realtor) ? '<span class="badge bg-info position-absolute top-0 end-0 m-2">Риэлтор</span>' : ''}
                ${ad.duplicates_count > 0 ? `<span class="badge bg-warning position-absolute top-0 start-0 m-2">${ad.duplicates_count} дубл.</span>` : ''}
            </div>
            <div class="card-body d-flex flex-column">
                <h6 class="card-title">${escapeHtml(ad.title || 'Без названия').substring(0, 80)}${ad.title && ad.title.length > 80 ? '...' : ''}</h6>
                <div class="text-muted small mb-2">
                    <i class="bi bi-geo-alt"></i> ${location || 'Адрес не указан'}
                </div>
                <div class="mb-2">
                    ${ad.area_sqm ? `<span class="badge bg-light text-dark me-1">${ad.area_sqm} м²</span>` : ''}
                    ${ad.land_area_sotka ? `<span class="badge bg-success text-white me-1">${ad.land_area_sotka} сот.</span>` : ''}
                    ${ad.rooms ? `<span class="badge bg-light text-dark me-1">${ad.rooms} комн.</span>` : ''}
                    ${ad.floor ? `<span class="badge bg-light text-dark me-1">${ad.floor} этаж</span>` : ''}
                </div>
                <div class="mt-auto">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong class="text-success">${price}</strong>
                        <div>
                            <a href="/ad/${ad.id}" class="btn btn-primary btn-sm">
                            <i class="bi bi-eye"></i> Подробнее
                            </a>
                            ${ad.realtor_id ? `<a href="/realtor/${ad.realtor_id}" class="btn btn-outline-info btn-sm ms-1"><i class="bi bi-person"></i> Риэлтор</a>` : ''}
                        </div>
                    </div>
                    <small class="text-muted">${formatDateTime(ad.created_at)}</small>
                </div>
            </div>
        </div>
    `;
    
    return card;
}

function updatePagination(data, paginationContainer) {
    if (!paginationContainer) return;
    
    const totalPages = Math.ceil(data.total / data.limit);
    const currentPage = Math.floor(data.offset / data.limit) + 1;
    
    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    let paginationHTML = '<nav><ul class="pagination justify-content-center">';
    
    // Предыдущая страница
    if (currentPage > 1) {
        paginationHTML += `<li class="page-item">
            <a class="page-link" href="?${updateUrlParam('offset', (currentPage - 2) * data.limit)}">Предыдущая</a>
        </li>`;
    }
    
    // Номера страниц
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const isActive = i === currentPage;
        paginationHTML += `<li class="page-item ${isActive ? 'active' : ''}">
            <a class="page-link" href="?${updateUrlParam('offset', (i - 1) * data.limit)}">${i}</a>
        </li>`;
    }
    
    // Следующая страница
    if (currentPage < totalPages) {
        paginationHTML += `<li class="page-item">
            <a class="page-link" href="?${updateUrlParam('offset', currentPage * data.limit)}">Следующая</a>
        </li>`;
    }
    
    paginationHTML += '</ul></nav>';
    paginationContainer.innerHTML = paginationHTML;
}

function updateUrlParam(param, value) {
    const params = new URLSearchParams(window.location.search);
    params.set(param, value);
    return params.toString();
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
    
    params.set('offset', '0');
    window.location.search = params.toString();
}

function clearFilters() {
    const form = document.getElementById('filters-form');
    if (form) {
        form.reset();
        window.location.search = '';
    }
}

// Модальные окна для объявлений
function showAdModal(adId) {
    console.log('Загружаем объявление ID:', adId);
    
    fetch(`/api/ads/unique/${adId}`)
        .then(response => {
            console.log('Ответ сервера:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Данные объявления:', data);
            const modal = new bootstrap.Modal(document.getElementById('adModal'));
            populateAdModal(data);
            modal.show();
        })
        .catch(error => {
            console.error('Ошибка загрузки объявления:', error);
            showNotification('error', `Ошибка загрузки объявления: ${error.message}`);
        });
}

function populateAdModal(data) {
    console.log('Полученные данные:', data);
    
    // Получаем базовое объявление из API ответа
    const ad = data.base_ad || data;
    console.log('Обрабатываемое объявление:', ad);
    
    // Заголовок
    document.getElementById('modal-ad-title').textContent = ad.title || 'Без названия';
    console.log('Заголовок:', ad.title);
    
    // Цена с правильной валютой
    let priceText = 'Цена не указана';
    if (ad.price) {
        console.log('Цена и валюта:', ad.price, ad.currency);
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
    console.log('Итоговая цена:', priceText);
    document.getElementById('modal-ad-price').textContent = priceText;
    
    // Описание
    document.getElementById('modal-ad-description').textContent = 
        ad.description || 'Описание отсутствует';
    
    // Характеристики - показываем только заполненные поля
    const characteristics = document.getElementById('modal-ad-characteristics');
    const charFields = [];
    
    // Основные характеристики
    if (ad.area_sqm) charFields.push(`<strong>Площадь:</strong> ${ad.area_sqm} м²`);
    if (ad.land_area_sotka) charFields.push(`<strong>Участок:</strong> ${ad.land_area_sotka} сот.`);
    if (ad.rooms) charFields.push(`<strong>Комнаты:</strong> ${ad.rooms}`);
    if (ad.floor) {
        const floorText = ad.total_floors ? `${ad.floor}/${ad.total_floors}` : ad.floor;
        charFields.push(`<strong>Этаж:</strong> ${floorText}`);
    }
    if (ad.series) charFields.push(`<strong>Серия:</strong> ${ad.series}`);
    if (ad.building_type) charFields.push(`<strong>Тип дома:</strong> ${ad.building_type}`);
    if (ad.building_year) charFields.push(`<strong>Год постройки:</strong> ${ad.building_year}`);
    if (ad.condition) charFields.push(`<strong>Состояние:</strong> ${ad.condition}`);
    if (ad.repair) charFields.push(`<strong>Ремонт:</strong> ${ad.repair}`);
    if (ad.furniture) charFields.push(`<strong>Мебель:</strong> ${ad.furniture}`);
    if (ad.heating) charFields.push(`<strong>Отопление:</strong> ${ad.heating}`);
    if (ad.hot_water) charFields.push(`<strong>Горячая вода:</strong> ${ad.hot_water}`);
    if (ad.gas) charFields.push(`<strong>Газ:</strong> ${ad.gas}`);
    if (ad.ceiling_height) charFields.push(`<strong>Высота потолков:</strong> ${ad.ceiling_height} м`);
    
    // Дополнительная информация
    if (ad.source_name) charFields.push(`<strong>Источник:</strong> ${ad.source_name}`);
    
    // Информация о риэлторе (новая логика)
    if (ad.realtor_id || ad.realtor) {
        let realtorText = 'Да';
        if (ad.realtor && ad.realtor.name) {
            realtorText += ` (${ad.realtor.name})`;
        }
        if (ad.realtor && ad.realtor.company_name) {
            realtorText += ` - ${ad.realtor.company_name}`;
        }
        if (ad.realtor && ad.realtor.total_ads_count) {
            realtorText += ` [${ad.realtor.total_ads_count} объявлений]`;
        }
        charFields.push(`<strong>Риэлтор:</strong> ${realtorText}`);
    } else {
        charFields.push(`<strong>Риэлтор:</strong> Нет`);
    }

    
    // Телефоны
    if (ad.phone_numbers && ad.phone_numbers.length > 0) {
        charFields.push(`<strong>Телефоны:</strong> ${ad.phone_numbers.join(', ')}`);
    }
    
    // Разбиваем на две колонки
    const halfPoint = Math.ceil(charFields.length / 2);
    const leftColumn = charFields.slice(0, halfPoint);
    const rightColumn = charFields.slice(halfPoint);
    
    characteristics.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                ${leftColumn.join('<br>')}
            </div>
            <div class="col-md-6">
                ${rightColumn.join('<br>')}
            </div>
        </div>
    `;
    
    // Адрес
    const location = ad.location;
    let locationText = 'Адрес не указан';
    if (location) {
        const parts = [];
        if (location.city) parts.push(location.city);
        if (location.district) parts.push(location.district);
        if (location.address) parts.push(location.address);
        if (parts.length > 0) locationText = parts.join(', ');
    }
    document.getElementById('modal-ad-location').textContent = locationText;
    
    // Фотографии
    const photosContainer = document.getElementById('modal-ad-photos');
    if (ad.photos && ad.photos.length > 0) {
        photosContainer.innerHTML = ad.photos.map((photo, index) => 
            `<div class="col-lg-3 col-md-4 col-sm-6 mb-3">
                <img src="${photo.url}" class="img-fluid rounded shadow-sm" alt="Фото ${index + 1}" 
                     style="height: 180px; width: 100%; object-fit: cover; cursor: pointer;"
                     onclick="showPhotoModal('${photo.url}')"
                     onerror="this.style.display='none'">
            </div>`
        ).join('');
    } else {
        photosContainer.innerHTML = '<div class="col-12"><p class="text-muted text-center py-3"><i class="bi bi-image"></i> Фотографии отсутствуют</p></div>';
    }
    
    // Информация о дубликатах
    const duplicatesInfo = document.getElementById('modal-ad-duplicates');
    const duplicatesCount = data.total_duplicates || 0;
    const showDuplicatesBtn = document.getElementById('show-duplicates-btn');
    
    console.log('Количество дубликатов:', duplicatesCount);
    
    duplicatesInfo.innerHTML = `
        <span class="badge bg-${duplicatesCount > 0 ? 'warning' : 'success'}">
            ${duplicatesCount} дубликатов
        </span>
        ${duplicatesCount > 0 ? `<br><small class="text-muted">Найдено ${duplicatesCount} похожих объявлений</small>` : ''}
    `;
    
    // Показываем кнопку только если есть дубликаты
    if (duplicatesCount > 0) {
        console.log('Показываем кнопку дубликатов');
        showDuplicatesBtn.style.display = 'block';
        
        // Удаляем старые обработчики и добавляем новый
        showDuplicatesBtn.replaceWith(showDuplicatesBtn.cloneNode(true));
        const newBtn = document.getElementById('show-duplicates-btn');
        newBtn.onclick = () => showDuplicatesModal(data.unique_ad_id);
    } else {
        console.log('Скрываем кнопку дубликатов');
        showDuplicatesBtn.style.display = 'none';
    }
    
    // Кнопка источника
    const sourceLinkContainer = document.getElementById('source-link-container');
    const sourceLinkBtn = document.getElementById('source-link-btn');
    
    console.log('=== ОТЛАДКА КНОПКИ ИСТОЧНИКА ===');
    console.log('sourceLinkContainer найден:', !!sourceLinkContainer);
    console.log('sourceLinkBtn найден:', !!sourceLinkBtn);
    console.log('data.base_ad:', data.base_ad);
    console.log('ad:', ad);
    
    // Получаем source_url из base_ad (для уникальных объявлений)
    const sourceUrl = data.base_ad?.source_url || ad.source_url;
    console.log('Итоговый sourceUrl:', sourceUrl);
    
    if (sourceUrl && sourceLinkContainer && sourceLinkBtn) {
        console.log('✅ Показываем кнопку источника:', sourceUrl);
        sourceLinkBtn.href = sourceUrl;
        sourceLinkContainer.style.display = 'block';
    } else {
        console.log('❌ Скрываем кнопку источника, причины:');
        console.log('- sourceUrl:', !!sourceUrl);
        console.log('- sourceLinkContainer:', !!sourceLinkContainer);
        console.log('- sourceLinkBtn:', !!sourceLinkBtn);
        if (sourceLinkContainer) {
            sourceLinkContainer.style.display = 'none';
        }
    }
}

// Функция для показа дубликатов объявления
function showDuplicatesModal(uniqueAdId) {
    console.log('Загружаем дубликаты для уникального объявления ID:', uniqueAdId);
    
    // Проверяем, не открыто ли уже модальное окно дубликатов
    const existingModal = document.getElementById('duplicatesModal');
    if (existingModal.classList.contains('show')) {
        console.log('Модальное окно дубликатов уже открыто');
        return;
    }
    
    fetch(`/api/ads/unique/${uniqueAdId}`)
        .then(response => {
            console.log('Ответ сервера:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Данные дубликатов:', data);
            populateDuplicatesModal(data);
            const modalElement = document.getElementById('duplicatesModal');
            console.log('Модальный элемент найден:', !!modalElement);
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
            console.log('Модальное окно дубликатов должно быть открыто');
        })
        .catch(error => {
            console.error('Ошибка загрузки дубликатов:', error);
            showNotification('error', `Ошибка загрузки дубликатов: ${error.message}`);
        });
}

function populateDuplicatesModal(data) {
    console.log('Данные для модального окна дубликатов:', data);
    console.log('Дубликаты из API:', data.duplicates);
    console.log('Базовое объявление:', data.base_ad);
    
    // Заголовок
    document.getElementById('duplicates-main-title').textContent = data.base_ad.title || 'Основное объявление';
    document.getElementById('duplicates-count').textContent = data.duplicates.length;
    
    // Список дубликатов
    const duplicatesList = document.getElementById('duplicates-list');
    
    if (data.duplicates.length === 0) {
        console.log('Дубликаты не найдены');
        duplicatesList.innerHTML = '<div class="col-12"><p class="text-muted text-center py-3">Дубликаты не найдены</p></div>';
        return;
    }
    
    console.log('Количество дубликатов:', data.duplicates.length);
    console.log('Первый дубликат:', data.duplicates[0]);
    
    duplicatesList.innerHTML = data.duplicates.map(duplicate => {
        // Правильное отображение валюты для дубликатов
        let priceText = 'Цена не указана';
        if (duplicate.price) {
            if (duplicate.currency === 'USD') {
                priceText = `$${duplicate.price.toLocaleString()}`;
            } else if (duplicate.currency === 'SOM') {
                priceText = `${duplicate.price.toLocaleString()} сом`;
            } else if (duplicate.currency === 'EUR') {
                priceText = `€${duplicate.price.toLocaleString()}`;
            } else {
                priceText = `${duplicate.price.toLocaleString()} ${duplicate.currency || ''}`;
            }
        }
        
        const locationText = duplicate.location ? 
            [duplicate.location.city, duplicate.location.district, duplicate.location.address].filter(x => x).join(', ') : 
            'Адрес не указан';
        
        const photoUrl = duplicate.photos && duplicate.photos.length > 0 ? 
            duplicate.photos[0].url : 
            null;
        
        const sourceIcon = {
            'house.kg': 'bi-house',
            'lalafo.kg': 'bi-shop',
            'stroka.kg': 'bi-newspaper'
        }[duplicate.source_name] || 'bi-globe';
        
        return `
            <div class="col-lg-4 col-md-6 mb-4">
                <div class="card h-100">
                    <div class="position-relative">
                        ${photoUrl ? 
                            `<img src="${photoUrl}" class="card-img-top" style="height: 200px; object-fit: cover;" alt="Фото">` : 
                            `<div class="card-img-top bg-light d-flex align-items-center justify-content-center" style="height: 200px;">
                                <i class="bi bi-image text-muted" style="font-size: 2rem;"></i>
                            </div>`
                        }
                        <span class="badge bg-primary position-absolute" style="top: 10px; right: 10px;">
                            <i class="${sourceIcon}"></i> ${duplicate.source_name ? duplicate.source_name.toUpperCase() : 'НЕИЗВЕСТНО'}
                        </span>
                    </div>
                    
                    <div class="card-body d-flex flex-column">
                        <h6 class="card-title">${duplicate.title ? duplicate.title.substring(0, 60) + (duplicate.title.length > 60 ? '...' : '') : 'Без названия'}</h6>
                        
                        <div class="text-success fw-bold mb-2">${priceText}</div>
                        
                        <div class="text-muted mb-3">
                            ${duplicate.area_sqm ? duplicate.area_sqm + ' м² • ' : ''}
                            ${duplicate.rooms ? duplicate.rooms + ' комн.' : ''}
                            <br><i class="bi bi-geo-alt"></i> ${locationText}
                        </div>
                        
                        <div class="mt-auto">
                            <small class="text-muted">
                                <i class="bi bi-calendar"></i> 
                                ${duplicate.created_at ? new Date(duplicate.created_at).toLocaleDateString() : 'Дата неизвестна'}
                            </small>
                            ${duplicate.source_url ? 
                                `<br><a href="${duplicate.source_url}" target="_blank" class="btn btn-outline-primary btn-sm mt-2">
                                    <i class="bi bi-box-arrow-up-right"></i> Источник
                                </a>` : ''
                            }
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    console.log('HTML дубликатов сгенерирован, длина:', duplicatesList.innerHTML.length);
    console.log('Первые 200 символов HTML:', duplicatesList.innerHTML.substring(0, 200));
    console.log('Элемент duplicates-list найден:', !!duplicatesList);
    console.log('Стили элемента duplicates-list:', window.getComputedStyle(duplicatesList).display);
    
    // Проверяем, есть ли дочерние элементы
    setTimeout(() => {
        console.log('Количество дочерних элементов в duplicates-list:', duplicatesList.children.length);
        if (duplicatesList.children.length > 0) {
            console.log('Первый дочерний элемент:', duplicatesList.children[0]);
        }
    }, 100);
}

// Функция для показа фотографии в полном размере
function showPhotoModal(photoUrl) {
    // Создаем модальное окно для фото если его нет
    let photoModal = document.getElementById('photoModal');
    if (!photoModal) {
        photoModal = document.createElement('div');
        photoModal.innerHTML = `
            <div class="modal fade" id="photoModal" tabindex="-1">
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Фотография</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center">
                            <img id="modal-photo-img" src="" class="img-fluid" alt="Фотография">
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(photoModal);
    }
    
    document.getElementById('modal-photo-img').src = photoUrl;
    const modal = new bootstrap.Modal(document.getElementById('photoModal'));
    modal.show();
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