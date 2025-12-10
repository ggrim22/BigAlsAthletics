// static/js/cart-update.js

// This function is called from the shopping cart partial template
// to update the UI after cart data is loaded
function updateCartUI(itemCount, totalCost) {
  // Update cart count badge
  updateCartCount(itemCount);

  // Update total display
  const totalElement = document.getElementById('cart-total');
  if (totalElement) {
    totalElement.textContent = '$' + parseFloat(totalCost).toFixed(2);
  }

  // Enable/disable checkout button based on cart contents
  const checkoutBtn = document.getElementById('checkout-btn');
  if (checkoutBtn) {
    checkoutBtn.disabled = itemCount === 0;
  }
}