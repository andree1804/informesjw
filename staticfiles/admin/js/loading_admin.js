document.addEventListener("DOMContentLoaded", function() {
    // Buscamos el enlace en el sidebar. 
    // El href suele contener el nombre del modelo 'guiaactividades'
    const enlaces = document.querySelectorAll('a[href*="guiaactividades"]');

    enlaces.forEach(enlace => {
        enlace.addEventListener("click", function(e) {
            // Evitar que se active con clic derecho
            if (e.button !== 0) return;

            const overlay = document.createElement('div');
            overlay.id = "loading-global-admin";
            overlay.style.cssText = "position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: white; display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 999999; font-family: Arial, sans-serif;";
            
            const loader = document.createElement('div');
            loader.style.cssText = "border: 8px solid #f3f3f3; border-top: 8px solid #d12027; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin-bottom: 15px;";
            
            const texto = document.createElement('p');
            texto.style.cssText = "font-weight: bold; color: #333;";
            texto.innerText = "Cargando actividades desde JW.org...";

            const style = document.createElement('style');
            style.innerHTML = "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }";
            
            document.head.appendChild(style);
            overlay.appendChild(loader);
            overlay.appendChild(texto);
            document.body.appendChild(overlay);
        });
    });
});