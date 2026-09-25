"""Ô chọn pipeline Assist và độ nhạy "nói xong" cho vệ tinh camera."""

from __future__ import annotations

from homeassistant.components.assist_pipeline import AssistPipelineSelect, VadSensitivitySelect
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DahuaTalkConfigEntry
from .const import DOMAIN
from .entity import DahuaTalkEntity


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DahuaTalkPipelineSelect(hass, entry),
                        DahuaTalkVadSelect(hass, entry)])


class DahuaTalkPipelineSelect(DahuaTalkEntity, AssistPipelineSelect):
    def __init__(self, hass: HomeAssistant, entry: DahuaTalkConfigEntry) -> None:
        DahuaTalkEntity.__init__(self, entry)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, entry.entry_id)


class DahuaTalkVadSelect(DahuaTalkEntity, VadSensitivitySelect):
    def __init__(self, hass: HomeAssistant, entry: DahuaTalkConfigEntry) -> None:
        DahuaTalkEntity.__init__(self, entry)
        VadSensitivitySelect.__init__(self, hass, entry.entry_id)
