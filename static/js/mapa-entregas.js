// static/js/mapa-entregas.js

document.addEventListener('DOMContentLoaded', function () {
    const initialCoords = [-14.2350, -51.9253];
    const map = L.map('map-render').setView(initialCoords, 4);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://riofer.com.br/">Riofer Map</a>'
    }).addTo(map);

    const markers = {};

    locations.forEach(loc => {
        if (loc.Latitude && loc.Longitude) {
            const marker = L.marker([loc.Latitude, loc.Longitude]).addTo(map);
            const popupContent = `
                <b>${loc.CardName}</b><br>
                Pedido: ${loc.AbsEntry}<br>
                Status: ${loc.Status}<br>
                <a href="/picking/${loc.AbsEntry}?source=mapa" class="btn" style="margin-top: 8px;">Ver Detalhes</a>
            `;
            marker.bindPopup(popupContent);
            markers[loc.AbsEntry] = marker;
        }
    });

    let tempMarker = null;
    let mapClickHandler = null;

    async function fetchGeo(absEntry, statusElement) {
        statusElement.innerHTML = `<p class="status-text">Procurando geolocalização...</p>`;
        try {
            const response = await fetch(`/mapa/find_geolocation/${absEntry}`, {
                method: 'POST'
            });
            const result = await response.json();
            if (result.status === 'success') {
                statusElement.innerHTML = `<p style="color: #10b981;">Encontrada!</p>`;
                updateItemData(absEntry, result.lat, result.lon);
            } else if (result.status === 'not_found') {
                statusElement.innerHTML = `<p class="geo-error">Não encontrada.</p>`;
            } else {
                statusElement.innerHTML = `<p class="geo-error">Erro na busca.</p>`;
            }
        } catch (error) {
            statusElement.innerHTML = `<p class="geo-error">Erro de conexão.</p>`;
        }
    }

    function enableMapClickForEdit(container, latInput, lonInput) {
        if (mapClickHandler) map.off('click', mapClickHandler);

        mapClickHandler = function(e) {
            const { lat, lng } = e.latlng;

            if (!tempMarker) {
                tempMarker = L.marker([lat, lng], { draggable: true }).addTo(map);
                tempMarker.on('dragend', function(evt){
                    const p = evt.target.getLatLng();
                    latInput.value = p.lat.toFixed(6);
                    lonInput.value = p.lng.toFixed(6);
                });
            } else {
                tempMarker.setLatLng([lat, lng]);
            }

            latInput.value = lat.toFixed(6);
            lonInput.value = lng.toFixed(6);
        };

        map.on('click', mapClickHandler);
    }

    function disableMapClickForEdit() {
        if (mapClickHandler) {
            map.off('click', mapClickHandler);
            mapClickHandler = null;
        }
        if (tempMarker) {
            map.removeLayer(tempMarker);
            tempMarker = null;
        }
    }

    function openEditFor(container) {
        document.querySelectorAll('.pedido-item .edit-form').forEach(f => {
            f.style.display = 'none';
            f.setAttribute('aria-hidden', 'true');
        });
        disableMapClickForEdit();
        editingAbs = container.dataset.absentry;
        const form = container.querySelector('.edit-form');
        form.style.display = 'block';
        form.setAttribute('aria-hidden', 'false');

        const latInput = form.querySelector('input[placeholder="Latitude"]');
        const lonInput = form.querySelector('input[placeholder="Longitude"]');

        latInput.focus();
        latInput.select();

        form.querySelector('.btn-mark-map').addEventListener('click', function markHandler(e) {
            e.stopPropagation();
            enableMapClickForEdit(container, latInput, lonInput);
            this.textContent = 'Clique no mapa...';
            const self = this;
            const cancelMark = function() {
                disableMapClickForEdit();
                self.textContent = 'Marcar no mapa';
                self.removeEventListener('click', cancelMark);
                self.addEventListener('click', markHandler);
            };
            this.removeEventListener('click', markHandler);
            this.addEventListener('click', cancelMark);
        }, { once: false });

        const existingLat = container.dataset.lat;
        const existingLon = container.dataset.lon;
        if (existingLat && existingLon && existingLat !== 'None' && existingLon !== 'None') {
            if (tempMarker) {
                tempMarker.setLatLng([existingLat, existingLon]);
            } else {
                tempMarker = L.marker([existingLat, existingLon], { draggable: true }).addTo(map);
                tempMarker.on('dragend', function(evt){
                    const p = evt.target.getLatLng();
                    form.querySelector('input[placeholder="Latitude"]').value = p.lat.toFixed(6);
                    form.querySelector('input[placeholder="Longitude"]').value = p.lng.toFixed(6);
                });
            }
            map.flyTo([existingLat, existingLon], 16);
        }
    }

    function updateItemData(absEntry, lat, lon) {
        const itemElement = document.getElementById(`pedido-${absEntry}`);
        itemElement.dataset.lat = lat;
        itemElement.dataset.lon = lon;
        itemElement.querySelector('.geo-status').innerHTML = `<p style="color: #10b981;">Geolocalização OK.</p>`;
        if(markers[absEntry]) {
            markers[absEntry].setLatLng([lat, lon]);
        } else {
            const marker = L.marker([lat, lon]).addTo(map);
            marker.bindPopup(`<b>Pedido ${absEntry}</b>`);
            markers[absEntry] = marker;
        }
        map.flyTo([lat, lon], 15);
        if (tempMarker) {
            map.removeLayer(tempMarker);
            tempMarker = null;
            disableMapClickForEdit();
        }
    }

    if (locations.length > 0) {
        const group = new L.featureGroup(Object.values(markers));
        map.fitBounds(group.getBounds().pad(0.5));
    }

    document.getElementById('sidebar').addEventListener('click', async function(e) {
        const item = e.target.closest('.pedido-item');
        if (!item) return;

        const absEntry = item.dataset.absentry;

        if (e.target.closest('.btn-save-geo')) {
            e.stopPropagation();
            const latInput = item.querySelector('input[placeholder="Latitude"]');
            const lonInput = item.querySelector('input[placeholder="Longitude"]');

            const response = await fetch('/mapa/save_geolocation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ abs_entry: absEntry, lat: latInput.value, lon: lonInput.value })
            });
            const result = await response.json();
            if (result.status === 'success') {
                alert('Salvo com sucesso!');
                updateItemData(absEntry, latInput.value, lonInput.value);
                closeEditForm(item);
            } else {
                alert('Erro ao salvar: ' + result.message);
            }
            return;
        }

        if (e.target.closest('.btn-edit')) {
            e.stopPropagation();
            const form = item.querySelector('.edit-form');
            if (form.style.display === 'block') {
                closeEditForm(item);
            } else {
                openEditFor(item);
            }
            return;
        }

        if (e.target.closest('.btn-cancel-edit')) {
            e.stopPropagation();
            closeEditForm(item);
            return;
        }

        if (!e.target.closest('.edit-form')) {
            const lat = item.dataset.lat;
            const lon = item.dataset.lon;
            if (lat && lon && lat !== 'None' && lon !== 'None') {
                map.flyTo([lat, lon], 15);
                if (markers[absEntry]) {
                    markers[absEntry].openPopup();
                }
            }
        }
    });

    document.getElementById('find-all-btn').addEventListener('click', async function() {
        this.disabled = true;
        this.textContent = "Buscando...";
        const itemsToFind = document.querySelectorAll('.geo-error');
        for (const item of itemsToFind) {
            const container = item.closest('.pedido-item');
            const absEntry = container.dataset.absentry;
            await fetchGeo(absEntry, container.querySelector('.geo-status'));
        }
        this.disabled = false;
        this.textContent = "Buscar Geolocalizações Faltantes";
    });

    document.querySelectorAll('.btn-find-one').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const container = this.closest('.pedido-item');
            const absEntry = container.dataset.absentry;
            fetchGeo(absEntry, container.querySelector('.geo-status'));
            this.style.display = 'none';
        });
    });

    const toggleFs = document.getElementById('toggle-fullscreen');
    const mapContainer = document.getElementById('map-container');

    function updateFullscreenUI() {
        const isInFullscreen = document.fullscreenElement || document.mozFullScreenElement || document.webkitFullscreenElement || document.msFullscreenElement;

        mapContainer.classList.toggle('fullscreen', !!isInFullscreen);

        if (isInFullscreen) {
            toggleFs.innerHTML = '<i class="fas fa-compress"></i> Sair da Tela Cheia';
        } else {
            toggleFs.innerHTML = '<i class="fas fa-expand"></i> Tela Cheia';
        }

        setTimeout(() => {
            map.invalidateSize();
        }, 300);
    }

    toggleFs.addEventListener('click', function() {
        const isInFullscreen = document.fullscreenElement || document.mozFullScreenElement || document.webkitFullscreenElement || document.msFullscreenElement;

        if (!isInFullscreen) {
            const element = mapContainer;
            if (element.requestFullscreen) {
                element.requestFullscreen();
            } else if (element.mozRequestFullScreen) { // Firefox
                element.mozRequestFullScreen();
            } else if (element.webkitRequestFullscreen) { // Chrome, Safari e Opera
                element.webkitRequestFullscreen();
            } else if (element.msRequestFullscreen) { // IE/Edge
                element.msRequestFullscreen();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.mozCancelFullScreen) { // Firefox
                document.mozCancelFullScreen();
            } else if (document.webkitExitFullscreen) { // Chrome, Safari e Opera
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) { // IE/Edge
                document.msExitFullscreen();
            }
        }
    });

    document.addEventListener('fullscreenchange', updateFullscreenUI);
    document.addEventListener('webkitfullscreenchange', updateFullscreenUI);
    document.addEventListener('mozfullscreenchange', updateFullscreenUI);
    document.addEventListener('MSFullscreenChange', updateFullscreenUI);

    const filterContainer = document.getElementById('filter-container');
    const filterToggle = document.getElementById('filter-toggle');
    const filterTypeLabel = document.getElementById('filter-type-label');

    function createFilterButton(name, type) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'filter-btn';
        btn.textContent = name;
        btn.setAttribute('data-filter', name);
        btn.setAttribute('data-type', type);
        btn.setAttribute('aria-pressed', 'false');
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            btn.classList.toggle('active');
            const pressed = btn.classList.contains('active');
            btn.setAttribute('aria-pressed', pressed ? 'true' : 'false');
            setVisibilityFromButtons();
        });
        return btn;
    }

    function populateFilters() {
        filterContainer.innerHTML = '';
        const isRegion = filterToggle.checked;
        filterTypeLabel.textContent = isRegion ? 'Regiões' : 'Cidades';
        const items = isRegion ? regioes : cities.map(c => ({ Nome: c }));
        const type = isRegion ? 'regiao' : 'cidade';

        items.forEach(item => {
            const btn = createFilterButton(item.Nome, type);
            filterContainer.appendChild(btn);
        });
    }

    filterToggle.addEventListener('change', populateFilters);

    document.getElementById('select-all-filters').addEventListener('click', () => {
        filterContainer.querySelectorAll('.filter-btn').forEach(b => {
            b.classList.add('active');
            b.setAttribute('aria-pressed', 'true');
        });
        setVisibilityFromButtons();
    });

    document.getElementById('clear-filters').addEventListener('click', () => {
        filterContainer.querySelectorAll('.filter-btn').forEach(b => {
            b.classList.remove('active');
            b.setAttribute('aria-pressed', 'false');
        });
        setVisibilityFromButtons();
    });

    function setVisibilityFromButtons() {
        const activeFilters = Array.from(filterContainer.querySelectorAll('.filter-btn.active')).map(b => b.dataset.filter);
        const isRegion = filterToggle.checked;

        document.querySelectorAll('.pedido-item').forEach(item => {
            const city = item.dataset.city || '';
            const abs = item.dataset.absentry;
            let show = activeFilters.length === 0;

            if (!show) {
                if (isRegion) {
                    show = activeFilters.some(regiaoNome => {
                        const regiao = regioes.find(r => r.Nome === regiaoNome);
                        return regiao && regiao.Cidades.includes(city);
                    });
                } else {
                    show = activeFilters.includes(city);
                }
            }

            item.style.display = show ? '' : 'none';
            if (markers[abs]) {
                if (show) markers[abs].addTo(map);
                else if (map.hasLayer(markers[abs])) map.removeLayer(markers[abs]);
            }
        });

        const visibleMarkers = Object.keys(markers)
            .filter(abs => {
                const el = document.getElementById(`pedido-${abs}`);
                return el && el.style.display !== 'none' && map.hasLayer(markers[abs]) === true;
            })
            .map(abs => markers[abs]);

        if (visibleMarkers.length > 0) {
            const group = new L.featureGroup(visibleMarkers);
            map.fitBounds(group.getBounds().pad(0.5));
        }
    }

    function closeEditForm(item) {
        const form = item.querySelector('.edit-form');
        form.style.display = 'none';
        form.setAttribute('aria-hidden', 'true');
        disableMapClickForEdit();
    }

    // Tabs
    window.openTab = function(evt, tabName) {
        const tabcontent = document.getElementsByClassName("tab-content");
        for (let i = 0; i < tabcontent.length; i++) {
            tabcontent[i].classList.remove('active');
        }
        const tablinks = document.getElementsByClassName("tab-link");
        for (let i = 0; i < tablinks.length; i++) {
            tablinks[i].classList.remove('active');
        }
        document.getElementById(tabName).classList.add('active');
        evt.currentTarget.classList.add('active');
        if (tabName === 'mapa') {
            map.invalidateSize();
        }
    }

    // Regiões Logic
    const regioesList = document.getElementById('regioes-list');
    const addRegiaoBtn = document.getElementById('add-regiao-btn');
    const regiaoNomeInput = document.getElementById('regiao-nome');
    const cidadesToggleContainer = document.getElementById('cidades-toggle-container');

    cidadesToggleContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('city-toggle-btn')) {
            e.target.classList.toggle('active');
        }
    });

    function renderRegioes() {
        regioesList.innerHTML = '';
        regioes.forEach(regiao => {
            const div = document.createElement('div');
            div.className = 'regiao-item';
            div.innerHTML = `
                <h4>${regiao.Nome}</h4>
                <p>${regiao.Cidades.join(', ')}</p>
                <button class="btn btn-danger btn-sm remove-regiao-btn">Remover</button>
            `;
            div.querySelector('.remove-regiao-btn').addEventListener('click', () => {
                regioes = regioes.filter(r => r.Nome !== regiao.Nome);
                renderRegioes();
            });
            regioesList.appendChild(div);
        });
    }

    addRegiaoBtn.addEventListener('click', () => {
        const nome = regiaoNomeInput.value.trim();
        if (!nome) {
            alert('Por favor, dê um nome para a região.');
            return;
        }
        if (regioes.some(r => r.Nome.toLowerCase() === nome.toLowerCase())) {
            alert('Uma região com este nome já existe.');
            return;
        }

        const selectedCidades = Array.from(cidadesToggleContainer.querySelectorAll('.city-toggle-btn.active'))
            .map(btn => btn.dataset.city);

        if (selectedCidades.length === 0) {
            alert('Selecione pelo menos uma cidade para a região.');
            return;
        }

        regioes.push({ Nome: nome, Cidades: selectedCidades });
        renderRegioes();

        // Reset form
        regiaoNomeInput.value = '';
        cidadesToggleContainer.querySelectorAll('.city-toggle-btn.active').forEach(btn => btn.classList.remove('active'));
    });
    
    document.getElementById('save-regioes-btn').addEventListener('click', async () => {
        const response = await fetch('/mapa/save_regioes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ regioes: regioes })
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert('Regiões salvas com sucesso!');
            populateFilters();
        } else {
            alert('Erro ao salvar as regiões: ' + result.message);
        }
    });


    // Initial setup
    populateFilters();
    setVisibilityFromButtons();
    renderRegioes();
});