// Smooth scroll to products section after collection selection
document.addEventListener('DOMContentLoaded', function() {
  const productsSection = document.getElementById('products-section');
  if (productsSection && productsSection.dataset.scrollTo === 'true') {
    productsSection.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  }
});

document.body.addEventListener('htmx:afterSwap', function(event) {

  if (event.detail.target.id === 'products-container') {
    setTimeout(function() {
      const productsSection = document.getElementById('products-section');

      if (productsSection) {
        productsSection.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    }, 100);
  }
});