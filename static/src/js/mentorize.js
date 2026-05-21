console.log("Mentorize Dashboard Loaded");
document.addEventListener('DOMContentLoaded', function () {

    const chartCanvas = document.getElementById('userChart');

    if (chartCanvas) {

        new Chart(chartCanvas, {

            type: 'bar',

            data: {

                labels: [
                    'Mahasiswa',
                    'Alumni',
                    'Mentoring Aktif',
                    'User Suspended'
                ],

                datasets: [{

                    label: 'Statistik Platform',

                    data: JSON.parse(
                        chartCanvas.dataset.chart.replace(/'/g, '"')
                    ),

                    borderRadius: 12,
                    borderSkipped: false,

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {
                        display: false
                    }

                },

                scales: {

                    y: {

                        beginAtZero: true,

                        ticks: {
                            stepSize: 20
                        },

                        grid: {
                            drawBorder: false
                        }

                    },

                    x: {

                        grid: {
                            display: false
                        }

                    }

                }

            }

        });

    }

});
```
