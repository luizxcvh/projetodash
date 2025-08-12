document.addEventListener('DOMContentLoaded', function() {
    // Tenta inicializar a Web App do Telegram
    try {
        Telegram.WebApp.ready();
    } catch (e) {
        console.warn("Telegram WebApp script não encontrado ou erro na inicialização.");
    }

    // --- RENDERIZAÇÃO DE GRÁFICOS ---
    
    // Gráficos de Rosca (Orçamento Geral das Secretarias)
    const secretariaDoughnutCharts = document.querySelectorAll('.chart-container canvas:not(.obra-chart)');
    secretariaDoughnutCharts.forEach(canvas => {
        const secretariaId = canvas.dataset.id;
        if (secretariaId) {
            fetch(`/api/orcamento/secretaria/${secretariaId}`)
                .then(response => response.json())
                .then(data => renderDoughnutChartSecretaria(canvas, [data.orcamento_gasto, data.orcamento_restante]));
        }
    });

    // Gráficos de Linha (Fluxo de Caixa das Secretarias)
    const lineCharts = document.querySelectorAll('.chart-container-diario canvas');
    lineCharts.forEach(canvas => {
        const secretariaId = canvas.dataset.id;
        if (secretariaId) {
            fetch(`/api/gastos_diarios/secretaria/${secretariaId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.labels && data.labels.length > 0) {
                        renderLineChart(canvas, data.labels, data.gastos, data.saldos, data.teto_orcamento, data.medicoes);
                    }
                });
        }
    });

    // Gráficos de Rosca (Orçamento Individual das Obras)
    const obraDoughnutCharts = document.querySelectorAll('.obra-chart');
    obraDoughnutCharts.forEach(canvas => {
        const obraId = canvas.dataset.id;
        if (obraId) {
            fetch(`/api/orcamento/obra/${obraId}`)
                .then(response => response.json())
                .then(data => renderDoughnutChartObra(canvas, data.gasto_da_obra, data.saldo_da_secretaria));
        }
    });

    // GRÁFICOS EM MINIATURA (TABELA DE OBRAS)
    const miniCharts = document.querySelectorAll('.mini-chart');
    miniCharts.forEach(canvas => {
        const gasto = parseFloat(canvas.dataset.gasto) || 0;
        const restante = parseFloat(canvas.dataset.restante) || 0;

        let chartData, chartColors;

        if (restante <= 0) {
            chartData = [gasto];
            chartColors = [getComputedStyle(document.body).getPropertyValue('--prejuizo-color')];
        } else {
            chartData = [gasto, restante];
            chartColors = [
                getComputedStyle(document.body).getPropertyValue('--gasto-color'),
                getComputedStyle(document.body).getPropertyValue('--disponivel-color')
            ];
        }

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: chartData,
                    backgroundColor: chartColors,
                    borderColor: getComputedStyle(document.body).getPropertyValue('--card-bg-color'), 
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '70%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                }
            }
        });
    });

    // --- LÓGICA DO BOTÃO DE ALTERNÂNCIA DE TEMA ---
    const themeToggle = document.getElementById('theme-toggle');
    
    const switchTheme = (e) => {
        if (e.target.checked) {
            document.documentElement.classList.add('dark-mode');
            localStorage.setItem('theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark-mode');
            localStorage.setItem('theme', 'light');
        }
    };

    if (themeToggle) {
        themeToggle.addEventListener('change', switchTheme);
        const currentTheme = localStorage.getItem('theme');
        if (currentTheme) {
            if (currentTheme === 'dark') {
                themeToggle.checked = true;
            }
        } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            themeToggle.checked = true;
        }
    }
});


// ==============================================================================
// FUNÇÕES AUXILIARES GLOBAIS
// ==============================================================================

function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor);
}

function renderDoughnutChartSecretaria(canvas, data) {
    const [gasto, restante] = data;
    let chartData, chartLabels, chartColors;

    if (restante <= 0) {
        chartLabels = ['Orçamento Excedido'];
        chartData = [gasto];
        chartColors = [getComputedStyle(document.body).getPropertyValue('--prejuizo-color')];
    } else {
        chartLabels = ['Gasto Consolidado', 'Saldo Geral'];
        chartData = [gasto, restante];
        chartColors = [
            getComputedStyle(document.body).getPropertyValue('--gasto-color'),
            getComputedStyle(document.body).getPropertyValue('--disponivel-color')
        ];
    }

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{ 
                data: chartData, 
                backgroundColor: chartColors,
                borderColor: getComputedStyle(document.body).getPropertyValue('--bg-color'), 
                borderWidth: 5, 
                hoverOffset: 10 
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '75%',
            plugins: { 
                legend: { display: false }, 
                tooltip: { callbacks: { label: (context) => `${context.label}: ${formatarMoeda(context.parsed)}` } }
            }
        }
    });
}

function renderDoughnutChartObra(canvas, gastoObra, saldoSecretaria) {
    const saldoParaGrafico = Math.max(0, saldoSecretaria);
    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: ['Gasto (desta Obra)', 'Disponível (na Secretaria)'],
            datasets: [{ 
                data: [gastoObra, saldoParaGrafico], 
                backgroundColor: [
                    getComputedStyle(document.body).getPropertyValue('--gasto-color'),
                    getComputedStyle(document.body).getPropertyValue('--disponivel-color')
                ], 
                borderColor: getComputedStyle(document.body).getPropertyValue('--bg-color'), 
                borderWidth: 5, 
                hoverOffset: 10 
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '75%',
            plugins: { 
                legend: { display: false }, 
                tooltip: { callbacks: { label: (context) => `${context.label}: ${formatarMoeda(context.parsed)}` } }
            }
        }
    });
}

function renderLineChart(canvas, labels, gastos, saldos, tetoOrcamento, medicoes) {
    const saldoFinal = saldos.length > 0 ? saldos[saldos.length - 1] : 0;
    const saldoColor = saldoFinal >= 0 ? 
        getComputedStyle(document.body).getPropertyValue('--disponivel-color') : 
        getComputedStyle(document.body).getPropertyValue('--prejuizo-color');

    const gastoColor = getComputedStyle(document.body).getPropertyValue('--gasto-color').trim();
    const gastoColorTransparent = gastoColor + '66';

    const coresMarcador = ['#8B5CF6', '#D946EF', '#F59E0B', '#14B8A6', '#EC4899']; // Violeta, Magenta, Âmbar, Turquesa, Rosa-choque
    const datasDeMedicao = new Set(medicoes.map(m => m.data));
    
    const marcadoresData = medicoes.map((medicao, index) => {
        const dataIndex = labels.indexOf(medicao.data);
        if (dataIndex === -1) return null;
        return {
            x: dataIndex,
            y: saldos[dataIndex],
            valor: medicao.valor,
            nome: medicao.nome,
            cor: coresMarcador[index % coresMarcador.length]
        };
    }).filter(p => p !== null);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    type: 'line',
                    label: 'Saldo Acumulado',
                    data: saldos,
                    borderColor: saldoColor,
                    borderWidth: 3,
                    fill: false,
                    tension: 0.3,
                    yAxisID: 'y',
                    pointRadius: (ctx) => datasDeMedicao.has(labels[ctx.dataIndex]) ? 6 : 0,
                    pointHoverRadius: (ctx) => datasDeMedicao.has(labels[ctx.dataIndex]) ? 8 : 0,
                    pointBackgroundColor: (ctx) => {
                        const marcador = marcadoresData.find(m => m.x === ctx.dataIndex);
                        return marcador ? marcador.cor : 'transparent';
                    },
                },
                {
                    type: 'bar',
                    label: 'Gasto Diário',
                    data: gastos,
                    backgroundColor: gastoColorTransparent,
                    borderColor: gastoColor,
                    borderWidth: 1,
                    yAxisID: 'y'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'bottom', labels: { color: getComputedStyle(document.body).getPropertyValue('--text-secondary') } },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: (context) => {
                            if (context.dataset.type === 'line' && context.element.options.radius > 0) {
                                const marcador = marcadoresData.find(m => m.x === context.dataIndex);
                                if (marcador) {
                                    return `Nova Medição (${marcador.nome}): ${formatarMoeda(marcador.valor)}`;
                                }
                            }
                            return `${context.dataset.label}: ${formatarMoeda(context.parsed.y)}`;
                        }
                    }
                }
            },
            scales: {
                x: { 
                    grid: { display: false }, 
                    ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-secondary') } 
                },
                y: {
                    beginAtZero: false,
                    position: 'left',
                    max: tetoOrcamento > 0 ? tetoOrcamento : undefined,
                    grid: { color: getComputedStyle(document.body).getPropertyValue('--border-color') },
                    ticks: {
                        color: getComputedStyle(document.body).getPropertyValue('--text-secondary'),
                        callback: (value) => {
                            if (Math.abs(value) >= 1000000) return `${formatarMoeda(value/1000000)}M`;
                            if (Math.abs(value) >= 1000) return `${formatarMoeda(value/1000)}k`;
                            return formatarMoeda(value);
                        }
                    }
                }
            }
        }
    });

    // Constrói a legenda de texto dinamicamente
    const legendContainer = document.getElementById(`legend-${canvas.dataset.id}`);
    if (legendContainer) {
        legendContainer.innerHTML = '';
        marcadoresData.forEach(marcador => {
            const item = document.createElement('div');
            item.className = 'legend-item';
            
            const dot = document.createElement('span');
            dot.className = 'legend-color-dot';
            dot.style.backgroundColor = marcador.cor;
            
            const text = document.createElement('span');
            text.className = 'legend-text';
            text.innerHTML = `${marcador.nome}: <strong>${formatarMoeda(marcador.valor)}</strong>`;
            
            item.appendChild(dot);
            item.appendChild(text);
            legendContainer.appendChild(item);
        });
    }
}