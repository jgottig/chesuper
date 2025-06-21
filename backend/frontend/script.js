// frontend/script.js (Versión Final Completa con todas las mejoras)

document.addEventListener('DOMContentLoaded', () => {
    // --- ESTADO DE LA APLICACIÓN ---
    const API_URL = 'http://127.0.0.1:8000';
    let carrito = [];
    let currentCategory = null;
    let lastComparisonResults = null;

    // --- ELEMENTOS DEL DOM ---
    const pageContent = document.getElementById('page-content');
    const searchInput = document.getElementById('search-input');
    const availabilityCheckbox = document.getElementById('availability-checkbox');
    const productCounterContainer = document.getElementById('product-counter-container');
    const cartItemsContainer = document.getElementById('cart-items-container');
    const cartSummaryContainer = document.getElementById('cart-summary-container');
    const compareButton = document.getElementById('compare-button');
    const uploadButton = document.getElementById('upload-list-button');
    const downloadButton = document.getElementById('download-list-button');
    const fileInput = document.getElementById('file-input');
    const clearCartButton = document.getElementById('clear-cart-button');

    // --- FUNCIONES DE AYUDA ---
    function getLogoForSupermercado(bandera) {
        const nombreNormalizado = bandera.toLowerCase().replace(/\s+/g, '');
        if (nombreNormalizado.includes('carrefour')) return 'img/carrefour.png';
        if (nombreNormalizado.includes('coto')) return 'img/coto.jpg';
        if (nombreNormalizado.includes('gallega')) return 'img/la_gallega.png';
        if (nombreNormalizado.includes('jumbo')) return 'img/jumbo.png';
        if (nombreNormalizado.includes('libertad')) return 'img/libertad.png';
        return 'img/default.png';
    }

    // --- FUNCIONES DE RENDERIZADO ---
    function renderCategorias(categorias) {
        pageContent.innerHTML = `<h3 class="page-title">Categorías</h3><div id="categorias-grid"></div>`;
        const grid = document.getElementById('categorias-grid');
        categorias.forEach(cat => {
            const card = document.createElement('div');
            card.className = 'category-card';
            card.textContent = cat;
            card.dataset.categoria = cat;
            grid.appendChild(card);
        });
    }

    function renderProductos(data, categoria) {
        productCounterContainer.textContent = `TOTAL DE PRODUCTOS: ${data.total_productos_disponibles}`;
        let title = categoria || (searchInput.value ? `Resultados para "${searchInput.value}"` : "Todos los productos");
        pageContent.innerHTML = `<h3 class="page-title"><button class="back-button">←</button>${title}</h3><div id="productos-list"></div>`;
        const list = document.getElementById('productos-list');
        if (data.productos.length === 0) {
            list.innerHTML = "<p>No se encontraron productos con los filtros actuales.</p>";
            return;
        }
        appendProductos(data.productos);
    }
    
    function appendProductos(productos) {
        const list = document.getElementById('productos-list');
        productos.forEach(p => {
            const item = document.createElement('div');
            item.className = 'product-item';
            const itemInCart = carrito.find(c => c.ean === p.ean);
            const quantity = itemInCart ? itemInCart.quantity : 0;
            item.innerHTML = `
                <img src="${p.imagen_url}" alt="${p.nombre}" onerror="this.src='data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='">
                <div class="product-info"><h4>${p.nombre}</h4><p>${p.marca}</p></div>
                <div class="product-controls" data-ean="${p.ean}" data-nombre="${p.nombre}" data-marca="${p.marca}">
                    <button class="quantity-control-btn minus" ${quantity === 0 ? 'style="visibility: hidden;"' : ''}>-</button>
                    <span class="quantity-display" ${quantity === 0 ? 'style="visibility: hidden;"' : ''}>${quantity}</span>
                    <button class="quantity-control-btn plus">+</button>
                </div>
            `;
            list.appendChild(item);
        });
    }

    function renderCarrito() {
        if (carrito.length === 0) {
            cartItemsContainer.innerHTML = '<p style="text-align: center; color: #606770;">Tu carrito está vacío</p>';
            cartSummaryContainer.style.display = 'none';
            compareButton.disabled = true;
            return;
        }
        
        const totalProductos = carrito.length;
        const totalUnidades = carrito.reduce((sum, item) => sum + item.quantity, 0);

        cartSummaryContainer.style.display = 'block';
        cartSummaryContainer.innerHTML = `
            <div class="cart-summary-item">
                <span>Total de Productos:</span>
                <span>${totalProductos}</span>
            </div>
            <div class="cart-summary-item">
                <span>Total de Unidades:</span>
                <span>${totalUnidades}</span>
            </div>
        `;

        cartItemsContainer.innerHTML = '';
        compareButton.disabled = false;
        
        carrito.forEach(item => {
            const div = document.createElement('div');
            div.className = 'cart-item';
            div.innerHTML = `
                <div class="product-controls"><span style="font-size:1.2rem; font-weight:500;">${item.quantity} x</span></div>
                <div class="cart-item-info"><h5>${item.nombre}</h5><p>${item.marca}</p></div>
                <div class="cart-item-actions">
                    <button class="cart-item-remove-btn" data-ean="${item.ean}" title="Eliminar producto">
                        <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"></path></svg>
                    </button>
                </div>
            `;
            cartItemsContainer.appendChild(div);
        });
    }

    function renderResultados(data, optimizacionData) {
        lastComparisonResults = { ...data, optimizacion: optimizacionData };
        if (!data.comparativa || data.comparativa.length === 0) {
            pageContent.innerHTML = '<h2>No se encontraron precios para tu carrito.</h2>';
            return;
        }
        
        const mejorOpcion = data.comparativa[0];
        let html = `
            <h3 class="page-title"><button class="back-button">←</button>Resultados de la Comparación</h3>
            <div class="resultados-options"><input type="checkbox" id="promo-results-checkbox" ${data.promo_inicial_activada ? 'checked' : ''}><label for="promo-results-checkbox">Incluir promociones</label></div>
            <div id="resultados-grid">`;
        data.comparativa.forEach((res, index) => {
            const logoUrl = getLogoForSupermercado(res.bandera);
            html += `
                <div class="resultado-card ${index === 0 ? 'mejor-opcion' : ''}" data-bandera="${res.bandera}">
                    <div class="card-logo-container" data-target="detalle-${index}">
                        <img src="${logoUrl}" alt="${res.bandera}" class="resultado-card-logo">
                        <div class="resultado-total" id="total-${res.bandera.replace(/\s+/g, '')}">$${res.total_inicial.toLocaleString('es-AR')}</div>
                        <p class="resultado-items-count">${res.items_encontrados} de ${res.items_encontrados + res.items_faltantes} items</p>
                        <button class="card-share-button" data-bandera="${res.bandera}" title="Compartir esta lista">
                            <svg viewBox="0 0 24 24"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3s3-1.34 3-3-1.34-3-3-3z"></path></svg>
                        </button>
                    </div>
                    <div class="detalle-productos" id="detalle-${index}">`;
            res.detalle.forEach(item => {
                const precioUsado = (data.promo_inicial_activada && item.precio_promo_a != null) ? item.precio_promo_a : item.precio_lista;
                html += `<div class="detalle-item" data-ean="${item.ean}"><span class="detalle-item-nombre">${item.nombre} (x${item.quantity})</span><span class="detalle-item-precio">$${(precioUsado * item.quantity).toLocaleString('es-AR')}</span></div>`;
            });
            res.no_encontrados.forEach(item => {
                html += `<div class="detalle-item detalle-item-faltante"><span>❌</span><span class="detalle-item-nombre">${item.nombre}</span></div>`;
            });
            html += `</div></div>`;
        });
        html += `</div>`;

        if (optimizacionData && optimizacionData.canastas && optimizacionData.canastas.length > 0) {
            const totalItemsEncontradosOptimizacion = optimizacionData.canastas.reduce((sum, canasta) => sum + canasta.detalle.length, 0);
            const totalItemsCarrito = carrito.length;
            const nombresCanastas = optimizacionData.canastas.map(c => c.bandera).join(' + ');

            html += `
                <div id="optimization-row">
                    <div class="optimization-header">
                        <div class="optimization-title">
                            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93s3.05-7.44 7-7.93v15.86zm2-15.86c1.03.13 2 .45 2.87.93L12.93 10H11V4.07zM11 14h1.93l3.94 3.94c-.87.48-1.84.8-2.87.93V14zm4.25-2H11v-2h3.93l.32-.32c.1-.25.15-.52.15-.8a1.5 1.5 0 00-1.5-1.5H11V6.07c2.03.35 3.71 1.5 4.59 3.12-.42.2-.81.46-1.16.78l-.18.15z"></path></svg>
                            <div>
                                <h4>Compra Optimizada (${nombresCanastas})</h4>
                                <p class="resultado-items-count">${totalItemsEncontradosOptimizacion} de ${totalItemsCarrito} items</p>
                            </div>
                        </div>
                        <span class="optimization-total" id="optimization-grand-total">$${optimizacionData.total_optimizado.toLocaleString('es-AR')}</span>
                    </div>
                    <div class="optimization-details">`;
            optimizacionData.canastas.forEach((canasta, basketIndex) => {
                const logoUrl = getLogoForSupermercado(canasta.bandera);
                html += `<div class="optimization-basket" data-basket-index="${basketIndex}">
                            <div class="optimization-basket-header" id="basket-header-${basketIndex}">
                                <img src="${logoUrl}" alt="${canasta.bandera}">
                                <span>Comprar en ${canasta.bandera} ($${canasta.total_canasta.toLocaleString('es-AR')}):</span>
                            </div>`;
                canasta.detalle.forEach(item => {
                    const precioUsado = (data.promo_inicial_activada && item.precio_promo_a != null) ? item.precio_promo_a : item.precio_lista;
                    html += `<div class="detalle-item" data-ean="${item.ean}"><span class="detalle-item-nombre">${item.nombre} (x${item.quantity})</span><span class="detalle-item-precio">$${(precioUsado * item.quantity).toLocaleString('es-AR')}</span></div>`;
                });
                html += `</div>`;
            });
            html += `</div></div>`;
        }
        pageContent.innerHTML = html;
    }
    
    function recalcularTotales(usePromos) {
        if (!lastComparisonResults) return;
        
        let resultadosSimplesRecalculados = [];
        lastComparisonResults.comparativa.forEach((supermercado, index) => {
            let nuevoTotal = 0;
            supermercado.detalle.forEach(item => {
                let precioUnitario = item.precio_lista;
                if (usePromos && item.precio_promo_a != null) {
                    precioUnitario = item.precio_promo_a;
                }
                const costoTotalItem = precioUnitario * item.quantity;
                nuevoTotal += costoTotalItem;
                const detalleItemPrecio = document.querySelector(`#detalle-${index} .detalle-item[data-ean="${item.ean}"] .detalle-item-precio`);
                if (detalleItemPrecio) detalleItemPrecio.textContent = `$${costoTotalItem.toLocaleString('es-AR')}`;
            });
            const totalElement = document.getElementById(`total-${supermercado.bandera.replace(/\s+/g, '')}`);
            if (totalElement) totalElement.textContent = `$${nuevoTotal.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            resultadosSimplesRecalculados.push({ ...supermercado, total: nuevoTotal });
        });
        resultadosSimplesRecalculados.sort((a, b) => a.total - b.total);
        const grid = document.getElementById('resultados-grid');
        if (grid) {
            resultadosSimplesRecalculados.forEach((res, index) => {
                const card = grid.querySelector(`.resultado-card[data-bandera="${res.bandera}"]`);
                if (card) {
                    card.style.order = index;
                    card.classList.toggle('mejor-opcion', index === 0);
                }
            });
        }
        
        if (lastComparisonResults.optimizacion && lastComparisonResults.optimizacion.canastas) {
            let nuevoTotalOptimizado = 0;
            lastComparisonResults.optimizacion.canastas.forEach((canasta, basketIndex) => {
                let nuevoTotalCanasta = 0;
                const basketDiv = document.querySelector(`.optimization-basket[data-basket-index="${basketIndex}"]`);
                
                canasta.detalle.forEach(item => {
                    let precioUnitario = item.precio_lista;
                    if (usePromos && item.precio_promo_a != null) {
                        precioUnitario = item.precio_promo_a;
                    }
                    const costoTotalItem = precioUnitario * item.quantity;
                    nuevoTotalCanasta += costoTotalItem;
                    
                    if (basketDiv) {
                        const detalleItemPrecio = basketDiv.querySelector(`.detalle-item[data-ean="${item.ean}"] .detalle-item-precio`);
                        if (detalleItemPrecio) detalleItemPrecio.textContent = `$${costoTotalItem.toLocaleString('es-AR')}`;
                    }
                });
                
                const basketHeader = document.getElementById(`basket-header-${basketIndex}`);
                if (basketHeader) basketHeader.querySelector('span').textContent = `Comprar en ${canasta.bandera} ($${nuevoTotalCanasta.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}):`;
                nuevoTotalOptimizado += nuevoTotalCanasta;
            });

            const grandTotalElement = document.getElementById('optimization-grand-total');
            if (grandTotalElement) grandTotalElement.textContent = `$${nuevoTotalOptimizado.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
    }

    async function fetchData(isNewSearch = true) {
        if (isNewSearch) pageContent.innerHTML = '<p style="text-align:center; padding: 2rem;">Buscando productos...</p>';
        const query = searchInput.value;
        const useAvailabilityFilter = availabilityCheckbox.checked;
        const minSupermercados = useAvailabilityFilter ? 3 : 1;
        const url = new URL(`${API_URL}/api/productos`);
        url.searchParams.append('page', '1');
        if (query) url.searchParams.append('q', query);
        if (currentCategory) url.searchParams.append('categoria', currentCategory);
        url.searchParams.append('min_supermercados', minSupermercados);
        try {
            const response = await fetch(url);
            const data = await response.json();
            if (isNewSearch) renderProductos(data, currentCategory);
        } catch(error) {
            pageContent.innerHTML = '<p>Error al cargar los productos.</p>';
        }
    }

    async function showCategoriasView() {
        currentCategory = null;
        searchInput.value = '';
        const useAvailabilityFilter = availabilityCheckbox.checked;
        const minSupermercados = useAvailabilityFilter ? 3 : 1;
        const url = new URL(`${API_URL}/api/productos`);
        url.searchParams.append('min_supermercados', minSupermercados);
        url.searchParams.append('limit', '1');
        try {
            const countResponse = await fetch(url);
            const countData = await countResponse.json();
            productCounterContainer.textContent = `TOTAL DE PRODUCTOS: ${countData.total_productos_disponibles}`;
            const response = await fetch(`${API_URL}/api/categorias`);
            renderCategorias(await response.json());
        } catch(error) {
            productCounterContainer.textContent = "Error al conectar.";
            pageContent.innerHTML = "<p>No se pudieron cargar las categorías.</p>";
        }
    }

    async function showProductosView(categoria) {
        currentCategory = categoria;
        searchInput.value = '';
        fetchData(true);
    }

    function updateProductQuantity(ean, nombre, marca, change) {
        let itemInCart = carrito.find(c => c.ean === ean);
        if (itemInCart) {
            itemInCart.quantity += change;
            if (itemInCart.quantity <= 0) carrito = carrito.filter(c => c.ean !== ean);
        } else if (change > 0) {
            carrito.push({ ean, nombre, marca, quantity: 1 });
        }
        renderCarrito();
        if (document.getElementById('productos-list')) {
            const productControls = document.querySelector(`.product-controls[data-ean="${ean}"]`);
            if (productControls) {
                const quantityDisplay = productControls.querySelector('.quantity-display');
                const minusButton = productControls.querySelector('.minus');
                const updatedItem = carrito.find(c => c.ean === ean);
                if (updatedItem) {
                    quantityDisplay.textContent = updatedItem.quantity;
                    quantityDisplay.style.visibility = 'visible';
                    minusButton.style.visibility = 'visible';
                } else {
                    quantityDisplay.textContent = 0;
                    quantityDisplay.style.visibility = 'hidden';
                    minusButton.style.visibility = 'hidden';
                }
            }
        }
    }

    // --- MANEJO DE EVENTOS ---
    pageContent.addEventListener('click', async e => {
        const categoryCard = e.target.closest('.category-card');
        const backButton = e.target.closest('.back-button');
        const quantityBtn = e.target.closest('.quantity-control-btn');
        const cardContainer = e.target.closest('.card-logo-container');
        const optimizationHeader = e.target.closest('.optimization-header');
        const shareButton = e.target.closest('.card-share-button');

        if (categoryCard) showProductosView(categoryCard.dataset.categoria);
        if (backButton) showCategoriasView();
        if (quantityBtn) {
            const controls = quantityBtn.closest('.product-controls');
            const { ean, nombre, marca } = controls.dataset;
            const change = quantityBtn.classList.contains('plus') ? 1 : -1;
            updateProductQuantity(ean, nombre, marca, change);
        }
        if (cardContainer) {
            const targetId = cardContainer.dataset.target;
            const detalle = document.getElementById(targetId);
            document.querySelectorAll('.detalle-productos.visible').forEach(d => {
                if (d.id !== targetId) d.classList.remove('visible');
            });
            detalle.classList.toggle('visible');
        }
        if (optimizationHeader) {
            const details = optimizationHeader.nextElementSibling;
            details.classList.toggle('visible');
        }
        if (e.target.matches('#promo-results-checkbox')) {
            recalcularTotales(e.target.checked);
        }
        if (shareButton) {
            e.stopPropagation();
            const bandera = shareButton.dataset.bandera;
            const usePromos = document.getElementById('promo-results-checkbox')?.checked || false;
            const supermercadoData = lastComparisonResults.comparativa.find(s => s.bandera === bandera);
            if (!supermercadoData) return;
            let textoCompartir = `¡Che! Te paso la lista para comprar en ${bandera}:\n\n`;
            let totalRecalculado = 0;
            supermercadoData.detalle.forEach(item => {
                let precioUnitario = item.precio_lista;
                if (usePromos && item.precio_promo_a != null) {
                    precioUnitario = item.precio_promo_a;
                }
                totalRecalculado += precioUnitario * item.quantity;
                textoCompartir += `• ${item.nombre} (x${item.quantity})\n`;
            });
            supermercadoData.no_encontrados.forEach(item => {
                textoCompartir += `• ${item.nombre} (NO DISPONIBLE)\n`;
            });
            textoCompartir += `\nTotal estimado: $${totalRecalculado.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            textoCompartir += `\n\nComparado con Che Súper!`;
            if (navigator.share) {
                try {
                    await navigator.share({ title: `Lista de compras para ${bandera}`, text: textoCompartir });
                } catch (error) { console.error('Error al compartir:', error); }
            } else {
                navigator.clipboard.writeText(textoCompartir);
                alert("La lista se ha copiado al portapapeles.");
            }
        }
    });

    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentCategory = null;
            fetchData(true);
        }, 400); 
    });

    availabilityCheckbox.addEventListener('change', () => {
        if (currentCategory || searchInput.value.trim() !== '') {
            fetchData(true);
        } else {
            showCategoriasView();
        }
    });

    cartItemsContainer.addEventListener('click', e => {
        const removeButton = e.target.closest('.cart-item-remove-btn');
        if (removeButton) {
            const eanToRemove = removeButton.dataset.ean;
            carrito = carrito.filter(item => item.ean !== eanToRemove);
            renderCarrito();
            if (document.getElementById('productos-list')) {
                const productControls = document.querySelector(`.product-controls[data-ean="${eanToRemove}"]`);
                if (productControls) {
                    const quantityDisplay = productControls.querySelector('.quantity-display');
                    const minusButton = productControls.querySelector('.minus');
                    quantityDisplay.textContent = 0;
                    quantityDisplay.style.visibility = 'hidden';
                    minusButton.style.visibility = 'hidden';
                }
            }
        }
    });
    
    compareButton.addEventListener('click', async () => {
        const promoCheckbox = document.getElementById('promo-results-checkbox');
        const usePromos = promoCheckbox ? promoCheckbox.checked : false;
        const body = { items: carrito.map(({ ean, quantity }) => ({ ean, quantity })), use_promos: usePromos };
        
        compareButton.textContent = 'Calculando...';
        compareButton.disabled = true;
        try {
            const [compareResponse, optimizeResponse] = await Promise.all([
                fetch(`${API_URL}/api/comparar`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
                fetch(`${API_URL}/api/optimizar`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
            ]);
            const compareData = await compareResponse.json();
            const optimizeData = await optimizeResponse.json();
            renderResultados(compareData, optimizeData);
        } catch (error) {
            pageContent.innerHTML = '<h2>Error al conectar con el servidor.</h2>';
            console.error("Error al comparar:", error);
        } finally {
            compareButton.textContent = 'COMPARAR';
        }
    });

    clearCartButton.addEventListener('click', () => {
        if (carrito.length > 0 && confirm("¿Estás seguro de que quieres vaciar el carrito?")) {
            carrito = [];
            renderCarrito();
            if (document.getElementById('productos-list')) {
                document.querySelectorAll('.quantity-display, .minus').forEach(el => {
                    el.textContent = '0';
                    el.style.visibility = 'hidden';
                });
            }
        }
    });

    downloadButton.addEventListener('click', () => {
        if (carrito.length === 0) { alert("El carrito está vacío."); return; }
        const dataStr = JSON.stringify(carrito, null, 2);
        const dataBlob = new Blob([dataStr], {type: "application/json"});
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        const fecha = new Date().toISOString().slice(0, 10);
        link.download = `mi_lista_che_super_${fecha}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    });

    uploadButton.addEventListener('click', () => { fileInput.click(); });
    fileInput.addEventListener('change', e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(event) {
            try {
                const nuevoCarrito = JSON.parse(event.target.result);
                if (Array.isArray(nuevoCarrito) && nuevoCarrito.every(item => 'ean' in item && 'nombre' in item && 'quantity' in item)) {
                    carrito = nuevoCarrito;
                    renderCarrito();
                    if (document.getElementById('productos-list')) fetchData(true);
                    alert("¡Lista cargada con éxito!");
                } else {
                    alert("El archivo no tiene el formato correcto.");
                }
            } catch (error) {
                alert("Error al leer el archivo.");
            }
        };
        reader.readAsText(file);
        e.target.value = '';
    });

    // --- INICIALIZACIÓN ---
    showCategoriasView();
    renderCarrito();
});