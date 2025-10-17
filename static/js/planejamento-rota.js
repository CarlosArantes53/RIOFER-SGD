// static/js/planejamento-rota.js

document.addEventListener('DOMContentLoaded', function () {
    // Inicialização do Mapa
    const map = L.map('map-render').setView([-14.235, -51.925], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    const markers = {};
    const selectedPedidos = new Map();

    locations.forEach(loc => {
        if (loc.Latitude && loc.Longitude) {
            const marker = L.marker([loc.Latitude, loc.Longitude]);
            marker.bindPopup(`<b>${loc.CardName}</b><br>Pedido: ${loc.AbsEntry}`);
            markers[loc.AbsEntry] = marker;
        }
    });

    // Elementos do DOM
    const sidebar = document.getElementById('sidebar');
    const footer = document.getElementById('planejamento-footer');
    const countPedidosEl = document.getElementById('count-pedidos');
    const totalPesoEl = document.getElementById('total-peso');
    const modal = document.getElementById('rota-modal');
    const btnCriarRota = document.getElementById('btn-criar-rota');
    const btnCancelarModal = document.getElementById('btn-cancelar-modal');
    const tipoRotaSelect = document.getElementById('tipo_rota');
    const camposRotaPendente = document.getElementById('campos-rota-pendente');
    const formCriarRota = document.getElementById('form-criar-rota');

    function updateFooter() {
        const count = selectedPedidos.size;
        let totalPeso = 0;
        selectedPedidos.forEach(pedido => totalPeso += pedido.peso);

        countPedidosEl.textContent = count;
        totalPesoEl.textContent = totalPeso.toFixed(2);

        if (count > 0) {
            footer.classList.add('visible');
        } else {
            footer.classList.remove('visible');
        }
    }
    
    function updateMapMarkers() {
        // Remove todos os marcadores
        Object.values(markers).forEach(marker => marker.remove());
        
        // Adiciona apenas os marcadores selecionados
        const visibleMarkers = [];
        selectedPedidos.forEach((pedido, absEntry) => {
            if (markers[absEntry]) {
                markers[absEntry].addTo(map);
                visibleMarkers.push(markers[absEntry]);
            }
        });
        
        if (visibleMarkers.length > 0) {
            const group = new L.featureGroup(visibleMarkers);
            map.fitBounds(group.getBounds().pad(0.1));
        } else if (locations.length > 0){
             map.setView([-14.235, -51.925], 4);
        }
    }


    sidebar.addEventListener('change', (e) => {
        if (e.target.classList.contains('pedido-checkbox')) {
            const item = e.target.closest('.pedido-item');
            const absEntry = item.dataset.absentry;

            if (e.target.checked) {
                selectedPedidos.set(absEntry, {
                    AbsEntry: absEntry,
                    CardName: item.dataset.cardname,
                    peso: parseFloat(item.dataset.peso)
                });
            } else {
                selectedPedidos.delete(absEntry);
            }
            updateFooter();
            updateMapMarkers();
        }
    });

    // Lógica do Modal
    btnCriarRota.addEventListener('click', () => {
        modal.style.display = 'block';
    });
    btnCancelarModal.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    tipoRotaSelect.addEventListener('change', () => {
        camposRotaPendente.style.display = tipoRotaSelect.value === 'Pendente' ? 'grid' : 'none';
    });

    // Submissão do Formulário
    formCriarRota.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(formCriarRota);
        const data = {
            pedidos: Array.from(selectedPedidos.values()),
            id_caminhao: formData.get('id_caminhao'),
            data_rota: formData.get('data_rota'),
            tipo: formData.get('tipo_rota'),
            meta_kg: formData.get('meta_kg'),
            data_limite: formData.get('data_limite'),
            observacoes: formData.get('observacoes')
        };

        try {
            const response = await fetch("{{ url_for('rotas.api_create_rota') }}", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.status === 'success') {
                // Redireciona para a página de gerenciamento, onde o flash message será exibido
                window.location.href = "{{ url_for('rotas.manage_rotas') }}";
            } else {
                alert('Erro: ' + result.message);
            }
        } catch (error) {
            console.error('Erro de conexão:', error);
            alert('Erro de conexão ao criar a rota.');
        }
    });
});