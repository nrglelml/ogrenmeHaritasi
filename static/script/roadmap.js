// Yol Haritası Oluşturma Fonksiyonu
async function generateRoadmap(event) {
    event.preventDefault();
    const userData = {
        goal: document.getElementById("goal").value,
        learning_style: document.getElementById("learning_style").value,
        daily_time: parseInt(document.getElementById("daily_time").value)
    };

    const response = await fetch('/api/roadmap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
    });

    const data = await response.json();
    document.getElementById("roadmap-result").innerHTML = `
        <ul>
            ${data.map(step => `<li>${step.step} - ${step.days_needed} gün</li>`).join('')}
        </ul>
    `;
}


// Yol Haritasını Sayfada Göster
function displayRoadmap(data) {
    const resultContainer = document.getElementById("roadmap-result");
    resultContainer.innerHTML = `
        <h3>Hedefiniz: ${data.goal}</h3>
        <h4>Günlük Çalışma Süresi: ${data.daily_time} saat</h4>
        <h4>Öğrenme Tarzı: ${data.learning_style}</h4>
        <ul class="list-group">
            ${data.roadmap
                .map(
                    (step) =>
                        `<li class="list-group-item">
                            <strong>Adım:</strong> ${step.step}<br>
                            <strong>Tahmini Süre:</strong> ${step.days_needed} gün
                        </li>`
                )
                .join("")}
        </ul>
    `;
}

// Form olay dinleyicisi
document.getElementById("roadmapForm").addEventListener("submit", generateRoadmap);
