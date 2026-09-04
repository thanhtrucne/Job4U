/* websocket.js - realtime WebSocket client with reconnect + toast */
(function () {
    const WS_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'ws://localhost:8000/ws'
        : (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';

    let ws;
    let retryDelay = 2000;
    const MAX_RETRY = 30000;

    function showToast(title, body) {
        let toast = document.getElementById('ws-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'ws-toast';
            document.body.appendChild(toast);
        }
        toast.innerHTML = `<strong>${title}</strong>${body}`;
        toast.classList.add('show');
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => toast.classList.remove('show'), 5000);
    }

    function connect() {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            retryDelay = 2000;
            console.log('[WS] Connected');
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'new_job') {
                    const d = msg.data;
                    showToast('Việc làm mới!', `${d.title} - ${d.company || ''}`);
                    // If on home/jobs page, prepend card
                    const grid = document.getElementById('jobs-grid');
                    if (grid && typeof buildJobCardHTML === 'function') {
                        const card = document.createElement('div');
                        card.innerHTML = buildJobCardHTML(d);
                        grid.prepend(card.firstElementChild);
                    }
                } else if (msg.type === 'crawl_status') {
                    if (msg.status === 'started') showToast('Crawler', 'Bắt đầu thu thập dữ liệu...');
                    else if (msg.status === 'completed') showToast('Crawler', `Hoàn thành. +${msg.count} việc làm mới`);
                    else if (msg.status === 'error') showToast('Crawler', 'Lỗi trong quá trình thu thập');
                }
            } catch (e) { console.warn('[WS] parse error', e); }
        };

        ws.onclose = () => {
            console.log(`[WS] Closed. Retrying in ${retryDelay}ms`);
            setTimeout(() => { retryDelay = Math.min(retryDelay * 2, MAX_RETRY); connect(); }, retryDelay);
        };

        ws.onerror = (e) => console.warn('[WS] Error', e);
    }

    connect();
})();
