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

        // Apply coordinate overrides if available
        try {
            const or = await fetch('data/coordinate-overrides.json');
            if (or.ok) {
                const overrides = await or.json();
                let applied = 0;
                for (const [addr, coords] of Object.entries(overrides)) {
                    const normAddr = addr.replace('Orebro', 'Örebro').replace(' ,', ',').trim();
                    allData.listings.forEach(l => {
                        const key = (l.geocodeQuery || '').replace('Orebro', 'Örebro').replace(' ,', ',').trim();
                        if (key === normAddr) {
                            l.lat = coords[0];
                            l.lon = coords[1];
                            l.precise = true;
                            applied++;
                        }
                    });
                }
                if (applied > 0) console.log(`Applied ${applied} coordinate overrides to ${Object.keys(overrides).length} addresses`);
            }
        } catch(e) {}

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

function updatePageTexts() {
    const ht = HEADER_TEXTS[getLang()] || HEADER_TEXTS['sv'];
    document.getElementById('mapTitle').textContent = ht.title;
    document.getElementById('filterToggle').setAttribute('aria-label', t('Filters'));
    document.getElementById('filterToggle').setAttribute('title', t('Filters'));
    document.getElementById('loadingText').textContent = t('Loading');
}
