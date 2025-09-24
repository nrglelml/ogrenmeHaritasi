// static/js/faqScript.js

// Sıkça Sorulan Sorular Arama Fonksiyonu
function filterFAQs() {
  const query = document.getElementById("faqSearch").value.toLowerCase();
  const items = document.querySelectorAll(".accordion-item");

  items.forEach(item => {
    const question = item.querySelector(".accordion-button").textContent.toLowerCase();
    if (question.includes(query)) {
      item.style.display = "block";
    } else {
      item.style.display = "none";
    }
  });
}
