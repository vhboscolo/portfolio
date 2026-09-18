// Ícones Lucide (o script chega por CDN com integridade fixada; se falhar, a página segue sem ícones)
if (window.lucide) window.lucide.createIcons();

const reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Rolagem suave só para âncoras desta página
document.querySelectorAll('a[href^="#"]').forEach((ancora) => {
  ancora.addEventListener("click", (evento) => {
    const alvo = ancora.getAttribute("href").length > 1 && document.querySelector(ancora.getAttribute("href"));
    if (!alvo) return;
    evento.preventDefault();
    alvo.scrollIntoView({ behavior: reduzMovimento ? "auto" : "smooth" });
    if (ancora.classList.contains("pular")) alvo.focus?.();
  });
});

// Calculadora de eficiência (só existe na home)
const horas = document.getElementById("hours-range");
const custoHora = document.getElementById("hourly-rate");
if (horas && custoHora) {
  const atualizar = () => {
    const horasSemana = parseInt(horas.value, 10);
    const valorHora = parseInt(custoHora.value, 10) || 0;
    // premissa: a automação devolve 80% do tempo manual, em 48 semanas úteis
    const horasAno = Math.round(horasSemana * 0.8 * 48);
    document.getElementById("hours-display").textContent = horasSemana;
    document.getElementById("time-value").textContent = `${horasAno} horas`;
    document.getElementById("savings-value").textContent = `R$ ${(horasAno * valorHora).toLocaleString("pt-BR")}`;
  };
  horas.addEventListener("input", atualizar);
  custoHora.addEventListener("input", atualizar);
  atualizar();
}

// Revelação em cascata ao rolar (desligada com movimento reduzido)
if (!reduzMovimento && "IntersectionObserver" in window) {
  const observador = new IntersectionObserver((entradas) => {
    entradas.forEach((entrada) => {
      if (!entrada.isIntersecting) return;
      entrada.target.style.opacity = "1";
      entrada.target.style.transform = "translateY(0)";
      observador.unobserve(entrada.target);
    });
  }, { threshold: 0.1, rootMargin: "0px 0px -50px 0px" });

  document.querySelectorAll(".glass-card, .feature-card, .process-card, .roi-grid, .methodology-content")
    .forEach((elemento, indice) => {
      elemento.style.opacity = "0";
      elemento.style.transform = "translateY(30px)";
      elemento.style.transition = `opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1) ${(indice % 3) * 0.1}s, transform 0.8s cubic-bezier(0.16, 1, 0.3, 1) ${(indice % 3) * 0.1}s`;
      observador.observe(elemento);
    });
}

// Cabeçalho mais opaco e botão flutuante de WhatsApp depois de rolar
const cabecalho = document.querySelector("header");
const botaoFlutuante = document.querySelector(".floating-cta");
if (botaoFlutuante) {
  botaoFlutuante.style.transition = "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)";
}
const aoRolar = () => {
  const rolou = window.scrollY > 50;
  if (cabecalho) {
    cabecalho.style.background = rolou ? "rgba(3, 7, 18, 0.9)" : "rgba(3, 7, 18, 0.7)";
    cabecalho.style.boxShadow = rolou ? "0 10px 30px rgba(0,0,0,0.3)" : "none";
  }
  if (botaoFlutuante) {
    botaoFlutuante.style.transform = rolou ? "scale(1)" : "scale(0)";
    botaoFlutuante.style.opacity = rolou ? "1" : "0";
  }
};
window.addEventListener("scroll", aoRolar, { passive: true });
aoRolar();
