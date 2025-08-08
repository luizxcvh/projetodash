// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    try {
        Telegram.WebApp.ready();
    } catch (e) {
        console.warn("Telegram WebApp script não encontrado.");
    }

    // --- GRÁFICOS DE ROSCA (ORÇAMENTO GERAL DAS SECRETARIAS) ---
    const secretariaDoughnutCharts = document.querySelectorAll('.chart-container canvas:not(.obra-chart)');
    secretariaDoughnutCharts.forEach(canvas => {
        const secretariaId = canvas.dataset.id;
        if (!secretariaId) return;
        fetch(`/api/orcamento/secretaria/${secretariaId}`)
            .then(response => response.json())
            .then(data => {
                renderDoughnutChart(canvas, [data.orcamento_gasto, data.orcamento_restante]);
            });
    });

    // --- GRÁFICOS DE LINHA (GASTOS DIÁRIOS DAS SECRETARIAS) ---
    const lineCharts = document.querySelectorAll('.chart-container-diario canvas');
    lineCharts.forEach(canvas => {
        const secretariaId = canvas.dataset.id;
        if (!secretariaId) return;
        fetch(`/api/gastos_diarios/secretaria/${secretariaId}`)
            .then(response => response.json())
            .then(data => {
                renderLineChart(canvas, data.labels, data.data);
            });
    });

    // --- GRÁFICOS DE ROSCA (ORÇAMENTO INDIVIDUAL DAS OBRAS) ---
    const obraDoughnutCharts = document.querySelectorAll('.obra-chart');
    obraDoughnutCharts.forEach(canvas => {
        const obraId = canvas.dataset.id;
        if (!obraId) return;
        fetch(`/api/orcamento/obra/${obraId}`)
            .then(response => response.json())
            .then(data => {
                renderDoughnutChart(canvas, [data.total_gasto, data.saldo]);
            });
    });
});

// --- FUNÇÃO AUXILIAR PARA FORMATAR MOEDA ---
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor);
}

// --- FUNÇÕES REUTILIZÁVEIS PARA DESENHAR GRÁFICOS ---
function renderDoughnutChart(canvas, data) {
    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: ['Gasto', 'Disponível'],
            datasets: [{ data: data, backgroundColor: ['#F97316', '#10B981'], borderColor: '#FFFFFF', borderWidth: 5, hoverOffset: 10 }]
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

function renderLineChart(canvas, labels, data) {
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 150);
    gradient.addColorStop(0, 'rgba(8, 145, 178, 0.4)');
    gradient.addColorStop(1, 'rgba(8, 145, 178, 0)');

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Gastos Diários', data: data, borderColor: '#0891B2', borderWidth: 2,
                pointBackgroundColor: '#0891B2', fill: true, backgroundColor: gradient, tension: 0.3
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (context) => `Gasto: ${formatarMoeda(context.parsed.y)}` } }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: (value) => formatarMoeda(value) }
                }
            }
        }
    });
}