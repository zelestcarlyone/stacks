class Toasts {
  constructor() {
    this.container = document.getElementById("toast-container");
    this.template = document.getElementById("toast-template");
  }

  show({ title = "", message = "", type = "info", timeout = 4000 }) {
    const toast = this._createToast(title, message, type);

    toast.classList.add("toast-" + type);
    this.container.appendChild(toast);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        toast.classList.add("show");
        toast.querySelector(".toast-progress").style.transition = `${timeout}ms linear`;
        toast.querySelector(".toast-progress").style.width = "0%";
      });
    });

    // Auto-remove
    setTimeout(() => this._removeToast(toast), timeout);
  }

  _createToast(title, message, type) {
    const node = this.template.content.firstElementChild.cloneNode(true);

    node.classList.add(type);

    node.querySelector(".toast-title").textContent = title;
    node.querySelector(".toast-message").textContent = message;

    // Icon mapping
    const icon = node.querySelector(".toast-icon");
    icon.setAttribute("data-icon", type);
    
    // Close button
    node.querySelector(".toast-close").addEventListener("click", () => {
      this._removeToast(node);
    });

    return node;
  }

  _removeToast(toast) {
    toast.classList.remove("show");
    toast.classList.add("hide");
    const handler = (e) => {
      if (e.target === toast) {
        toast.remove();
        toast.removeEventListener("transitionend", handler);
      }
    };
    toast.addEventListener("transitionend", handler);
  }
}

window.toasts = new Toasts();
