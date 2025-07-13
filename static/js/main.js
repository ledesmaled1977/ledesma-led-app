// static/js/main.js v2.0
document.addEventListener('DOMContentLoaded', () => {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar-nav a');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

    if (currentPath === '/') { // Si estamos en la raíz (dashboard)
        initDashboard();
    } else if (currentPath.includes('/crear_proforma') || currentPath.includes('/proforma/editar')) {
        initCrearProforma();
    } else if (currentPath.includes('/lista_proformas')) {
        initListaProformas();
    } else if (currentPath.includes('/clientes')) {
        initClientes();
    }
});

// REEMPLAZA LA FUNCIÓN initCrearProforma() EXISTENTE CON ESTA VERSIÓN COMPLETA
function initCrearProforma() {
    // --- VARIABLES Y CONSTANTES ---
    const proformaId = document.getElementById('proforma_id').value;
    const esModoEdicion = !!proformaId;
    
    let items = [];
    let editIndex = -1;

    const pageTitle = document.getElementById('page-title');
    const btnAgregar = document.getElementById('btn-agregar-producto');
    const btnGenerar = document.getElementById('btn-generar-cotizacion');
    const tablaItemsBody = document.getElementById('tabla-items');
    const totalProformaEl = document.getElementById('total-proforma');
    
    const itemInput = document.getElementById('item');
    const precioInput = document.getElementById('precio_unitario');
    const cantidadInput = document.getElementById('cantidad');
    const fechaInput = document.getElementById('fecha');
    const cotizacionNroInput = document.getElementById('cotizacion_nro');
    const clienteInput = document.getElementById('cliente');
    const suggestionsContainer = document.getElementById('cliente-suggestions');
    
    const cargarNumeroSugerido = async () => {
    try {
        const response = await fetch('/api/proformas/next_number');
        if (!response.ok) return;
        const data = await response.json();
        if (data.next_number) {
            cotizacionNroInput.value = data.next_number;
        }
    } catch (error) {
        console.error("No se pudo cargar el número de proforma sugerido:", error);
    }
    };
    // --- FUNCIONES ---

    const cargarDatosParaEdicion = async (id) => {
        try {
            const response = await fetch(`/api/proforma/${id}`);
            if (!response.ok) {
                throw new Error('No se pudo cargar la proforma para editar. Puede que no tenga permisos o la proforma no exista.');
            }

            const proforma = await response.json();
            
            // Llenar campos principales del formulario
            fechaInput.value = proforma.fecha;
            cotizacionNroInput.value = proforma.cotizacion_nro;
            clienteInput.value = proforma.cliente;
            
            // Cargar los items en nuestra variable local y renderizar la tabla
            items = proforma.items;
            renderizarTabla();
        } catch(error) {
            alert(error.message);
            // Si falla, redirigir a la lista para evitar confusiones
            window.location.href = "/lista_proformas";
        }
    };

    function renderizarTabla() {
        tablaItemsBody.innerHTML = '';
        let total = 0;
        if (items) {
            items.forEach((item, index) => {
                const costo = (item.cantidad || 0) * (item.precio_unitario || 0);
                total += costo;
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.item}</td>
                    <td>${item.cantidad}</td>
                    <td>S/ ${parseFloat(item.precio_unitario).toFixed(2)}</td>
                    <td>S/ ${costo.toFixed(2)}</td>
                    <td>
                        <button class="btn btn-primary btn-editar" data-index="${index}" style="padding:5px 10px; font-size:0.9em;">Editar</button>
                        <button class="btn btn-danger btn-eliminar" data-index="${index}" style="padding:5px 10px; font-size:0.9em;">Eliminar</button>
                    </td>
                `;
                tablaItemsBody.appendChild(row);
            });
        }
        totalProformaEl.textContent = `S/ ${total.toFixed(2)}`;
    }

    // --- EVENT LISTENERS (MANEJADORES DE EVENTOS) ---

    btnAgregar.addEventListener('click', () => {
        const newItem = {
            item: itemInput.value,
            precio_unitario: parseFloat(precioInput.value),
            cantidad: parseInt(cantidadInput.value)
        };

        if (!newItem.item || isNaN(newItem.precio_unitario) || isNaN(newItem.cantidad)) {
            alert('Por favor, complete todos los campos del producto.');
            return;
        }

        if (editIndex > -1) {
            items[editIndex] = newItem;
            editIndex = -1; // Salir del modo de edición de item
            btnAgregar.textContent = "Agregar Producto";
        } else {
            items.push(newItem);
        }
        
        renderizarTabla();
        itemInput.value = '';
        precioInput.value = '';
        cantidadInput.value = '';
        itemInput.focus(); // Poner el cursor de nuevo en el campo de item
    });

    tablaItemsBody.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-eliminar')) {
            const index = e.target.dataset.index;
            items.splice(index, 1);
            renderizarTabla();
        }
        if (e.target.classList.contains('btn-editar')) {
            const index = e.target.dataset.index;
            const item = items[index];
            itemInput.value = item.item;
            precioInput.value = item.precio_unitario;
            cantidadInput.value = item.cantidad;
            editIndex = index;
            btnAgregar.textContent = "Actualizar Producto";
        }
    });
    
    btnGenerar.addEventListener('click', async () => {
        const originalText = btnGenerar.textContent;
        btnGenerar.textContent = 'Guardando...';
        btnGenerar.disabled = true;

        const proformaData = {
            fecha: fechaInput.value,
            cotizacion_nro: cotizacionNroInput.value,
            cliente: clienteInput.value,
            incluye_igv: false, 
            items: items
        };

        let errores = [];
        if (!proformaData.fecha) errores.push("La fecha es obligatoria.");
        if (!proformaData.cotizacion_nro) errores.push("El número de cotización es obligatorio.");
        if (!proformaData.cliente) errores.push("El nombre del cliente es obligatorio.");
        if (items.length === 0) errores.push("Debe agregar al menos un producto a la proforma.");

        if (errores.length > 0) {
            // Mostramos todos los errores encontrados de una vez
            alert("Por favor, corrija los siguientes errores:\n\n- " + errores.join("\n- "));
            btnGenerar.textContent = originalText;
            btnGenerar.disabled = false;
            return;
        }

        try {
            const url = esModoEdicion ? `/api/proformas/${proformaId}` : '/api/proformas';
            const method = esModoEdicion ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(proformaData)
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'Error del servidor.');
            }

            window.location.href = `/exito?id=${result.proforma_id}`;

        } catch (error) {
            alert(`Ocurrió un error: ${error.message}`);
        } finally {
            btnGenerar.disabled = false;
            btnGenerar.textContent = originalText;
        }
    });
    
    // Lógica de autocompletado (sin cambios)
    clienteInput.addEventListener('input', async () => {
        const searchTerm = clienteInput.value;
        if (searchTerm.length < 2) {
            suggestionsContainer.innerHTML = '';
            suggestionsContainer.style.display = 'none';
            return;
        }
        const response = await fetch(`/api/clientes/search?term=${searchTerm}`);
        const suggestions = await response.json();
        suggestionsContainer.innerHTML = '';
        if (suggestions.length > 0) {
            suggestions.forEach(cliente => {
                const div = document.createElement('div');
                div.textContent = cliente.nombre;
                div.addEventListener('click', () => {
                    clienteInput.value = cliente.nombre;
                    suggestionsContainer.innerHTML = '';
                    suggestionsContainer.style.display = 'none';
                });
                suggestionsContainer.appendChild(div);
            });
            suggestionsContainer.style.display = 'block';
        } else {
            suggestionsContainer.style.display = 'none';
        }
    });

    document.addEventListener('click', (e) => {
        if (e.target !== clienteInput) {
            suggestionsContainer.style.display = 'none';
        }
    });
    
    // --- INICIALIZACIÓN DE LA PÁGINA ---
    if (esModoEdicion) {
        // MODO EDICIÓN: Cargamos los datos existentes.
        pageTitle.textContent = "Editando Proforma";
        btnGenerar.textContent = "Guardar Cambios";
        cargarDatosParaEdicion(proformaId);
    } else {
        // MODO CREACIÓN: Sugerimos el siguiente número de proforma.
        cargarNumeroSugerido();
    }
}

// REEMPLAZA LA FUNCIÓN initListaProformas() EXISTENTE CON ESTA VERSIÓN COMPLETA
function initListaProformas() {
    const tablaProformasBody = document.getElementById('tabla-proformas');
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const paginationControls = document.getElementById('pagination-controls');
    
    // Variables del Modal de Eliminación
    const modal = document.getElementById('deleteModal');
    const cancelDeleteBtn = document.getElementById('btn-cancel-delete');
    const confirmDeleteBtn = document.getElementById('btn-confirm-delete');
    const modalError = document.getElementById('modal-error');
    let proformaIdToDelete = null;

    // Variables para el estado de la página
    let currentPage = 1;
    let currentSearch = '';

    async function cargarProformas(page = 1, search = '') {
        try {
            const response = await fetch(`/api/proformas?page=${page}&search=${search}`);
            if (!response.ok) {
                throw new Error(`Error del servidor: ${response.status}`);
            }
            const data = await response.json();
            const proformas = data.proformas;
            
            tablaProformasBody.innerHTML = '';
            if (proformas.length === 0) {
                tablaProformasBody.innerHTML = `<tr><td colspan="6">No se encontraron proformas para los criterios de búsqueda.</td></tr>`;
            } else {
                proformas.forEach(p => {
                    const row = document.createElement('tr');
                    const itemsHtml = p.items.map(i => `<li>${i.item_descripcion} (x${i.cantidad})</li>`).join('');
                    row.innerHTML = `
                        <td>${p.fecha}</td>
                        <td>${p.cotizacion_nro}</td>
                        <td>${p.cliente}</td>
                        <td>${p.author}</td> <td>
                            <select class="status-select" data-id="${p.id}">
                                <option value="Enviada" ${p.status === 'Enviada' ? 'selected' : ''}>Enviada</option>
                                <option value="Aprobada" ${p.status === 'Aprobada' ? 'selected' : ''}>Aprobada</option>
                                <option value="Rechazada" ${p.status === 'Rechazada' ? 'selected' : ''}>Rechazada</option>
                            </select>
                        </td>
                        <td><ul>${itemsHtml}</ul></td>
                        <td>S/ ${parseFloat(p.monto_total).toFixed(2)}</td>
                        <td>
                            <a href="/proforma/editar/${p.id}" class="btn btn-primary" style="padding: 5px 10px; font-size: 0.9em;">Editar</a>
                            <a href="/proforma/duplicar/${p.id}" class="btn" style="background-color: #ffc107; color: black; padding: 5px 10px; font-size: 0.9em;">Duplicar</a>
                            <a href="/api/proforma/${p.id}/preview" target="_blank" class="btn btn-secondary" style="padding: 5px 10px; font-size: 0.9em;">Ver</a>
                            <a href="/api/proforma/${p.id}/pdf" class="btn btn-success" style="padding: 5px 10px; font-size: 0.9em;">Descargar</a>
                            <button class="btn btn-danger btn-eliminar-proforma" data-id="${p.id}" style="padding: 5px 10px; font-size: 0.9em;">Eliminar</button>
                        </td>
                    `;
                    tablaProformasBody.appendChild(row);
                });
            }
            renderizarPaginacion(data.pagination);
        } catch (error) {
            console.error("Error al cargar proformas:", error);
            tablaProformasBody.innerHTML = `<tr><td colspan="6" class="error-message">Error al cargar los datos. Revise la consola.</td></tr>`;
        }
    }

    function renderizarPaginacion(pagination) {
        paginationControls.innerHTML = '';
        if (pagination.total_pages <= 1) return;

        const prevButton = document.createElement('button');
        prevButton.textContent = 'Anterior';
        prevButton.className = 'btn btn-secondary';
        prevButton.disabled = pagination.page === 1;
        prevButton.addEventListener('click', () => {
            currentPage--;
            cargarProformas(currentPage, currentSearch);
        });

        const pageInfo = document.createElement('span');
        pageInfo.textContent = `Página ${pagination.page} de ${pagination.total_pages}`;

        const nextButton = document.createElement('button');
        nextButton.textContent = 'Siguiente';
        nextButton.className = 'btn btn-secondary';
        nextButton.disabled = pagination.page === pagination.total_pages;
        nextButton.addEventListener('click', () => {
            currentPage++;
            cargarProformas(currentPage, currentSearch);
        });

        paginationControls.appendChild(prevButton);
        paginationControls.appendChild(pageInfo);
        paginationControls.appendChild(nextButton);
    }

    searchButton.addEventListener('click', () => {
        currentPage = 1;
        currentSearch = searchInput.value;
        cargarProformas(currentPage, currentSearch);
    });

    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            searchButton.click();
        }
    });

    // --- LÓGICA COMPLETA DEL MODAL DE ELIMINACIÓN ---
    function openModal(id) {
        proformaIdToDelete = id;
        modal.style.display = 'flex';
    }

    function closeModal() {
        modal.style.display = 'none';
        modalError.style.display = 'none';
    }

    tablaProformasBody.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-eliminar-proforma')) {
            openModal(e.target.dataset.id);
        }
    });

    tablaProformasBody.addEventListener('change', async (e) => {
    if (e.target.classList.contains('status-select')) {
        const proformaId = e.target.dataset.id;
        const nuevoStatus = e.target.value;

        try {
            const response = await fetch(`/api/proformas/${proformaId}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: nuevoStatus })
            });
            if (!response.ok) {
                throw new Error('No se pudo actualizar el estado.');
            }
            // Opcional: podrías añadir una pequeña notificación de "Guardado"
            // Por ahora, no hace nada visual, pero el cambio se guarda.
        } catch (error) {
            console.error(error);
            alert('Error al actualizar el estado.');
            // Si falla, recargamos para mostrar el estado original
            cargarProformas(currentPage, currentSearch);
        }
    }
    });

    cancelDeleteBtn.onclick = closeModal;
    
    confirmDeleteBtn.addEventListener('click', async () => {
        modalError.style.display = 'none';
        try {
            const response = await fetch(`/api/proformas/${proformaIdToDelete}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                try {
                    const errorJson = JSON.parse(errorText);
                    throw new Error(errorJson.error || `Error del servidor: ${response.status}`);
                } catch (e) {
                     throw new Error(`Error del servidor (código: ${response.status}).`);
                }
            }

            const result = await response.json();
            if (result.success) {
                closeModal();
                cargarProformas(currentPage, currentSearch); // Recargar la página actual
            } else {
                throw new Error(result.error || 'El servidor indicó un fallo.');
            }
        } catch (error) {
            console.error('Error al eliminar proforma:', error);
            modalError.textContent = error.message;
            modalError.style.display = 'block';
        }
    });

    window.onclick = (event) => {
        if (event.target == modal) {
            closeModal();
        }
    };
    // --- FIN DE LA LÓGICA DEL MODAL ---

    // Carga inicial
    cargarProformas();
}

// --- NUEVA FUNCIÓN PARA GESTIÓN DE CLIENTES ---
function initClientes() {
    const form = document.getElementById('form-cliente');
    const formTitle = document.getElementById('form-title');
    const clienteIdInput = document.getElementById('cliente-id');
    const nombreInput = document.getElementById('nombre');
    const rucDniInput = document.getElementById('ruc_dni');
    const direccionInput = document.getElementById('direccion');
    const telefonoInput = document.getElementById('telefono');
    const emailInput = document.getElementById('email');
    const tablaClientes = document.getElementById('tabla-clientes');
    const btnCancel = document.getElementById('btn-cancel-edit');

    // Función para cargar y mostrar los clientes en la tabla
    const cargarClientes = async () => {
        try {
            const response = await fetch('/api/clientes');
            if (!response.ok) throw new Error('No se pudo cargar la lista de clientes.');

            const clientes = await response.json();
            tablaClientes.innerHTML = '';
            clientes.forEach(c => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${c.nombre}</td>
                    <td>${c.ruc_dni || ''}</td>
                    <td>${c.email || ''}<br>${c.telefono || ''}</td>
                    <td>
                        <button class="btn btn-primary btn-edit" data-id='${c.id}' style="padding: 5px 10px; font-size: 0.9em;">Editar</button>
                        <button class="btn btn-danger btn-delete" data-id='${c.id}' style="padding: 5px 10px; font-size: 0.9em;">Eliminar</button>
                    </td>
                `;
                // Añadir datos del cliente al botón de editar para fácil acceso
                row.querySelector('.btn-edit').dataset.cliente = JSON.stringify(c);
                tablaClientes.appendChild(row);
            });
        } catch(error) {
            console.error(error);
            tablaClientes.innerHTML = `<tr><td colspan="4" class="error-message">Error al cargar clientes.</td></tr>`;
        }
    };

    // Resetear el formulario a su estado inicial
    const resetForm = () => {
        formTitle.textContent = 'Añadir Nuevo Cliente';
        form.reset();
        clienteIdInput.value = '';
        btnCancel.style.display = 'none';
    };

    // Enviar el formulario (para crear o editar)
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const clienteId = clienteIdInput.value;
        const url = clienteId ? `/api/clientes/${clienteId}` : '/api/clientes';
        const method = clienteId ? 'PUT' : 'POST';

        const data = {
            nombre: nombreInput.value,
            ruc_dni: rucDniInput.value,
            direccion: direccionInput.value,
            telefono: telefonoInput.value,
            email: emailInput.value
        };

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            resetForm();
            cargarClientes();
        } else {
            alert('Error al guardar el cliente.');
        }
    });

    // Manejar clics en la tabla (para editar o eliminar)
    tablaClientes.addEventListener('click', async (e) => {
        // Botón de Editar
        if (e.target.classList.contains('btn-edit')) {
            const clienteData = JSON.parse(e.target.dataset.cliente);
            formTitle.textContent = 'Editando Cliente';
            clienteIdInput.value = clienteData.id;
            nombreInput.value = clienteData.nombre;
            rucDniInput.value = clienteData.ruc_dni || '';
            direccionInput.value = clienteData.direccion || '';
            telefonoInput.value = clienteData.telefono || '';
            emailInput.value = clienteData.email || '';
            btnCancel.style.display = 'inline-block';
            window.scrollTo(0, 0); // Subir al inicio de la página
        }

        // Botón de Eliminar
        if (e.target.classList.contains('btn-delete')) {
            if (!confirm('¿Está seguro de que desea eliminar este cliente?')) return;

            const clienteId = e.target.dataset.id;
            const response = await fetch(`/api/clientes/${clienteId}`, { method: 'DELETE' });

            if (response.ok) {
                resetForm();
                cargarClientes();
            } else {
                alert('Error al eliminar el cliente.');
            }
        }
    });

    // Botón de Cancelar Edición
    btnCancel.addEventListener('click', resetForm);

    // Carga inicial de clientes
    cargarClientes();
}

// --- NUEVA FUNCIÓN PARA EL GRÁFICO DEL DASHBOARD ---
function initDashboard() {
    const ctx = document.getElementById('proformasChart').getContext('2d');

    const renderChart = async () => {
        try {
            const response = await fetch('/api/dashboard_stats');
            const stats = await response.json();

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: stats.labels,
                    datasets: [{
                        label: '# de Proformas',
                        data: stats.data,
                        backgroundColor: 'rgba(13, 110, 253, 0.7)',
                        borderColor: 'rgba(13, 110, 253, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1 // Asegura que el eje Y vaya de 1 en 1
                            }
                        }
                    },
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        } catch (error) {
            console.error("Error al cargar datos del gráfico:", error);
        }
    };

    renderChart();
}