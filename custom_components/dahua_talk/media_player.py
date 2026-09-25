"""Loa camera thành một media_player: ``tts.speak`` và ``play_media`` phát ra loa camera."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DahuaTalkConfigEntry
from .entity import DahuaTalkEntity
from .talk import TalkError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DahuaTalkPlayer(entry)])


class DahuaTalkPlayer(DahuaTalkEntity, MediaPlayerEntity):
    _attr_translation_key = "speaker"
    _attr_supported_features = (MediaPlayerEntityFeature.PLAY_MEDIA
                                 | MediaPlayerEntityFeature.BROWSE_MEDIA
                                 | MediaPlayerEntityFeature.MEDIA_ANNOUNCE)

    def __init__(self, entry: DahuaTalkConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}-speaker"
        self._attr_state = MediaPlayerState.IDLE

    async def async_play_media(self, media_type: MediaType | str, media_id: str,
                               **kwargs: Any) -> None:
        if media_source.is_media_source_id(media_id):
            play = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = play.url
        url = async_process_play_media_url(self.hass, media_id)
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()
        try:
            await self._entry.runtime_data.speaker.async_play_url(url)
        except (TalkError, OSError) as exc:
            _LOGGER.warning("%s: cannot play to camera speaker: %s", self.entity_id, exc)
        finally:
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()

    async def async_browse_media(self, media_content_type: MediaType | str | None = None,
                                 media_content_id: str | None = None) -> BrowseMedia:
        return await media_source.async_browse_media(
            self.hass, media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"))
