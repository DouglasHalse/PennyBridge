// map.js — Leaflet map with clustered markers colored by landlord

const MAP_CENTER = [59.275, 15.213];
const MAP_ZOOM = 13;

let map;
let markerCluster;
let allMarkers = [];
let markerLookup = {};

function initMap() {
    map = L.map('map', {
        center: MAP_CENTER,
        zoom: MAP_ZOOM,
        zoomControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
    }).addTo(map);

    markerCluster = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        iconCreateFunction: function (cluster) {
            const count = cluster.getChildCount();
            let size = count > 100 ? 'large' : count > 20 ? 'medium' : 'small';
            return L.divIcon({
                html: `<div class="cluster-icon cluster-${size}">${count}</div>`,
                className: 'cluster-container',
                iconSize: L.point(40, 40),
            });
        },
    });

    map.addLayer(markerCluster);
    L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map);
    L.control.locate({ position: 'topright', strings: { title: 'Show my location' }, flyTo: true }).addTo(map);
}

function createMarkerIcon(listing) {
    const landlord = getLandlordMeta(listing.source);
    const size = 11;
    return L.divIcon({
        className: 'custom-marker',
        html: `<div style="
            width:${size*2}px;height:${size*2}px;
            background:${landlord.color};
            border:2px solid white;
            border-radius:50%;
            box-shadow:0 1px 4px rgba(0,0,0,0.3);
            cursor:pointer;
            display:flex;align-items:center;justify-content:center;
            font-size:${size-2}px;
        "></div>`,
        iconSize: [size * 2, size * 2],
        iconAnchor: [size, size],
    });
}

function createPopupContent(listing) {
    const landlord = getLandlordMeta(listing.source);
    const price = formatPrice(listing.price);
    const avail = listing.availableFrom ? formatDate(listing.availableFrom) : t('Not available');
    const rooms = getRoomLabel(listing.type);
    const url = getListingUrl(listing);

    let imgHtml = '';
    const thumb = getThumbnailUrl(listing);
    if (thumb) {
        imgHtml = `<img src="${thumb}"
             style="width:100%;border-radius:6px;" alt="${listing.displayName}" loading="lazy">`;
    }

    const tags = (listing.tags || []).map(tg =>
        `<span class="popup-badge" style="background:${landlord.color};opacity:0.7">${getTagLabel(tg)}</span>`
    ).join('');

    return `
        <div class="popup-content">
            ${imgHtml}
            <h3>${listing.displayName}</h3>
            <p><span class="popup-badge" style="background:${landlord.color}">${landlord.name}</span>${tags}</p>
            ${rooms ? `<p><strong>${t('Type')}:</strong> ${rooms}${listing.sqm ? ' &middot; ' + Math.round(listing.sqm) + ' ' + t('sqm') : ''}</p>` : ''}
            <p><strong>${t('Rent')}:</strong> ${price}</p>
            <p><strong>${t('Available from')}:</strong> ${avail}</p>
            ${listing.area ? `<p><strong>${t('Area')}:</strong> ${listing.area}</p>` : ''}
            ${listing.number ? `<p class="popup-id">${listing.number}</p>` : ''}
            <a href="${url}" target="_blank" rel="noopener" class="popup-link">
                ${t('View listing')} ↗
            </a>
            <a href="${getReportUrl(listing)}" target="_blank" rel="noopener" style="display:block;margin-top:3px;font-size:0.65rem;color:var(--text-secondary);text-decoration:none;" title="${t('Report wrong location')}">📍 ${t('Report')}</a>
        </div>`;
}

function addMarkers(listings) {
    markerCluster.clearLayers();
    allMarkers = [];
    markerLookup = {};

    listings.forEach(listing => {
        if (!listing.lat || !listing.lon) return;

        const icon = createMarkerIcon(listing);
        const marker = L.marker([listing.lat, listing.lon], { icon });

        marker.bindPopup(createPopupContent(listing), {
            maxWidth: 260,
            className: 'pb-popup',
            autoPanPaddingTopLeft: [10, 70],
        });

        marker.on('click', () => {
            highlightResultCard(listing.id);
            if (window.innerWidth < 768) {
                const size = map.getSize();
                const px = map.latLngToContainerPoint([listing.lat, listing.lon]);
                const targetY = size.y * 0.7;
                const targetX = size.x / 2;
                map.panBy([px.x - targetX, px.y - targetY], { animate: true, duration: 0.3 });
            }
        });

        markerCluster.addLayer(marker);
        allMarkers.push({ marker, listing });
        markerLookup[listing.id] = marker;
    });
}

function flyToSpot(spotId) {
    const entry = allMarkers.find(m => m.listing.id === spotId);
    if (!entry) return;
    const { marker } = entry;
    markerCluster.zoomToShowLayer(marker, () => {
        marker.openPopup();
    });
    if (window.innerWidth < 768) closeSidebar();
}

function highlightResultCard(spotId) {
    document.querySelectorAll('.result-card').forEach(card => card.classList.remove('active'));
    const card = document.querySelector(`.result-card[data-id="${spotId}"]`);
    if (card) {
        card.classList.add('active');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

let highlightedMarker = null;

function highlightMapMarker(spotId) {
    unhighlightMapMarker();
    const marker = markerLookup[spotId];
    if (!marker) return;
    highlightedMarker = marker;
    const el = marker.getElement();
    if (!el) return;
    const dot = el.querySelector('div');
    if (dot) {
        dot.style.transform = 'scale(1.6)';
        dot.style.boxShadow = '0 0 10px 3px rgba(26,26,46,0.5)';
        dot.style.zIndex = '1000';
    }
}

function unhighlightMapMarker() {
    if (highlightedMarker) {
        const el = highlightedMarker.getElement();
        if (el) {
            const dot = el.querySelector('div');
            if (dot) {
                dot.style.transform = '';
                dot.style.boxShadow = '0 1px 4px rgba(0,0,0,0.3)';
                dot.style.zIndex = '';
            }
        }
        highlightedMarker = null;
    }
}
