let explicitelyPreferScheme = false;

if (window.localStorage) {
    if (localStorage.getItem('colorMode') === 'dark') {
        document.documentElement.classList.add('dark');
        explicitelyPreferScheme = 'dark';
    } else if (localStorage.getItem('colorMode') === 'light') {
        document.documentElement.classList.remove('dark');
        explicitelyPreferScheme = 'light';
    }
}

if (explicitelyPreferScheme !== 'light' && window.matchMedia('(prefers-color-scheme:dark)').matches) {
    document.documentElement.classList.add('dark');
}
