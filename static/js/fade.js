/*
Functionality to apply a fade class to any feature which has the 'data-fade-ms` data attribute. This
data attribute defines a time in ms, after which the `fade-default` class will be applied. This class
then plays an animation which will fade the object from view by setting its opacity to 0.
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
