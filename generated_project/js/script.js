(function() {
  // Exported function for smooth scrolling to a target element by ID
  function smoothScroll(targetId) {
    var element = document.getElementById(targetId);
    if (!element) return;
    window.scrollTo({
      top: element.offsetTop,
      behavior: 'smooth'
    });
  }

  // Helper to remove previous error states/messages
  function clearFieldError(field) {
    field.classList.remove('error');
    var next = field.nextElementSibling;
    if (next && next.classList.contains('error-msg')) {
      next.parentNode.removeChild(next);
    }
  }

  // Validate contact form on submit
  function validateContactForm(event) {
    event.preventDefault();
    var form = event.target;
    var nameField = form.querySelector('#name');
    var emailField = form.querySelector('#email');
    var messageField = form.querySelector('#message');

    // Clear previous errors
    [nameField, emailField, messageField].forEach(clearFieldError);

    var hasError = false;
    var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    // Name validation
    if (!nameField.value.trim()) {
      hasError = true;
      nameField.classList.add('error');
      var span = document.createElement('span');
      span.className = 'error-msg';
      span.textContent = 'Name is required.';
      nameField.parentNode.appendChild(span);
    }

    // Email validation
    if (!emailField.value.trim() || !emailPattern.test(emailField.value.trim())) {
      hasError = true;
      emailField.classList.add('error');
      var span = document.createElement('span');
      span.className = 'error-msg';
      span.textContent = emailField.value.trim() ? 'Enter a valid email address.' : 'Email is required.';
      emailField.parentNode.appendChild(span);
    }

    // Message validation
    if (!messageField.value.trim()) {
      hasError = true;
      messageField.classList.add('error');
      var span = document.createElement('span');
      span.className = 'error-msg';
      span.textContent = 'Message cannot be empty.';
      messageField.parentNode.appendChild(span);
    }

    if (!hasError) {
      alert('Form submitted (placeholder)');
      // Optionally, you could reset the form here:
      // form.reset();
    }
  }

  // Attach listeners once DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll links
    var scrollLinks = document.querySelectorAll('a[data-scroll]');
    scrollLinks.forEach(function(link) {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        var href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
          var targetId = href.substring(1);
          smoothScroll(targetId);
        }
      });
    });

    // Contact form submit handler
    var contactForm = document.getElementById('contactForm');
    if (contactForm) {
      contactForm.addEventListener('submit', validateContactForm);
    }
  });

  // Expose smoothScroll globally if needed
  window.smoothScroll = smoothScroll;
})();