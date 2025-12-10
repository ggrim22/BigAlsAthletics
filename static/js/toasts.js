// Listen for HTMX "messages" event only once
htmx.on("messages", (e) => {
  const messages = e.detail.value;

  // If you want logging, uncomment this:
  // console.log(messages);

  messages.forEach(createToast);
});

function createToast(message) {
  // Clone the template
  const element = htmx.find("[data-toast-template]").cloneNode(true);

  // Remove the data-toast-template attribute
  delete element.dataset.toastTemplate;

  // Apply CSS classes (Bootstrap alert classes)
  element.className += " " + message.tags;

  // Insert the message text
  htmx.find(element, "[data-toast-body]").innerText = message.message;

  // Add the toast to the container
  htmx.find("[data-toast-container]").appendChild(element);

  // Show with Bootstrap API
  const toast = new bootstrap.Toast(element, { delay: 1500 });
  toast.show();
}
