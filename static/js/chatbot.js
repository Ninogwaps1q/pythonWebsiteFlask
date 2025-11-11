document.getElementById("chatbot-toggle").onclick = () => {
  document.getElementById("chatbot-box").classList.toggle("hidden");
};

document.getElementById("send-btn").onclick = async () => {
  const input = document.getElementById("user-input");
  const message = input.value.trim();
  if (!message) return;

  const chatMessages = document.getElementById("chatbot-messages");

  addMessage(message, "user-msg");
  input.value = "";

  const response = await fetch("/chatbot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  const data = await response.json();
  addMessage(data.reply, "bot-msg");
};

function addMessage(text, type) {
  const chatMessages = document.getElementById("chatbot-messages");
  const msg = document.createElement("div");
  msg.className = type; 
  msg.textContent = text;
  chatMessages.appendChild(msg);

  chatMessages.scrollTop = chatMessages.scrollHeight;
};

async function updateCartCount() {
  try {
    const response = await fetch('/cart_count', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

    const data = await response.json();
    const cartCount = document.getElementById('cart-count');

    if (cartCount) {
      cartCount.textContent = data.count;
    }
  } catch (err) {
    console.error('Error updating cart count:', err);
  }
}

document.addEventListener('DOMContentLoaded', updateCartCount);

document.addEventListener('submit', function (e) {
  if (e.target.action.includes('/add_to_cart')) {t
    setTimeout(updateCartCount, 500);
  }
});

document.addEventListener('click', function (e) {
  if (
    e.target.matches('.remove-from-cart') ||
    e.target.matches('.clear-cart')
  ) {
    setTimeout(updateCartCount, 500);
  }
});
