/*
this file contains any theme related code that can be removed from the header/base,
they should only be placed there when performance is needed.
*/

function changeTheme() {
  const storedColorMode = localStorage.getItem("colorMode");
  const browserColorMode = getBrowserColorMode(window);
  let newColorMode = null;
  if (storedColorMode) {
    newColorMode = storedColorMode === "dark" ? "light" : "dark";
  } else {
    newColorMode = browserColorMode === "dark" ? "light" : "dark";
  }
  saveColorMode(newColorMode);  // triggers theme change via storage event
}

function saveColorMode(colorMode) {
  const oldColorMode = localStorage.getItem("colorMode");
  const allowedModes = ['light', 'dark'];
  if (!allowedModes.includes(colorMode)) {
    if (console) {
      console.warn(`Invalid color mode: ${colorMode}`);
    }
    return;
  }
  localStorage.setItem("colorMode", colorMode);
  // this is dumb but only on pages that AREN'T the current page do normal
  // localStorage events get picked up, so they need to be triggered manually here.
  // To prevent errors from triggering twice actions should be idempotent.
  window.dispatchEvent(
    new StorageEvent('storage', {
      key: 'colorMode',
      oldValue: oldColorMode,
      newValue: colorMode,
    })
  );
}

// here we handle the picking up of the change in color mode from the storage event
// which is then handled differently for iframes with very slight delay for the
// parent so there's minimal disparity between iframe and parent changing
window.addEventListener('storage', function (e) {
  if (e.key === 'colorMode' && e.newValue) {
    let isIframe = window.location.pathname === "srcdoc";
    if (isIframe) {
      setColorElements(e.newValue);
    }
    else {
      setTimeout(() => setColorElements(e.newValue), 1);
    }
    const geckoSearchButton = document.getElementById("gecko-search-button");
    if (geckoSearchButton) {
      geckoSearchButton.setAttribute('data-theme-mode', e.newValue);
    }
  }
});

function setColorElements(colorMode) {
  const iconchange = document.getElementById("light-dark")
  const docElement = document.documentElement;
  if (colorMode === "dark") {
    if (iconchange) {
      iconchange.classList.remove('fa-moon');
      iconchange.classList.add('fa-sun');
    }
    docElement.classList.remove("light");
  } else {
    if (iconchange) {
      iconchange.classList.remove('fa-sun');
      iconchange.classList.add('fa-moon');
    }
    docElement.classList.remove("dark");
  }
  docElement.classList.add(colorMode);
}


function getBrowserColorMode(win) {
  // win is the appropriate window object
  const prefersDark = win.matchMedia('(prefers-color-scheme: dark)').matches;
  return prefersDark ? "dark" : "light";
}

function checkmedia() {
  const relevantWindow = window.parent || window;
  let browserColorMode = null;
  const userColorMode = localStorage.getItem("colorMode");
  if (!relevantWindow.matchMedia) {
    browserColorMode = getBrowserColorMode(relevantWindow);
    //  transparently removed on next load if matches browser setting
    if (userColorMode === browserColorMode) {
      localStorage.removeItem("colorMode");
    }
  }
  setColorElements(userColorMode || browserColorMode || "light");
}

checkmedia();

document.addEventListener("alpine:init", function() {
  document.getElementById("gecko-search-button").setAttribute(
    'data-theme-mode',
    localStorage.getItem("colorMode") || getBrowserColorMode(window)
  );
});
