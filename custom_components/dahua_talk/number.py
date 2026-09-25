"""Mức tăng mic (dB): mic camera nhỏ, nói cách vài mét không tới ngưỡng từ gọi."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DahuaTalkConfigEntry
from .const import MIC_GAIN_MAX
from .entity import DahuaTalkEntity


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DahuaTalkMicGain(entry)])


class DahuaTalkMicGain(DahuaTalkEntity, RestoreNumber):
    _attr_translation_key = "mic_gain"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = MIC_GAIN_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: DahuaTalkConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}-mic_gain"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        cu = await self.async_get_last_number_data()
        if cu is not None and cu.native_value is not None:
            self._entry.runtime_data.set_mic_gain(float(cu.native_value))

    @property
    def native_value(self) -> float:
        return self._entry.runtime_data.mic_gain_db

    async def async_set_native_value(self, value: float) -> None:
        self._entry.runtime_data.set_mic_gain(float(value))
        self.async_write_ha_state()
