from typing import Optional, Callable

import discord

from effect import Effect
from util import get_player_from_member  # Assumes this function exists to retrieve player data


class PlayerInteractionView(discord.ui.View):
    """Handles player interactions (e.g., hug, handshake) with accept/reject buttons."""

    def __init__(
            self,
            initiator: discord.Member,
            recipient: discord.Member,
            effect_initiator: Optional[tuple] = None,
            effect_recipient: Optional[tuple] = None,
            custom_function: Optional[Callable] = None,
            success_embed: Optional[discord.Embed] = None,  # Accept success embed
            failure_embed: Optional[discord.Embed] = None,  # Accept failure embed
            timeout: int = 300,
    ):
        """
        Initializes the interaction view.
        """
        super().__init__(timeout=timeout)
        self.initiator = initiator
        self.recipient = recipient
        self.effect_initiator = effect_initiator
        self.effect_recipient = effect_recipient
        self.custom_function = custom_function
        self.success_embed = success_embed
        self.failure_embed = failure_embed

    @discord.ui.button(label="Accept ✅", style=discord.ButtonStyle.green)
    async def accept_interaction(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handles acceptance of the interaction."""
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message("This request is not for you!", ephemeral=True)
            return

        # Retrieve player objects
        initiator_player = get_player_from_member(interaction, self.initiator)
        recipient_player = get_player_from_member(interaction, self.recipient)

        # Check if players exist
        if not initiator_player or not recipient_player:
            await interaction.response.send_message(
                "One or both players are not registered in the system.", ephemeral=True
            )
            return

        # Apply effects if provided
        if self.effect_initiator:
            initiator_player.add_effect(Effect(*self.effect_initiator))

        if self.effect_recipient:
            recipient_player.add_effect(Effect(*self.effect_recipient))

        # Execute custom function if provided
        if self.custom_function:
            await self.custom_function(interaction, self.initiator, self.recipient)

        # Clone embed to avoid modifying shared reference
        if self.success_embed:
            embed = discord.Embed(
                title=self.success_embed.title,
                description=self.success_embed.description.format(
                    sender=self.initiator.display_name, recipient=self.recipient.display_name
                ),
                color=self.success_embed.color
            )
        else:
            embed = discord.Embed(
                title="Interaction Successful! 🎉",
                description=f"**{self.initiator.display_name}** and **{self.recipient.display_name}** shared a warm hug!",
                color=0x00FF00
            )

        await interaction.message.edit(embed=embed, view=None)  # Update message and remove buttons

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.red)
    async def decline_interaction(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handles rejection of the interaction."""
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message("This request is not for you!", ephemeral=True)
            return

        # Clone embed to avoid modifying shared reference
        if self.failure_embed:
            embed = discord.Embed(
                title=self.failure_embed.title,
                description=self.failure_embed.description.format(
                    sender=self.initiator.display_name, recipient=self.recipient.display_name
                ),
                color=self.failure_embed.color
            )
        else:
            embed = discord.Embed(
                title="Interaction Declined ❌",
                description=f"**{self.recipient.display_name}** declined the interaction with **{self.initiator.display_name}**.",
                color=0x808080
            )

        await interaction.message.edit(embed=embed, view=None)  # Update message and remove buttons
