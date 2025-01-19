document.addEventListener('DOMContentLoaded', function() {
    // Handle reaction button clicks
    const reactionButtons = document.querySelectorAll('.add-reaction');
    let currentIdeaId = null;
    
    reactionButtons.forEach(button => {
        button.addEventListener('click', function() {
            currentIdeaId = this.dataset.ideaId;
            const modal = new bootstrap.Modal(document.getElementById('emojiModal'));
            modal.show();
        });
    });

    // Handle emoji selection
    const picker = document.querySelector('emoji-picker');
    if (picker) {
        picker.addEventListener('emoji-click', event => {
            if (currentIdeaId) {
                const emoji = event.detail.unicode;
                addReaction(currentIdeaId, emoji);
                bootstrap.Modal.getInstance(document.getElementById('emojiModal')).hide();
            }
        });
    }

    // Function to send reaction to server
    async function addReaction(ideaId, emoji) {
        try {
            const response = await fetch(`/idea/${ideaId}/react`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `emoji=${encodeURIComponent(emoji)}`
            });

            if (response.ok) {
                location.reload(); // Refresh to show new reaction
            } else {
                console.error('Failed to add reaction');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    // Initialize tooltips for reaction emojis
    const reactionEmojis = document.querySelectorAll('.reaction-emoji');
    reactionEmojis.forEach(emoji => {
        const username = emoji.dataset.user;
        if (username) {
            new bootstrap.Tooltip(emoji, {
                title: `Reacted by ${username}`,
                placement: 'top'
            });
        }
    });
});
