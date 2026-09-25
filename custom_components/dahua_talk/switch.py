"""Công tắc tắt mic: vệ tinh thôi nghe (loa và thông báo vẫn chạy)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DahuaTalkConfigEntry
from .entity import DahuaTalkEntity


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DahuaTalkMuteSwitch(entry)])


class DahuaTalkMuteSwitch(DahuaTalkEntity, SwitchEntity, RestoreEntity):
    _attr_translation_key = "mute"

    def __init__(self, entry: DahuaTalkConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}-mute"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        cu = await self.async_get_last_state()
        self._entry.runtime_data.set_mic_muted(cu is not None and cu.state == STATE_ON)

    @property
    def is_on(self) -> bool:
        return self._entry.runtime_data.mic_muted

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._entry.runtime_data.set_mic_muted(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._entry.runtime_data.set_mic_muted(False)
        self.async_write_ha_state()
