// Smooth scroll to products section after collection selection
document.addEventListener('DOMContentLoaded', function() {
  // Check if products section exists and has the data-scroll-to attribute
  const productsSection = document.getElementById('products-section');
  if (productsSection && productsSection.dataset.scrollTo === 'true') {
    productsSection.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  }
});

// Scroll after HTMX loads products
document.body.addEventListener('htmx:afterSwap', function(event) {
  console.log('HTMX afterSwap fired', event.detail.target.id);

  if (event.detail.target.id === 'products-container') {
    // Add a small delay to ensure DOM is fully updated
    setTimeout(function() {
      const productsSection = document.getElementById('products-section');
      console.log('Scrolling to products section', productsSection);

      if (productsSection) {
        productsSection.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    }, 100);
  }
});