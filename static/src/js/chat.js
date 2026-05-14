/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { mount } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc_service";

class MentorizeChatApp extends Component {
    static template = "mentorize.MentorizeChatApp";

    setup() {
        this.state = useState({
            loading: true,
            currentUser: {},
            conversations: [],
            messages: [],
            mentorDetail: {},
            selectedRoomId: null,
            newMessage: "",
        });

        onWillStart(async () => {
            await this.loadChatData();
        });

        onMounted(() => {
            this.scrollToBottom();
        });
    }

    async loadChatData() {
        const params = new URLSearchParams(window.location.search);
        const roomId = params.get("room_id");

        const data = await rpc("/mentorize/chat/data", {
            room_id: roomId,
        });

        this.state.currentUser = data.current_user || {};
        this.state.conversations = data.conversations || [];
        this.state.messages = data.messages || [];
        this.state.mentorDetail = data.mentor_detail || {};

        if (data.selected_room_id) {
            this.state.selectedRoomId = data.selected_room_id;
        } else if (this.state.conversations.length > 0) {
            this.state.selectedRoomId = this.state.conversations[0].id;
        }

        this.state.loading = false;

        setTimeout(() => {
            this.scrollToBottom();
        }, 100);
    }

    async selectRoom(roomId) {
        this.state.selectedRoomId = roomId;

        const data = await rpc("/mentorize/chat/data", {
            room_id: roomId,
        });

        this.state.messages = data.messages || [];
        this.state.mentorDetail = data.mentor_detail || {};

        const newUrl = `/mentorize/mahasiswa/chat?room_id=${roomId}`;
        window.history.pushState({}, "", newUrl);

        setTimeout(() => {
            this.scrollToBottom();
        }, 100);
    }

    async sendMessage() {
        const message = this.state.newMessage.trim();

        if (!message || !this.state.selectedRoomId) {
            return;
        }

        const result = await rpc("/mentorize/chat/send", {
            room_id: this.state.selectedRoomId,
            message: message,
        });

        if (result.success) {
            this.state.messages.push(result.message);
            this.state.newMessage = "";

            setTimeout(() => {
                this.scrollToBottom();
            }, 50);
        }
    }

    onEnterKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    scrollToBottom() {
        const box = document.querySelector(".mz-chat-messages");
        if (box) {
            box.scrollTop = box.scrollHeight;
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const target = document.querySelector("#mentorize_chat_app");

    if (target) {
        mount(MentorizeChatApp, target);
    }
});