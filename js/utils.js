// utils.js — i18n, formatting, landlord styles

// === i18n ===
const LANG_KEY = 'pennybridge-lang';

const STRINGS = {
    'listings':        { sv: 'objekt', en: 'listings' },
    'Available now':   { sv: 'Lediga nu', en: 'Available now' },
    'Showing':         { sv: 'Visar', en: 'Showing' },
    'of':              { sv: 'av', en: 'of' },
    'All':             { sv: 'Alla', en: 'All' },
    'All landlords':   { sv: 'Alla värdar', en: 'All landlords' },
    'Landlord':        { sv: 'Värd', en: 'Landlord' },
    'Max price':       { sv: 'Maxpris', en: 'Max price' },
    'kr/month':        { sv: 'kr/mån', en: 'kr/mo' },
    'Available from':  { sv: 'Ledig från', en: 'Available from' },
    'Not available':   { sv: 'Ej tillgänglig', en: 'Not available' },
    'Rent':            { sv: 'Hyra', en: 'Rent' },
    'Loading':         { sv: 'Laddar data...', en: 'Loading data...' },
    'Load error':      { sv: 'Kunde inte ladda data.', en: 'Could not load data.' },
    'More':            { sv: 'till — använd filtren', en: 'more — use filters' },
    'No results':      { sv: 'Inga objekt matchar filtren.', en: 'No listings match the filters.' },
    'View listing':    { sv: 'Visa objekt', en: 'View listing' },
    'Filters':         { sv: 'Filter', en: 'Filters' },
    'sqm':             { sv: 'kvm', en: 'm²' },
    'ago':             { sv: 'sedan', en: 'ago' },
    'updated':         { sv: 'uppdaterad', en: 'updated' },
    'Rooms':           { sv: 'Rum', en: 'Rooms' },
    'Tags':            { sv: 'Taggar', en: 'Tags' },
    'student':         { sv: 'Student', en: 'Student' },
    'senior':          { sv: 'Senior', en: 'Senior' },
    'youth':           { sv: 'Ungdom', en: 'Youth' },
    'quick-pick':      { sv: 'Snabbval', en: 'Quick pick' },
    'Report wrong location': { sv: 'Rapportera fel plats', en: 'Report wrong location' },
    'Report':          { sv: 'Rapportera', en: 'Report' },
};

let currentLang = localStorage.getItem(LANG_KEY) || 'en';

function t(key) {
    const entry = STRINGS[key];
    if (!entry) return key;
    return entry[currentLang] || entry['sv'] || key;
}

function toggleLanguage() {
    currentLang = currentLang === 'sv' ? 'en' : 'sv';
    localStorage.setItem(LANG_KEY, currentLang);
    location.reload();
}

function getLang() { return currentLang; }

// === Formatting ===
function formatDate(dateStr) {
    if (!dateStr) return '—';
    // Skip free-text availability strings
    if (!/^\d{4}-\d{2}-\d{2}/.test(dateStr) && !/^\d{4}-\d{2}-\d{2}T/.test(dateStr)) return dateStr;
    const d = new Date(dateStr);
    const locale = currentLang === 'sv' ? 'sv-SE' : 'en-GB';
    return d.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatPrice(price) {
    if (price == null) return '—';
    return Math.round(price).toLocaleString('sv-SE') + ' ' + t('kr/month');
}

// === Landlord display names and colors ===
const LANDLORD_META = {
    'obo':       { name: 'Örebrobostäder', color: '#cf0035', short: 'ÖBO' },
    'ragnfast':  { name: 'Ragnfast', color: '#224b91', short: 'RAG' },
    'soderberg': { name: 'Söderberg', color: '#862633', short: 'SÖD' },
    'pgj':       { name: 'PG Jönsson', color: '#2e7d32', short: 'PGJ' },
    'husherren': { name: 'Husherren', color: '#e65100', short: 'HUS' },
    'behrn':     { name: 'Behrn', color: '#1b232d', short: 'BEH' },
    'egeryds':   { name: 'Egeryds', color: '#6a1b9a', short: 'EGY' },
    'heimstaden':{ name: 'Heimstaden', color: '#00558b', short: 'HEM' },
};

function getLandlordMeta(source) {
    return LANDLORD_META[source] || { name: source, color: '#95a5a6', short: '???' };
}

// === Rooms display ===
const ROOM_STYLES = {
    '1 rum och kök':   { label: { sv: '1:a', en: '1 room' } },
    '2 rum och kök':   { label: { sv: '2:a', en: '2 rooms' } },
    '3 rum och kök':   { label: { sv: '3:a', en: '3 rooms' } },
    '4 rum och kök':   { label: { sv: '4:a', en: '4 rooms' } },
    '5 rum och kök':   { label: { sv: '5:a', en: '5 rooms' } },
    '1 rum kokvrå':    { label: { sv: '1:a', en: '1 room' } },
    '2 rum kokvrå':    { label: { sv: '2:a', en: '2 rooms' } },
    '3 rum kokvrå':    { label: { sv: '3:a', en: '3 rooms' } },
};

function getRoomLabel(type) {
    const style = ROOM_STYLES[type];
    if (style) return style.label[currentLang] || style.label['sv'];
    // Try to match "N rum och kök" or "N rum kokvrå"
    const m = type.match(/^(\d+)\s*rum/);
    if (m) return m[1] + ':a';
    return type || '';
}

// === Tags ===
function getTagLabel(tag) {
    return t(tag);
}

// === Generate listing URL ===
function getListingUrl(listing) {
    if (listing.url && listing.url.startsWith('http')) return listing.url;
    return '#';
}

// === Thumbnail URL ===
function getThumbnailUrl(listing) {
    if (listing.imageBase && listing.image) {
        return listing.imageBase + '/v2/market/objects/' + listing.image + '/thumbnail?width=120&height=80';
    }
    if (listing.image && listing.image.startsWith('http')) {
        return listing.image;
    }
    return null;
}

// === Report wrong location ===
function getReportUrl(listing) {
    const title = encodeURIComponent(`Wrong location: ${listing.displayName}`);
    const body = encodeURIComponent(
        `**Listing:** ${listing.displayName}\n` +
        `**Landlord:** ${getLandlordMeta(listing.source).name}\n` +
        `**Current position:** ${listing.lat?.toFixed(6)}, ${listing.lon?.toFixed(6)}\n` +
        `**Address used for geocoding:** ${listing.geocodeQuery}\n\n` +
        `**Expected location:** (describe where it should be)\n\n` +
        `---\n_Reported via PennyBridge map_`
    );
    return `https://github.com/DouglasHalse/PennyBridge/issues/new?title=${title}&body=${body}&labels=location-report`;
}

async function submitLocationReport(listing, expected) {
    const payload = {
        ref: 'main',
        inputs: {
            listing: listing.displayName,
            landlord: getLandlordMeta(listing.source).name,
            current_lat: String(listing.lat?.toFixed(6) || ''),
            current_lon: String(listing.lon?.toFixed(6) || ''),
            geocode_query: listing.geocodeQuery || '',
            expected: expected
        }
    };
    try {
        const r = await fetch(
            'https://api.github.com/repos/DouglasHalse/PennyBridge/actions/workflows/report-location.yml/dispatches',
            { method: 'POST', headers: { 'Accept': 'application/vnd.github.v3+json' }, body: JSON.stringify(payload) }
        );
        return r.ok;
    } catch(e) {
        return false;
    }
}
