// static/js/cart.js

function toggleCart() {
  const sidebar = document.getElementById('cart-sidebar');
  const overlay = document.getElementById('cart-overlay');
  const isOpen = !sidebar.classList.contains('translate-x-full');

  if (isOpen) {
    // Close cart
    sidebar.classList.add('translate-x-full');
    overlay.classList.add('opacity-0', 'pointer-events-none');
  } else {
    // Open cart
    sidebar.classList.remove('translate-x-full');
    overlay.classList.remove('opacity-0', 'pointer-events-none');
    // Trigger HTMX to load cart items
    htmx.trigger('#cart-items-container', 'items-updated');
  }
}

// Update cart count badge
function updateCartCount(count) {
  const badge = document.getElementById('cart-count');
  const badgeMobile = document.getElementById('cart-count-mobile');

  if (count > 0) {
    [badge, badgeMobile].forEach(el => {
      if (el) {
        el.textContent = count;
        el.style.display = 'flex';
        el.classList.add('animate-pulse');
        setTimeout(() => el.classList.remove('animate-pulse'), 1000);
      }
    });
  } else {
    [badge, badgeMobile].forEach(el => {
      if (el) el.style.display = 'none';
    });
  }
}

// Initialize cart on page load
document.addEventListener('DOMContentLoaded', function() {
  // Load cart items on page load
  htmx.trigger('#cart-items-container', 'items-updated');

  // Close cart with Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      const sidebar = document.getElementById('cart-sidebar');
      if (!sidebar.classList.contains('translate-x-full')) {
        toggleCart();
      }
    }
  });

  // Handle successful item deletion
  document.body.addEventListener('htmx:afterRequest', function(event) {
    if (event.detail.pathInfo.requestPath.includes('delete-item')) {
      // Reload cart items after deletion
      htmx.trigger('#cart-items-container', 'items-updated');
    }
  });

  // Auto-open cart when items are added
  document.body.addEventListener('htmx:afterRequest', function(event) {
    if (event.detail.pathInfo.requestPath.includes('add-item')) {
      toggleCart();
    }
  });
});