document.addEventListener("DOMContentLoaded", function() {
    // 1. Creamos el contenedor del Loading de inmediato
    const overlay = document.createElement('div');
    overlay.style.cssText = "position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: white; display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 999999; font-family: Arial, sans-serif;";
    
    const loader = document.createElement('div');
    loader.style.cssText = "border: 8px solid #f3f3f3; border-top: 8px solid #d12027; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin-bottom: 15px;";
    
    const texto = document.createElement('p');
    texto.style.cssText = "font-weight: bold; color: #333;";
    texto.innerText = "Conectando con JW.org y procesando las actividades...";

    const style = document.createElement('style');
    style.innerHTML = "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }";
    
    document.head.appendChild(style);
    overlay.appendChild(loader);
    overlay.appendChild(texto);
    document.body.appendChild(overlay);

    // 2. Esperamos un milisegundo a que el loading sea visible y REDIRIGIMOS por JS
    setTimeout(function() {
        // Redirige a la misma URL que tenías en tu admin.py
        window.location.href = "/admin/activities/guiaactividades/guia-mes-completo/";
    }, 50);
});