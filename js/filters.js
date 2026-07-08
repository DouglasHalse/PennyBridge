// filters.js — Multi-landlord filter logic and UI

let filterState = {
    landlords: [],
    tags: [],
    minRooms: 1,
    priceMax: 5000,
    availableNow: false,
};

let allListings = [];
let onFilterChange = null;
let priceDebounce = null;
let roomsDebounce = null;
let dataGenerated = null;

function initFilters(listings, callback, generated) {
    allListings = listings;
    onFilterChange = callback;
    dataGenerated = generated;
    buildFilterUI(listings);
    applyFilters();
}

function getRoomCount(listing) {
    // Extract numeric room count from type string
    const t = listing.type || '';
    const short = listing.shortType || '';
    // Try "3 rum och kök", "2 rum kokvrå", "3 RKV"
    const m = t.match(/^(\d+)/) || short.match(/^(\d+)/);
    return m ? parseInt(m[1]) : 0;
}

function buildFilterUI(listings) {
    const container = document.getElementById('filters');

    const sources = [...new Set(listings.map(s => s.source).filter(Boolean))].sort();
    const prices = listings.map(s => s.price || 0).filter(p => p > 0);
    const priceMax = Math.ceil(Math.max(...prices, 3000) / 100) * 100;

    // Compute max rooms across all listings
    const roomCounts = listings.map(s => getRoomCount(s)).filter(r => r > 0);
    const maxRooms = Math.max(...roomCounts, 5);

    // Collect all tags present
    const allTags = new Set();
    listings.forEach(s => { if (s.tags) s.tags.forEach(t => allTags.add(t)); });

    filterState.priceMax = priceMax;
    filterState.minRooms = 1;
    filterState.landlords = [];
    filterState.tags = [];

    container.innerHTML = `
        <div class="filter-group">
            <label>${t('Landlord')}</label>
            <div class="multi-select" id="landlordMultiSelect">
                <div class="multi-select-trigger" id="landlordSelectTrigger">
                    <span class="multi-select-label">${t('All landlords')}</span>
                    <span class="multi-select-arrow">▼</span>
                </div>
                <div class="multi-select-dropdown" id="landlordSelectDropdown">
                    ${sources.map(src => {
                        const meta = getLandlordMeta(src);
                        return `<label class="multi-select-option">
                            <input type="checkbox" value="${src}">
                            <span class="tab-dot" style="background:${meta.color}"></span>
                            ${meta.name}
                        </label>`;
                    }).join('')}
                </div>
            </div>
        </div>

        <div class="filter-row">
            <div class="filter-group filter-half">
                <label>${t('Rooms')}: <strong id="roomsDisplay">${t('All')}</strong></label>
                <input type="range" id="roomsSlider" min="1" max="${maxRooms}" value="1" step="1">
            </div>

            <div class="filter-group filter-half">
                <label>${t('Max price')}: <strong id="priceDisplay">${priceMax} ${t('kr/month')}</strong></label>
                <input type="range" id="priceMaxSlider" min="0" max="${priceMax}" value="${priceMax}" step="100">
            </div>
        </div>

        ${allTags.size > 0 ? `
        <div class="filter-group">
            <label>${t('Tags')}</label>
            <div class="tag-filters">
                ${[...allTags].sort().map(tg =>
                    `<span class="tag-pill" data-tag="${tg}" onclick="toggleTag('${tg}')">${getTagLabel(tg)}</span>`
                ).join('')}
            </div>
        </div>
        ` : ''}

        <div class="filter-group">
            <label class="checkbox-row">
                <input type="checkbox" id="availableNow">
                ${t('Available now')}
            </label>
        </div>
    `;

    // Landlord multi-select
    setupMultiSelect('landlordMultiSelect', 'landlordSelectTrigger', 'landlordSelectDropdown',
        () => filterState.landlords, (vals) => { filterState.landlords = vals; });

    // Rooms slider
    document.getElementById('roomsSlider').addEventListener('input', (e) => {
        const val = +e.target.value;
        const label = val === 1 ? t('All') : val + ' ' + t('Rooms').toLowerCase() + '+';
        document.getElementById('roomsDisplay').textContent = label;
        clearTimeout(roomsDebounce);
        roomsDebounce = setTimeout(() => {
            filterState.minRooms = val;
            applyFilters();
        }, 80);
    });

    // Price slider
    document.getElementById('priceMaxSlider').addEventListener('input', (e) => {
        const val = +e.target.value;
        document.getElementById('priceDisplay').textContent = `${val} ${t('kr/month')}`;
        clearTimeout(priceDebounce);
        priceDebounce = setTimeout(() => {
            filterState.priceMax = val;
            applyFilters();
        }, 80);
    });

    // Available now
    document.getElementById('availableNow').addEventListener('change', (e) => {
        filterState.availableNow = e.target.checked;
        applyFilters();
    });
}

function setupMultiSelect(containerId, triggerId, dropdownId, getter, setter) {
    const dropdown = document.getElementById(dropdownId);
    const trigger = document.getElementById(triggerId);
    const label = trigger.querySelector('.multi-select-label');

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('open');
    });

    dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', () => {
            const vals = [...dropdown.querySelectorAll('input:checked')].map(c => c.value);
            setter(vals);
            updateDisplay();
            applyFilters();
        });
    });

    function updateDisplay() {
        const checked = dropdown.querySelectorAll('input:checked');
        if (checked.length === 0) {
            label.textContent = t('All landlords');
        } else if (checked.length <= 2) {
            label.textContent = [...checked].map(cb => {
                const parent = cb.parentElement;
                return parent.textContent.trim();
            }).join(', ');
        } else {
            label.textContent = checked.length + ' ' + t('listings').toLowerCase();
        }
    }

    document.addEventListener('click', (e) => {
        if (!document.getElementById(containerId).contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });
}

function toggleTag(tag) {
    const idx = filterState.tags.indexOf(tag);
    if (idx >= 0) {
        filterState.tags.splice(idx, 1);
    } else {
        filterState.tags.push(tag);
    }
    document.querySelectorAll('.tag-pill').forEach(pill => {
        pill.classList.toggle('active', filterState.tags.includes(pill.dataset.tag));
    });
    applyFilters();
}

function applyFilters() {
    const today = new Date().toISOString().split('T')[0];

    const filtered = allListings.filter(listing => {
        if (filterState.landlords.length > 0 && !filterState.landlords.includes(listing.source)) return false;
        if (filterState.minRooms > 1 && getRoomCount(listing) < filterState.minRooms) return false;
        if (filterState.tags.length > 0) {
            const listingTags = listing.tags || [];
            if (!filterState.tags.some(t => listingTags.includes(t))) return false;
        }
        if ((listing.price || 0) > filterState.priceMax) return false;
        if (filterState.availableNow) {
            if (!listing.availableFrom || listing.availableFrom > today) return false;
        }
        return true;
    });

    filtered.sort((a, b) => {
        const aAvail = a.availableFrom && a.availableFrom <= today ? 0 : 1;
        const bAvail = b.availableFrom && b.availableFrom <= today ? 0 : 1;
        if (aAvail !== bAvail) return aAvail - bAvail;
        return (a.price || 0) - (b.price || 0);
    });

    updateStats(filtered.length);
    updateResultsList(filtered);

    if (onFilterChange) onFilterChange(filtered);
}

function updateStats(showing) {
    const hoursAgo = dataGenerated ? Math.round((Date.now() - new Date(dataGenerated)) / (1000 * 60 * 60)) : null;
    const ageStr = hoursAgo != null
        ? ` · ${t('updated')} ${hoursAgo < 24 ? hoursAgo + 'h ' : Math.round(hoursAgo / 24) + 'd '}${t('ago')}`
        : '';
    document.getElementById('stats').innerHTML = `
        <p class="stats-text">${t('Showing')} <strong>${showing}</strong> ${t('of')} ${allListings.length} ${t('listings')}${ageStr}</p>
    `;
}

function updateResultsList(listings) {
    const container = document.getElementById('resultsList');
    const today = new Date().toISOString().split('T')[0];
    const maxShow = 200;

    const html = listings.slice(0, maxShow).map(listing => {
        const landlord = getLandlordMeta(listing.source);
        const isAvailable = listing.availableFrom && listing.availableFrom <= today;
        const rooms = getRoomLabel(listing.type);
        const url = getListingUrl(listing);
        const thumb = getThumbnailUrl(listing);

        const tags = (listing.tags || []).map(tg =>
            `<span class="tag-pill active" style="font-size:0.6rem;padding:1px 5px;margin-left:2px;background:${landlord.color};color:#fff;border-color:${landlord.color}">${getTagLabel(tg)}</span>`
        ).join('');

        return `
        <div class="result-card ${isAvailable ? 'available' : ''}"
             data-id="${listing.id}"
             tabindex="0"
             onmouseenter="highlightMapMarker('${listing.id}')"
             onmouseleave="unhighlightMapMarker()"
             onclick="flyToSpot('${listing.id}')"
             onkeydown="if(event.key==='Enter')flyToSpot('${listing.id}')">
            <div class="result-image">
                ${thumb
                    ? `<img src="${thumb}" alt="" loading="lazy">`
                    : `<div class="no-image">🏠</div>`}
            </div>
            <div class="result-info">
                <h4><span class="result-badge" style="background:${landlord.color}">${landlord.short}</span>${listing.displayName}${tags}</h4>
                <p class="result-price">${formatPrice(listing.price)}${rooms ? ' &middot; ' + rooms : ''}${listing.sqm ? ' &middot; ' + Math.round(listing.sqm) + ' ' + t('sqm') : ''}</p>
                <p class="result-available">
                    ${listing.availableFrom ? t('Available from') + ' ' + formatDate(listing.availableFrom) : '—'}
                    <a href="${url}" target="_blank" rel="noopener" class="result-link"
                       onclick="event.stopPropagation()">${t('View listing')} ↗</a>
                </p>
                <div style="margin-top:1px;">
                    <a href="#" id="reportBtn_${listing.id}" onclick="event.preventDefault();event.stopPropagation();submitReport('${listing.id}')" style="font-size:0.6rem;color:var(--text-secondary);text-decoration:none;">📍 ${t('Report wrong location')}</a>
                </div>
            </div>
        </div>`;
    }).join('');

    if (listings.length > maxShow) {
        container.innerHTML = html + `<p class="results-truncated">+ ${listings.length - maxShow} ${t('More')}</p>`;
    } else if (listings.length === 0) {
        container.innerHTML = `<p class="results-empty">${t('No results')}</p>`;
    } else {
        container.innerHTML = html;
    }
}
