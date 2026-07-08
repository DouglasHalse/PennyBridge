<?php
/**
 * PennyBridge location report endpoint.
 * Receives POST from the map, creates a GitHub issue.
 *
 * Place this file at: https://douglashalse.com/api/report.php
 *
 * Before deploying, replace GITHUB_PAT_HERE with a GitHub fine-grained
 * personal access token that has 'Issues' read/write permission on
 * the DouglasHalse/PennyBridge repo.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'POST only']);
    exit;
}

// --- Spam protection ---

// 1. Honeypot: hidden field bots auto-fill, humans never see
if (!empty($_POST['website']) || !empty($_POST['url'])) {
    http_response_code(200); // pretend success so bots don't retry
    echo json_encode(['success' => true]);
    exit;
}

// 2. Rate limit: one submission per IP per 60 seconds
$rateFile = __DIR__ . '/report_ratelimit.json';
$ratelimit = file_exists($rateFile) ? json_decode(file_get_contents($rateFile), true) : [];
$ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$now = time();

// Clean up old entries
foreach ($ratelimit as $storedIp => $storedTime) {
    if ($now - $storedTime > 300) unset($ratelimit[$storedIp]);
}

if (isset($ratelimit[$ip]) && ($now - $ratelimit[$ip]) < 60) {
    http_response_code(429);
    echo json_encode(['error' => 'Too many requests, please wait']);
    exit;
}

$ratelimit[$ip] = $now;
file_put_contents($rateFile, json_encode($ratelimit));

// --- Process request ---

$input = json_decode(file_get_contents('php://input'), true);

$listing  = trim($input['listing'] ?? '');
$landlord = trim($input['landlord'] ?? '');
$lat      = trim($input['lat'] ?? '');
$lon      = trim($input['lon'] ?? '');
$query    = trim($input['query'] ?? '');
$expected = trim($input['expected'] ?? '');

// Basic validation
if (!$listing || !$expected) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing required fields']);
    exit;
}
if (strlen($expected) > 500) {
    http_response_code(400);
    echo json_encode(['error' => 'Expected location too long']);
    exit;
}

$title = "Wrong location: $listing";
$body  = "**Listing:** $listing\n";
$body .= "**Landlord:** $landlord\n";
$body .= "**Current position:** $lat, $lon\n";
$body .= "**Address used:** $query\n";
$body .= "**Expected:** $expected\n\n";
$body .= "---\n_Reported via PennyBridge map_";

$payload = json_encode([
    'title'  => $title,
    'body'   => $body,
    'labels' => ['location-report'],
]);

$token = 'GITHUB_PAT_HERE'; // <- replace with your token

$ch = curl_init('https://api.github.com/repos/DouglasHalse/PennyBridge/issues');
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $payload,
    CURLOPT_HTTPHEADER     => [
        'Authorization: Bearer ' . $token,
        'Accept: application/vnd.github.v3+json',
        'User-Agent: PennyBridge-Reporter',
        'Content-Type: application/json',
    ],
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 10,
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($httpCode === 201) {
    echo json_encode(['success' => true]);
} else {
    http_response_code(500);
    echo json_encode(['error' => 'GitHub API error', 'code' => $httpCode]);
}
