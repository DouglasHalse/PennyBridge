// app.js — PennyBridge entry point

const HEADER_TEXTS = {
    sv: { title: '🌉 PennyBridge — Hyreskartan' },
    en: { title: '🌉 PennyBridge — Rental Map' },
};

let allData = null;

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('langToggle').textContent = getLang() === 'en' ? 'SV' : 'EN';
    document.getElementById('langToggle').addEventListener('click', toggleLanguage);

    updatePageTexts();

    try {
        initMap();

        const response = await fetch('data/listings.json');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        allData = await response.json();

        console.log(`Loaded ${allData.total} listings from ${Object.keys(allData.landlords || {}).length} landlords`);

        const genDate = new Date(allData.generated);
        const daysOld = (Date.now() - genDate) / (1000 * 60 * 60 * 24);
        if (daysOld > 7) console.warn(`Data is ${Math.round(daysOld)} days old`);

        // Count by landlord
        const landlordCounts = {};
        allData.listings.forEach(l => {
            landlordCounts[l.source] = (landlordCounts[l.source] || 0) + 1;
        });

        // Build landlord tabs
        buildCategoryTabs(landlordCounts);

        // Initialize with all listings
        initFilters(allData.listings, (filtered) => addMarkers(filtered), allData.generated);

        document.getElementById('loading').style.display = 'none';

        // Mobile filter toggle
        const sidebar = document.getElementById('sidebar');
        const toggleBtn = document.getElementById('filterToggle');
        const backdrop = document.getElementById('sidebarBackdrop');
        const mapEl = document.getElementById('map');

        function openSidebar() {
            sidebar.classList.add('open');
            toggleBtn.classList.add('active');
            backdrop.style.display = 'block';
        }
        window.closeSidebar = function() {
            sidebar.classList.remove('open');
            toggleBtn.classList.remove('active');
            backdrop.style.display = 'none';
        };

        toggleBtn.addEventListener('click', () => {
            sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
        });

        backdrop.addEventListener('click', closeSidebar);

        mapEl.addEventListener('click', () => {
            if (window.innerWidth < 768) closeSidebar();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'f' && e.ctrlKey) {
                e.preventDefault();
                sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
            }
        });

    } catch (err) {
        console.error('Failed to load data:', err);
        document.getElementById('loading').innerHTML =
            `<div class="error-overlay"><p>${t('Load error')}</p><p class="error-hint">${err.message}</p></div>`;
    }
});

function buildCategoryTabs(landlordCounts) {
    const container = document.getElementById('categoryTabs');
    const lang = getLang();

    // Single group: All Landlords
    const landlords = Object.keys(LANDLORD_META);
    const presentLandlords = landlords.filter(l => landlordCounts[l]);

    let html = '<div class="category-group">';
    html += `<div class="category-group-label">${lang === 'sv' ? 'Värdar' : 'Landlords'}</div>`;
    html += '<div class="category-group-tabs">';

    presentLandlords.forEach(src => {
        const meta = LANDLORD_META[src];
        const count = landlordCounts[src];
        html += `<button class="category-tab" data-landlord="${src}" onclick="filterByLandlord('${src}')">
            <span class="tab-dot" style="background:${meta.color}"></span>${meta.name}<span class="tab-count">${count}</span>
        </button>`;
    });

    html += '</div></div>';
    container.innerHTML = html;

    // Fade indicators for mobile
    container.insertAdjacentHTML('afterbegin',
        '<div class="category-tabs-fade category-tabs-fade-left" id="fadeLeft"></div>');
    container.insertAdjacentHTML('beforeend',
        '<div class="category-tabs-fade category-tabs-fade-right" id="fadeRight"></div>');

    const fadeLeft = document.getElementById('fadeLeft');
    const fadeRight = document.getElementById('fadeRight');

    function updateFades() {
        const canScroll = container.scrollWidth > container.clientWidth;
        fadeLeft.classList.toggle('visible', canScroll && container.scrollLeft > 2);
        fadeRight.classList.toggle('visible', canScroll && container.scrollLeft < container.scrollWidth - container.clientWidth - 2);
    }

    updateFades();
    container.addEventListener('scroll', updateFades);
    window.addEventListener('resize', updateFades);
}

function filterByLandlord(source) {
    // Toggle landlord filter
    const idx = filterState.landlords.indexOf(source);
    if (idx >= 0) {
        filterState.landlords.splice(idx, 1);
    } else {
        filterState.landlords = [source]; // Select only this landlord
    }

    // Update tab active state
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.toggle('active', filterState.landlords.includes(tab.dataset.landlord));
    });

    // Update the landlord multi-select checkboxes
    const dropdown = document.getElementById('landlordSelectDropdown');
    if (dropdown) {
        dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = filterState.landlords.includes(cb.value);
        });
        // Update display
        const label = document.querySelector('#landlordSelectTrigger .multi-select-label');
        if (label) {
            if (filterState.landlords.length === 0) {
                label.textContent = t('All landlords');
            } else if (filterState.landlords.length === 1) {
                label.textContent = getLandlordMeta(filterState.landlords[0]).name;
            } else {
                label.textContent = filterState.landlords.length + ' ' + t('listings').toLowerCase();
            }
        }
    }

    applyFilters();
}

function updatePageTexts() {
    const ht = HEADER_TEXTS[getLang()] || HEADER_TEXTS['sv'];
    document.getElementById('mapTitle').textContent = ht.title;
    document.getElementById('filterToggle').setAttribute('aria-label', t('Filters'));
    document.getElementById('filterToggle').setAttribute('title', t('Filters'));
    document.getElementById('loadingText').textContent = t('Loading');
}
