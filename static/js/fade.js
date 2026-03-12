/*

*/


(function () {
    function initFade(root) {
        if (!root) return;

        const fadeDelay = root.getAttribute('data-fade-ms');
        if (fadeDelay) {
            setTimeout(() => {
                root.classList.add("fade-default")
            }, parseInt(fadeDelay, 10));
        }
    }

    function init() {
        document.querySelectorAll('[data-fade-ms]').forEach(initFade);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFade);
    } else {
        init();
    }
})();
