/**
 * handles card click navigation with modifier key support
 * @param {Event} event - the click event
 * @param {string} url - the URL to navigate to
 */
function handleCardClick(event, url) {
  if (event.target.tagName === 'A' || event.target.closest('a')) {
    return;
  }
  if (event.ctrlKey || event.metaKey || event.shiftKey) {
    window.open(url, '_blank');
    return;
  }
  window.location = url;
}
