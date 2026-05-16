/** @odoo-module **/

import { Component, mount, onMounted, useRef, useState, whenReady } from "@odoo/owl";

class RoleSelector extends Component {
    static template = "mentorize.RoleSelector";
    static props = {
        defaultRole: { type: String, optional: true },
        kind: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ role: this.props.defaultRole || "mahasiswa" });
        this.rootRef = useRef("root");
        onMounted(() => this.applyRole());
    }

    selectRole(role) {
        this.state.role = role;
        this.applyRole();
    }

    applyRole() {
        const role = this.state.role;
        const kind = this.props.kind || "login";
        const root = (this.rootRef.el && this.rootRef.el.closest(".mtz-auth-card")) || document;
        const roleInput = root.querySelector("#input-role") || document.querySelector("#input-role");
        const identityLabel = root.querySelector("#identity-label") || document.querySelector("#identity-label");
        const identityInput = root.querySelector("#identity-input") || document.querySelector("#identity-input");
        const submitButton = root.querySelector("#btn-login") || root.querySelector("#btn-register") || document.querySelector("#btn-login") || document.querySelector("#btn-register");

        if (roleInput) roleInput.value = role;
        if (identityLabel) identityLabel.textContent = role === "mahasiswa" ? "NIM" : "KAPA";
        if (identityInput) identityInput.placeholder = role === "mahasiswa" ? "Masukkan NIM Anda" : "Masukkan KAPA Anda";
        if (submitButton) {
            const action = kind === "register" ? "Daftar" : "Masuk";
            submitButton.childNodes.forEach((node) => {
                if (node.nodeType === Node.TEXT_NODE) node.textContent = "";
            });
            submitButton.textContent = `${action} sebagai ${role === "mahasiswa" ? "Mahasiswa" : "Alumni"}`;
        }
    }
}

function setupPageTransitions() {
    document.documentElement.classList.add("mtz-page-ready");

    document.querySelectorAll("a[href]").forEach((link) => {
        const href = link.getAttribute("href") || "";
        const isInternal = href.startsWith("/") && !href.startsWith("/web/content") && !href.includes("#");
        if (!isInternal || link.target === "_blank") return;
        link.addEventListener("click", (event) => {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            document.body.style.transition = "opacity .18s ease, transform .18s ease";
            document.body.style.opacity = "0";
            document.body.style.transform = "translateY(6px)";
            window.setTimeout(() => { window.location.href = href; }, 170);
        });
    });
}

function setupLoadingForms() {
    document.querySelectorAll(".mtz-loading-form").forEach((form) => {
        form.addEventListener("submit", () => form.classList.add("is-loading"));
    });
}

function setupCounters() {
    document.querySelectorAll("[data-mtz-counter]").forEach((el) => {
        const target = parseInt(el.textContent || "0", 10);
        if (Number.isNaN(target) || target <= 0) return;
        let current = 0;
        const duration = 700;
        const start = performance.now();
        const tick = (now) => {
            const progress = Math.min((now - start) / duration, 1);
            current = Math.round(target * progress);
            el.textContent = String(current);
            if (progress < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    });
}

whenReady(() => {
    document.querySelectorAll(".mtz-role-owl-root").forEach((root) => {
        mount(RoleSelector, root, {
            props: {
                defaultRole: root.dataset.defaultRole || "mahasiswa",
                kind: root.dataset.kind || "login",
            },
        });
    });
    setupPageTransitions();
    setupLoadingForms();
    setupCounters();
});
